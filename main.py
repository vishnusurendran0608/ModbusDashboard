import threading
import os
import json
import time
from app.modbus_reader import poll_devices, get_data
from app.flask_server import create_app
from app.mqtt_manager import initialize_mqtt, publish_to_mqtt
from app.logger import logger  # <- use centralized logger from logger.py

# Load settings
with open("settings.json") as f:
    settings = json.load(f)

print("Current working directory:", os.getcwd())

# Initialize MQTT connection
initialize_mqtt(settings)

# Setup Flask app
app = create_app()

# Start Modbus polling in a background thread
poll_thread = threading.Thread(target=poll_devices, daemon=True)
poll_thread.start()
logger.info("Started Modbus polling thread.")

# Start MQTT publish thread
def mqtt_publish_thread():
    while True:
        device_data = get_data()
        publish_to_mqtt(device_data, settings)
        time.sleep(settings["mqtt"].get("publish_interval", 10))

mqtt_thread = threading.Thread(target=mqtt_publish_thread, daemon=True)
mqtt_thread.start()
logger.info("Started MQTT publishing thread.")

# Run Flask server
if __name__ == "__main__":
    logger.info("Starting Flask dashboard server...")
    app.run(host="0.0.0.0", port=5000, use_reloader=False)
