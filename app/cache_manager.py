# cache_manager.py
import os
import json
import logging

logger = logging.getLogger("modbus")

# Go one level up from the current file's directory (i.e., out of app/)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Point to the cache_buffer.json in the root folder
CACHE_FILE = os.path.join(ROOT_DIR, "cache_buffer.json")

def save_payload_to_cache(payload):
    try:
        cache = []
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
        cache.append(payload)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
        logger.warning("Saved payload to cache.")
    except Exception as e:
        logger.error(f"Error saving to cache: {e}")

def load_cached_payloads():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading cache: {e}")
    return []

def clear_cache():
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            logger.info("Cleared MQTT cache.")
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
