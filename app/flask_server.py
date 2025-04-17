import os
from flask import Flask, render_template, jsonify
from app.modbus_reader import get_data

# Force Flask to use the correct templates directory
TEMPLATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
app = Flask(__name__, template_folder=TEMPLATE_DIR)

def create_app():
    @app.route('/')
    def index():
        return render_template("index.html")

    @app.route('/data')
    def data():
        return jsonify(get_data())

    return app
