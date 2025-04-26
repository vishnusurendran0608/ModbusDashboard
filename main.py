import threading
import logging
import os
from app.modbus_reader import poll_devices, start_sql_thread
from app.flask_server import create_app

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

# Start SQL uploading thread
start_sql_thread()

# Start Flask server (dashboard)
if __name__ == "__main__":
    logger.info("Starting Flask dashboard server...")
    app.run(host="0.0.0.0", port=5000, use_reloader=False)
