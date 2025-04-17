import threading
from app.modbus_reader import poll_devices
from app.flask_server import create_app
import logging
import os
print("Current working directory:", os.getcwd())
# Setup app and logging
app = create_app()
logging.basicConfig(level=logging.INFO)

# Start polling in a background thread
poll_thread = threading.Thread(target=poll_devices, daemon=True)
poll_thread.start()

# Start Flask in the main thread
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, use_reloader=False)
