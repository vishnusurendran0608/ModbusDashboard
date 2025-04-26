import threading
import json
import os

cache_file = "cache_buffer.json"
cache_lock = threading.Lock()

def append_to_cache(entry):
    with cache_lock:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                data = json.load(f)
        else:
            data = []

        data.append(entry)

        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)

def load_cache():
    with cache_lock:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
        else:
            return []

def clear_cache():
    with cache_lock:
        if os.path.exists(cache_file):
            with open(cache_file, 'w') as f:
                json.dump([], f)
