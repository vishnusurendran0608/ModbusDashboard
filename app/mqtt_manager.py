# app/mqtt_manager.py

import json
import threading
import time
import logging
from awscrt import io, mqtt5
from awsiot import mqtt5_client_builder
from pathlib import Path
from concurrent.futures import Future
from app.cache_manager import save_payload_to_cache, load_cached_payloads, clear_cache
import os

mqtt_client_instance = None
logger = logging.getLogger("modbus")

# ----------------------
# Configuration
# ----------------------
DEVICE_FILE = "device.json"
# Load configuration
with open(DEVICE_FILE, 'r') as f:
    config = json.load(f)
pi_id = config.get('pi_id')

# Endpoint for AWS IoT Core
AWS_IOT_ENDPOINT = "d037955127pwy1xzu5whf-ats.iot.eu-west-1.amazonaws.com"

# Get the directory two levels up (Root Folder)
BASE_DIR = Path(__file__).resolve().parent.parent

CERT_PATH = f"{pi_id}-certificate.pem.crt"
KEY_PATH = f"{pi_id}-private.pem.key"
CA_PATH = "AmazonRootCA1.pem"

# Event to signal when the script is done (e.g., on KeyboardInterrupt).
is_sample_done = threading.Event()
future_connection_success = Future()
# ----------------------
# Lifecycle Callbacks
# ----------------------
def on_lifecycle_connection_success(lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData):
    """
    Callback for when the MQTT5 client successfully connects to AWS IoT Core.
    
    Args:
        lifecycle_connect_success_data: Data about the connection success event.
    """
    print("Lifecycle Connection Success")
    global future_connection_success
    future_connection_success.set_result(lifecycle_connect_success_data)

def on_lifecycle_stopped(lifecycle_stopped_data: mqtt5.LifecycleStoppedData):
    """
    Callback for when the MQTT5 client stops.
    
    Args:
        lifecycle_stopped_data: Data about the stop event.
    """
    print("Client Stopped.")
    is_sample_done.set()


def initialize_mqtt(settings):
    global mqtt_client_instance
    mqtt_config = settings.get("mqtt", {})
    if mqtt_config.get("enabled", False):
        try:

            mqtt_client_instance = mqtt5_client_builder.mtls_from_path(
                                   endpoint=AWS_IOT_ENDPOINT,
                                   port=8883,
                                   cert_filepath=CERT_PATH,
                                   pri_key_filepath=KEY_PATH,
                                   ca_filepath=CA_PATH,
                                   client_id=pi_id,
                                   clean_session=False,
                                   keep_alive_secs=30,
                                   on_lifecycle_connection_success=on_lifecycle_connection_success,
                                   on_lifecycle_stopped=on_lifecycle_stopped)                               

            mqtt_client_instance.start()
            future_connection_success.result()
            logger.info(f"Connected to AWS IoT Core at {AWS_IOT_ENDPOINT}")

        except Exception as e:
            logger.error(f"MQTT (AWS IoT) connection failed: {e}")
            mqtt_client_instance = None

def publish_to_mqtt(device_data, settings):
    organized_devices = []
    for device_key, entries in device_data.items():
        if not entries:
            continue

        # Use first entry to extract static info
        first_entry = entries[0]
        device_type = first_entry.get("device_type", "")
        device_name = first_entry.get("device_name", "")

        metrics = {}
        for entry in entries:
            variable = entry["variable_name"]
            value = entry["value"]
            metrics[variable] = value

        organized_devices.append({
            "device_id": device_key,
            "device_type": device_type,
            "device_name": device_name,
            "metrics": metrics
        })
    
    payload = {
        "tenant_id": config["tenant_id"],
        "customer_id": config["customer_id"],
        "site_id": config["site_id"],
        "pi_id": pi_id,
        "timestamp": int(time.time() * 1000),
        "devices": organized_devices
    }
    
    topic = f"solar/{payload['tenant_id']}/{payload['customer_id']}/{payload['site_id']}/{payload['pi_id']}/data"
    if mqtt_client_instance:
        try:
            payload_json = json.dumps(payload, default=str)
            publish_future = mqtt_client_instance.publish(
                mqtt5.PublishPacket(
                    topic=topic,
                    payload=payload_json.encode("utf-8"),
                    qos=mqtt5.QoS.AT_LEAST_ONCE,
                )
            )
            publish_future.result()
            logger.info(f"Published payload to AWS IoT Core topic: {topic}")
            sync_cached_payloads()  # Sync if there are any cached payloads
        except Exception as e:
            logger.error(f"Failed to publish to AWS IoT: {e}")
            save_payload_to_cache(payload)  # Save to cache
    else:
        save_payload_to_cache(payload)
        logger.warning("MQTT client not connected. Skipping publish.")


def sync_cached_payloads():
    cached_payloads = load_cached_payloads()
    for payload in cached_payloads:
        try:
            # If payload is a string (loaded from file), convert to dict
            if isinstance(payload, str):
                payload = json.loads(payload)

            topic = f"solar/{payload['tenant_id']}/{payload['customer_id']}/{payload['site_id']}/{payload['pi_id']}/data"

            if mqtt_client_instance:
                message = mqtt5.PublishPacket(
                    topic=topic,
                    payload=json.dumps(payload).encode("utf-8"),
                    qos=mqtt5.QoS.AT_LEAST_ONCE,
                )
                mqtt_client_instance.publish(message).result()
                logger.info(f"Synced cached payload to: {topic}")
            else:
                logger.warning("MQTT not available. Skipping cache sync.")
                return

        except Exception as e:
            logger.error(f"Error syncing cached payload: {e}")
            return  # You can also use 'continue' if you want to try the rest

    clear_cache()

# For tracking last published error line
ERROR_LOG_PATH = "logs/error.log"
ERROR_STATE_PATH = "logs/last_error_line.txt"

def publish_new_errors_to_mqtt(settings):
    """
    Publishes only new error log entries to MQTT.
    """
    if not mqtt_client_instance:
        logger.warning("MQTT client not connected. Skipping error log publish.")
        return

    try:
        if not os.path.exists(ERROR_LOG_PATH):
            logger.warning(f"Error log file not found: {ERROR_LOG_PATH}")
            return

        # Read last published line number
        last_line = 0
        if os.path.exists(ERROR_STATE_PATH):
            with open(ERROR_STATE_PATH, "r") as f:
                last_line = int(f.read().strip())

        # Read new error lines
        with open(ERROR_LOG_PATH, "r") as f:
            all_lines = f.readlines()

        new_lines = all_lines[last_line:]
        if not new_lines:
            return  # No new errors

        # Construct payload
        payload = {
            "tenant_id": config["tenant_id"],
            "customer_id": config["customer_id"],
            "site_id": config["site_id"],
            "pi_id": pi_id,
            "timestamp": int(time.time() * 1000),
            "errors": [line.strip() for line in new_lines]
        }

        topic = f"solar/{payload['tenant_id']}/{payload['customer_id']}/{payload['site_id']}/{payload['pi_id']}/errors"

        message = mqtt5.PublishPacket(
            topic=topic,
            payload=json.dumps(payload).encode("utf-8"),
            qos=mqtt5.QoS.AT_LEAST_ONCE,
        )
        mqtt_client_instance.publish(message).result()
        logger.info(f"Published new error logs to: {topic}")

        # Update line state
        with open(ERROR_STATE_PATH, "w") as f:
            f.write(str(len(all_lines)))

    except Exception as e:
        logger.error(f"Failed to publish error logs to MQTT: {e}")