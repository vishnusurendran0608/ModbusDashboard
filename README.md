# ModbusDashboard

A real-time Modbus TCP dashboard using Python and Flask. Displays data polled from multiple Modbus slave devices based on register and device mappings.

---

## 📁 Folder Structure

ModbusDashboard/ ├── app/ │ ├── init.py │ ├── modbus_reader.py │ ├── logger.py │ ├── csv_parser.py │ ├── utils.py ├── static/ │ └── chart.js ├── templates/ │ └── dashboard.html ├── data/ │ ├── register_map.csv │ └── device_map.csv ├── logs/ │ └── (log files are stored here, automatically rotated) ├── settings.json ├── main.py ├── requirements.txt └── README.md