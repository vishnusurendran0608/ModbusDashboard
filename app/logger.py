import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("modbus_logger")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if already added
    if not logger.handlers:
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "modbus.log"), maxBytes=10_000_000, backupCount=5
        )
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

    return logger

# Global logger instance
log = setup_logger()
