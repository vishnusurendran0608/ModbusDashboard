# app/logger.py

import logging
import os

# Ensure log directory exists
os.makedirs("logs", exist_ok=True)

# Create a logger
logger = logging.getLogger("modbus")
logger.setLevel(logging.DEBUG)  # Capture all levels, filtered by handlers

# Remove any previous handlers
if logger.hasHandlers():
    logger.handlers.clear()

# ----------------------------
# Custom log level filters
# ----------------------------

class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO

class WarningFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.WARNING

class ErrorFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.ERROR

# ----------------------------
# Info handler
# ----------------------------
info_handler = logging.FileHandler("logs/info.log", mode='a', encoding='utf-8')
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(logging.Formatter('%(asctime)s [INFO] %(message)s'))
info_handler.addFilter(InfoFilter())

# ----------------------------
# Warning handler
# ----------------------------
warning_handler = logging.FileHandler("logs/warning.log", mode='a', encoding='utf-8')
warning_handler.setLevel(logging.WARNING)
warning_handler.setFormatter(logging.Formatter('%(asctime)s [WARNING] %(message)s'))
warning_handler.addFilter(WarningFilter())

# ----------------------------
# Error handler
# ----------------------------
error_handler = logging.FileHandler("logs/error.log", mode='a', encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s [ERROR] %(message)s'))
error_handler.addFilter(ErrorFilter())

# ----------------------------
# Console handler (optional)
# ----------------------------
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

# Add handlers to logger
logger.addHandler(info_handler)
logger.addHandler(warning_handler)
logger.addHandler(error_handler)
logger.addHandler(console_handler)
