import csv

def parse_register_map(path):
    with open(path, mode='r', encoding='utf-8-sig', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        register_map = []
        for row in reader:
            register_map.append({
                "device_type_id": row["device_type_id"].strip(),
                "variable_name": row["variable_name"].strip(),
                "access": row["access"].strip(),
                "type": row["type"].strip(),
                "unit": row["unit"].strip(),
                "gain": float(row["gain"]),
                "address": int(row["address"]),
                "quantity": int(row["quantity"])
            })
        return register_map

def parse_device_map(path):
    with open(path, mode='r', encoding='utf-8-sig', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        device_map = []
        for row in reader:
            device_map.append({
                "device_id": int(row["device_id"]),
                "slave_id": int(row["slave_id"]),
                "device_name": row["device_name"].strip(),
                "device_type_id": row["device_type_id"].strip(),
                "address": row["address"].strip(),  # IP or serial port
                "port_baudRate": row["port_baudRate"].strip(),  # port for TCP or baud rate for RTU
                "protocol": row["protocol"].strip().upper(),  # "TCP" or "RTU"
                "byte_swap": row.get("byte_swap", "none").strip()
            })
        return device_map
