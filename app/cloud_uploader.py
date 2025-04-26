import time
import json
import logging
import pyodbc
from app.cache_manager import load_cache, clear_cache

# Load settings
with open("settings.json") as f:
    settings = json.load(f)

sql_config = settings.get("sql", {})

logger = logging.getLogger("modbus")

def upload_to_cloud():
    while True:
        try:
            rows = load_cache()

            if not rows:
                time.sleep(10)
                continue

            conn_str = (
                f"DRIVER={{{sql_config['driver']}}};"
                f"SERVER={sql_config['server']};"
                f"DATABASE={sql_config['database']};"
                f"UID={sql_config['uid']};"
                f"PWD={sql_config['pwd']};"
                "Encrypt=yes;"
                "TrustServerCertificate=no;"
                "Connection Timeout=30;"
            )

            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            insert_sql = f"""
                INSERT INTO {sql_config['table']}
                (timestamp, device_id, device_name, variable_name, address, value, unit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """

            values = []
            for row in rows:
                values.append((
                    row.get("timestamp"),
                    row.get("device_id"),
                    row.get("device_name"),
                    row.get("variable_name"),
                    row.get("address"),
                    row.get("value"),
                    row.get("unit")
                ))

            cursor.executemany(insert_sql, values)
            conn.commit()
            conn.close()

            logger.info(f"[SQL] Inserted {len(values)} records into {sql_config['table']}.")
            clear_cache()

        except Exception as e:
            logger.error(f"[SQL] Failed to upload to cloud: {e}")

        time.sleep(10)

def start_uploader_thread():
    uploader_thread = threading.Thread(target=upload_to_cloud, daemon=True)
    uploader_thread.start()
    logger.info("Started cloud uploader thread.")
