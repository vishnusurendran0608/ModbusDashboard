import json
import logging
import boto3
import watchtower
from datetime import datetime
import os
import re
from app.logger import logger

# Set up module-level logger

logger.setLevel(logging.ERROR)

# Remove any default handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Global to hold the current device ID (optional export)
current_pi_id = None

def load_aws_config(config_file_path):
    """Load AWS credentials from a JSON config file."""
    try:
        config_file_path = os.getenv("AWS_CONFIG_FILE", config_file_path)
        with open(config_file_path, 'r') as file:
            config = json.load(file)
            return {
                'aws_access_key_id': config['access_id'],
                'aws_secret_access_key': config['access'],
                'region_name': config['region']
            }
    except Exception as e:
        logger.error(f"Error loading AWS config: {str(e)}")
        raise

def read_pi_id(json_file_path):
    """Read pi_id from JSON file and validate it."""
    try:
        if not os.path.exists(json_file_path):
            raise FileNotFoundError(f"JSON file not found: {json_file_path}")
        
        with open(json_file_path, 'r') as file:
            data = json.load(file)
            pi_id = data.get('pi_id')
            
            if not pi_id:
                raise ValueError("pi_id not found in JSON file")
            
            if not re.match(r'^[a-zA-Z0-9._/-]{1,512}$', pi_id):
                raise ValueError("pi_id must be 1-512 characters, alphanumeric, or contain ._/+-")
            
            logger.info(f"Using pi_id: {pi_id}")
            return pi_id
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON format: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error reading JSON file: {str(e)}")
        raise

def init_logger(config_path="aws_config.json", device_config="device.json"):
    """Initializes the logger to stream to AWS CloudWatch."""
    global current_pi_id

    try:
        aws_config = load_aws_config(config_path)
        boto3.setup_default_session(
            aws_access_key_id=aws_config['aws_access_key_id'],
            aws_secret_access_key=aws_config['aws_secret_access_key'],
            region_name=aws_config['region_name']
        )

        pi_id = read_pi_id(device_config)
        current_pi_id = pi_id

        log_group = f"/aws/pi/{pi_id}"
        stream_name = f"{pi_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        cloudwatch_handler = watchtower.CloudWatchLogHandler(
            log_group=log_group,
            stream_name=stream_name,
            create_log_group=True
        )

        formatter = logging.Formatter(
            '[%(levelname)s] %(asctime)s "message": "%(message)s"'
        )
        cloudwatch_handler.setFormatter(formatter)

        # Avoid re-adding handler on repeated calls
        if not any(isinstance(h, watchtower.CloudWatchLogHandler) for h in logger.handlers):
            logger.addHandler(cloudwatch_handler)

        logger.info(f"CloudWatch logging initialized for {log_group}/{stream_name}")

    except Exception as e:
        logger.error(f"Logger setup failed: {str(e)}")
        raise
