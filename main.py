import threading
<<<<<<< HEAD
import logging
import os
from app.modbus_reader import poll_devices, start_sql_thread
from app.flask_server import create_app
=======
from app.modbus_reader import poll_devices, get_data
from app.flask_server import create_app
from app.mqtt_manager import initialize_mqtt, publish_to_mqtt
import logging
import os
import json
import time

# Load settings
with open("settings.json") as f:
    settings = json.load(f)

print("Current working directory:", os.getcwd())

# Initialize MQTT connection
initialize_mqtt(settings)


# Setup app and logging
app = create_app()
logging.basicConfig(level=logging.INFO)
>>>>>>> 4c30550 (AWS MQTT Added)

# Print current working directory
print("Current working directory:", os.getcwd())

# Setup Flask app and logging
app = create_app()

os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("modbus")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("logs/log_1.txt", mode='a', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
console_handler.setFormatter(console_formatter)

# Always attach handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Start Modbus polling in a background thread
poll_thread = threading.Thread(target=poll_devices, daemon=True)
poll_thread.start()
logger.info("Started Modbus polling thread.")

<<<<<<< HEAD
# Start SQL uploading thread
start_sql_thread()

# Start Flask server (dashboard)
=======
# Start MQTT publish thread
def mqtt_publish_thread():
    while True:
        device_data = get_data()
        publish_to_mqtt(device_data, settings)
        time.sleep(settings["mqtt"].get("publish_interval", 10))

mqtt_thread = threading.Thread(target=mqtt_publish_thread, daemon=True)
mqtt_thread.start()

# Run Flask server
>>>>>>> 4c30550 (AWS MQTT Added)
if __name__ == "__main__":
    logger.info("Starting Flask dashboard server...")
    app.run(host="0.0.0.0", port=5000, use_reloader=False)
