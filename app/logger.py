# logger.py

import logging
import os

# Ensure log directory exists
os.makedirs("logs", exist_ok=True)

# Get or create logger
logger = logging.getLogger("modbus")
logger.setLevel(logging.INFO)

# Formatter for all log entries
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

# Info log handler (INFO and below)
info_handler = logging.FileHandler("logs/info.log", mode='a', encoding='utf-8')
info_handler.setLevel(logging.INFO)
info_handler.addFilter(lambda record: record.levelno <= logging.INFO)
info_handler.setFormatter(formatter)

# Error log handler (WARNING and above)
error_handler = logging.FileHandler("logs/error.log", mode='a', encoding='utf-8')
error_handler.setLevel(logging.WARNING)
error_handler.setFormatter(formatter)

# Console log handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Avoid duplicate handlers
if logger.hasHandlers():
    logger.handlers.clear()

# Add handlers
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(console_handler)
