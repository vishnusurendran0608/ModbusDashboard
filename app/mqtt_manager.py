# app/mqtt_manager.py

import json
import threading
import time
import logging
from awscrt import io, mqtt5
from awsiot import mqtt5_client_builder

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

# Paths to the shared provisioning claim certificate and keys used for initial provisioning.
CERT_PATH = f"{pi_id}-certificate.pem.crt"
KEY_PATH = f"{pi_id}-private.pem.key"
CA_PATH = "AmazonRootCA1.pem"

# Event to signal when the script is done (e.g., on KeyboardInterrupt).
is_sample_done = threading.Event()

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
            event_loop_group = io.EventLoopGroup(1)
            host_resolver = io.DefaultHostResolver(event_loop_group)
            client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

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

            connect_future = mqtt_client_instance.start()
            connect_future.result()
            logger.info(f"Connected to AWS IoT Core at {mqtt_config['endpoint']}")

        except Exception as e:
            logger.error(f"MQTT (AWS IoT) connection failed: {e}")
            mqtt_client_instance = None

def publish_to_mqtt(device_data, settings):
    mqtt_config = settings.get("mqtt", {})
    payload = {
        "tenant_id": config["tenant_id"],
        "customer_id": config["customer_id"],
        "site_id": config["site_id"],
        "pi_id": pi_id,
        "timestamp": int(time.time() * 1000),
        "devices": device_data
    }
    topic = f"solar/{payload['tenant_id']}/{payload['customer_id']}/{payload['site_id']}/{payload['pi_id']}/data"
    if mqtt_client_instance:
        try:
            payload = json.dumps(device_data, default=str)
            publish_future = mqtt_client_instance.publish(
                mqtt5.PublishPacket(
                    topic=mqtt_config.get(topic, "default/topic"),
                    payload=payload.encode("utf-8"),
                    qos=mqtt5.QoS.AT_LEAST_ONCE,
                )
            )
            publish_future.result()
            logger.info(f"Published payload to AWS IoT Core topic: {mqtt_config.get('topic')}")
        except Exception as e:
            logger.error(f"Failed to publish to AWS IoT: {e}")
    else:
        logger.warning("MQTT client not connected. Skipping publish.")
