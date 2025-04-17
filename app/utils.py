import struct

def apply_byte_order(raw_values, data_type, swap_bytes):
    # Combine registers into bytes
    if swap_bytes == "word":
        raw_values = [raw_values[i ^ 1] for i in range(len(raw_values))]
    elif swap_bytes == "both":
        raw_values = [raw_values[i ^ 1] for i in range(len(raw_values))]
        raw_values.reverse()

    # Convert to bytes
    byte_array = b''.join(r.to_bytes(2, byteorder='big') for r in raw_values)

    try:
        if data_type == "U16":
            return int.from_bytes(byte_array, byteorder='big', signed=False)
        elif data_type == "I16":
            return int.from_bytes(byte_array, byteorder='big', signed=True)
        elif data_type == "U32":
            return int.from_bytes(byte_array, byteorder='big', signed=False)
        elif data_type == "I32":
            return int.from_bytes(byte_array, byteorder='big', signed=True)
        elif data_type == "FLOAT":
            return struct.unpack(">f", byte_array)[0]  # big-endian float
        else:
            return int.from_bytes(byte_array, byteorder='big')  # fallback
    except Exception as e:
        return f"decode error: {e}"
