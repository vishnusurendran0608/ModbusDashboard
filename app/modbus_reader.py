import csv
import json
import threading
import time
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from app.csv_parser import parse_register_map, parse_device_map
from app.utils import apply_byte_order
from datetime import datetime
import os
from collections import defaultdict
from app.logger import logger

# Load configuration
with open("settings.json") as f:
    settings = json.load(f)

register_map = parse_register_map("data/register_map.csv")
device_map = parse_device_map("data/device_map.csv")

max_registers = settings.get("max_registers", 100)

data_lock = threading.Lock()
device_data = defaultdict(list)
polling_locks = defaultdict(threading.Lock)

def poll_device(device):
    protocol = device.get('protocol', 'TCP').strip().upper()
    swap_bytes = device.get('byte_swap', 'none')
    unit_id = int(device['slave_id'])
    device_key = f"{device['device_id']}_{unit_id}"

    if protocol == 'TCP':
        address = device['address']
        port = int(device.get('port_baudRate', 502))
        client = ModbusTcpClient(address, port=port)
    elif protocol == 'RTU':
        address = device['address']
        baudrate = int(device.get('port_baudRate', 9600))
        client = ModbusSerialClient(
            port=address,
            baudrate=baudrate,
            timeout=3,
            parity='N',
            stopbits=1,
            bytesize=8
        )
    else:
        logger.error(f"Unsupported protocol '{protocol}' for device ID: {device['device_id']}")
        return

    with polling_locks[address]:
        if not client.connect():
            logger.warning(f"Unable to connect to Address: {address}, ID: {unit_id}")
            return

        logger.info(f"Connected to device at Address: {address}, ID: {unit_id}")
        with data_lock:
            device_data[device_key] = []

        regs = [r for r in register_map if r['device_type_id'] == device['device_type_id']]
        regs.sort(key=lambda r: (int(r.get('function_code', 3)), int(r['address'])))

        i = 0
        while i < len(regs):
            current_fc = int(regs[i].get('function_code', 3))
            start_address = int(regs[i]['address'])
            block = [regs[i]]
            total_regs = int(regs[i]['quantity'])
            j = i + 1

            while j < len(regs):
                next_fc = int(regs[j].get('function_code', 3))
                if next_fc != current_fc:
                    break

                prev_end = int(regs[j-1]['address']) + int(regs[j-1]['quantity'])
                next_start = int(regs[j]['address'])
                if next_start != prev_end:
                    break

                next_addr = int(regs[j]['address'])
                next_qty = int(regs[j]['quantity'])
                if next_addr + next_qty - start_address <= max_registers:
                    block.append(regs[j])
                    total_regs = (next_addr + next_qty) - start_address
                    j += 1
                else:
                    break

            end_address = start_address + total_regs - 1
            logger.info(f"Reading FC {current_fc} from Device Address: {address}, ID: {unit_id}, Block: {start_address} to {end_address}")

            read_func = {
                3: client.read_holding_registers,
                4: client.read_input_registers
            }.get(current_fc)

            if read_func is None:
                logger.warning(f"Unsupported function code {current_fc} at address {start_address}")
                i = j
                continue

            result = read_func(address=start_address, count=total_regs, slave=unit_id)

            if result and not result.isError():
                for reg in block:
                    addr = int(reg['address'])
                    offset = addr - start_address
                    quantity = int(reg['quantity'])
                    variable = reg['variable_name']

                    try:
                        raw_values = result.registers[offset:offset+quantity]
                        value = apply_byte_order(raw_values, reg['type'], swap_bytes)

                        gain = float(reg.get('gain', 1))
                        if gain != 0:
                            value = value / gain

                        with data_lock:
                            entry = {
                                "timestamp": datetime.now().isoformat(),
                                "device_key": device_key,
                                "variable_name": variable,
                                "address": addr,
                                "value": value,
                                "unit": reg.get("unit", ""),
                                "device_name": device["device_name"]
                            }
                            device_data[device_key].append(entry)

                        logger.info(f"Read {variable} = {value} from Address: {address}, ID: {unit_id}, Address: {addr}")
                    except Exception as e:
                        logger.error(f"Error decoding register {variable} at address {addr}: {e}")
            else:
                logger.warning(f"Failed to read FC {current_fc} block at {start_address} from Address: {address}, ID: {unit_id}")

            i = j

        client.close()
        logger.info(f"Disconnected from Address: {address}, ID: {unit_id}")

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
        return device_data
