import csv
import json
import threading
import time
import logging
from pymodbus.client import ModbusTcpClient
from app.csv_parser import parse_register_map, parse_device_map
from app.utils import apply_byte_order
from datetime import datetime
import os
from collections import defaultdict

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logger
logger = logging.getLogger("modbus")
logger.setLevel(logging.INFO)
handler = logging.FileHandler("logs/log_1.txt", mode='a', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(handler)

# Load configuration
with open("settings.json") as f:
    settings = json.load(f)

register_map = parse_register_map("data/register_map.csv")
device_map = parse_device_map("data/device_map.csv")

data_lock = threading.Lock()
device_data = defaultdict(dict)

polling_locks = defaultdict(threading.Lock)

def read_registers(client, unit_id, address, count):
    try:
        return client.read_holding_registers(address=address, count=count, slave=unit_id)
    except Exception as e:
        logger.error(f"Error reading from Unit ID {unit_id}: {e}")
        return None

def poll_device(device):
    ip = device['ip_address']
    port = int(device.get('port', 1502))
    unit_id = int(device['slave_id'])
    swap_bytes = device.get('byte_swap', 'none')
    device_key = f"{ip}_{unit_id}"

    with polling_locks[ip]:
        client = ModbusTcpClient(ip, port=port)
        if not client.connect():
            logger.warning(f"Unable to connect to IP: {ip}, ID: {unit_id}")
            return

        logger.info(f"Connected to device at IP: {ip}, ID: {unit_id}")
        device_data[device_key] = {}

        regs = [r for r in register_map if r['device_type_id'] == device['device_type_id']]
        regs.sort(key=lambda r: int(r['address']))

        i = 0
        while i < len(regs):
            start_address = int(regs[i]['address'])
            block = [regs[i]]
            total_regs = int(regs[i]['quantity'])

            j = i + 1
            while j < len(regs):
                next_addr = int(regs[j]['address'])
                next_qty = int(regs[j]['quantity'])
                if next_addr + next_qty - start_address <= 125:
                    block.append(regs[j])
                    total_regs = (next_addr + next_qty) - start_address
                    j += 1
                else:
                    break

            end_address = start_address + total_regs - 1
            logger.info(f"Reading from Device IP: {ip}, ID: {unit_id}, Address Block: {start_address} to {end_address}")
            result = read_registers(client, unit_id, start_address, total_regs)

            if result and not result.isError():
                for reg in block:
                    addr = int(reg['address'])
                    offset = addr - start_address
                    quantity = int(reg['quantity'])
                    variable = reg['variable_name']

                    try:
                        raw_values = result.registers[offset:offset+quantity]
                        value = apply_byte_order(raw_values, reg['type'], swap_bytes)

                        # Apply gain to the final decoded value
                        gain = float(reg.get('gain', 1))
                        if gain != 0:
                            value = value / gain

                        with data_lock:
                            #device_data[device_key][variable] = value
                            if device_key not in device_data or not isinstance(device_data[device_key], list):
                               device_data[device_key] = []
                            device_data[device_key].append({
                                       "address": addr,
                                       "variable_name": variable,
                                       "value": value,
                                       "unit": reg.get("unit", "")
                             })

                        logger.info(f"Read {variable} = {value} from IP: {ip}, ID: {unit_id}, Address: {addr}")
                    except Exception as e:
                        logger.error(f"Error decoding register {variable} at address {addr}: {e}")
            else:
                logger.warning(f"Failed to read registers at block starting {start_address} from IP: {ip}, ID: {unit_id}")

            i = j

        client.close()
        logger.info(f"Disconnected from IP: {ip}, ID: {unit_id}")

def poll_devices():
    while True:
        threads = []
        for device in device_map:
            t = threading.Thread(target=poll_device, args=(device,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        time.sleep(settings.get("poll_interval", 5))

def get_data():
    with data_lock:
         return json.loads(json.dumps(device_data, default=str))
