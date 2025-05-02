# main.py

import threading
import os
from app.modbus_reader import poll_devices
from app.mqtt_manager import initialize_mqtt, publish_to_mqtt
from app.cache_manager import initialize_cache
from app.cloud_uploader import start_sql_thread
from app.flask_server import create_app
from app.logger import logger  # Import the configured logger

import time
import json

from app.modbus_reader import get_data
from app.mqtt_manager import mqtt_client_instance, settings

# Print current working directory
print("Current working directory:", os.getcwd())

# Initialize cache DB
initialize_cache()

# Initialize Flask app
app = create_app()

# Start Modbus polling in background
poll_thread = threading.Thread(target=poll_devices, daemon=True)
poll_thread.start()
logger.info("Started Modbus polling thread.")

# Start SQL upload thread
start_sql_thread()

# Initialize MQTT connection
initialize_mqtt()

# Start MQTT publish thread
def mqtt_publish_thread():
    while True:
        device_data = get_data()
        publish_to_mqtt(device_data, settings)
        time.sleep(settings["mqtt"].get("publish_interval", 10))

mqtt_thread = threading.Thread(target=mqtt_publish_thread, daemon=True)
mqtt_thread.start()
logger.info("Started MQTT publishing thread.")

# Start Flask dashboard
if __name__ == "__main__":
    logger.info("Starting Flask dashboard server...")
    app.run(host="0.0.0.0", port=5000, use_reloader=False)
