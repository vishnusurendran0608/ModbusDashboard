import json
import time
from awscrt import mqtt5
from awsiot import iotidentity, mqtt5_client_builder
from concurrent.futures import Future
import threading
import traceback
import sys
import boto3
import requests

# ----------------------
# Configuration
# ----------------------
# Endpoint for AWS IoT Core
ENDPOINT = "d037955127pwy1xzu5whf-ats.iot.eu-west-1.amazonaws.com"
CREDENTIALS_ENDPOINT = "c9cq0lk0lo8th.credentials.iot.eu-west-1.amazonaws.com"

# Paths to the shared provisioning claim certificate and keys used for initial provisioning.
CLAIM_CERT_PATH = "shared-certificate.pem.crt"
CLAIM_KEY_PATH = "shared-private.pem.key"
ROOT_CA_PATH = "AmazonRootCA1.pem"

# Name of the provisioning template in AWS IoT Core.
# This template defines how the device is provisioned (e.g., thing creation, attributes).
TEMPLATE_NAME = "SolarDeviceProvisioningTemplate"
ROLE_ALIAS = "IoTDeviceProvisioningRole-credentials"
# AWS region where the IoT Core resources are located.
REGION = "eu-west-1"

# Path to the configuration file containing the device ID (pi_id).
CONFIG_FILE = "device.json"

# Load configuration
with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)
client_id = config.get('pi_id')

# ----------------------
# Global Variables
# ----------------------
# Event to signal when the script is done (e.g., on KeyboardInterrupt).
is_sample_done = threading.Event()

# MQTT5 client and identity client for interacting with AWS IoT Core during provisioning.
mqtt5_client = None
identity_client = None

# Responses from provisioning steps, used to track progress and extract certificates.
createKeysAndCertificateResponse = None
registerThingResponse = None
future_connection_success = Future()

# Device attributes retrieved from the Device Shadow after provisioning.
site_id, tenant_id, customer_id = None, None, None

# ----------------------
# Utility Functions
# ----------------------
def exit(msg_or_exception):
    """
    Gracefully exits the script, stopping the MQTT5 client if necessary.
    
    Args:
        msg_or_exception: Either a message (str) or an exception to log.
    """
    if isinstance(msg_or_exception, Exception):
        print("Exiting Sample due to exception.")
        traceback.print_exception(msg_or_exception.__class__, msg_or_exception, sys.exc_info()[2])
    else:
        print("Exiting Sample:", msg_or_exception)

    print("Stop the Client...")
    mqtt5_client.stop()

# ----------------------
# Lifecycle Callbacks
# ----------------------
def on_lifecycle_connection_success(lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData):
    """
    Callback for when the MQTT5 client successfully connects to AWS IoT Core.
    
    Args:
        lifecycle_connect_success_data: Data about the connection success event.
    """
    print("Lifecycle Connection Success")
    global future_connection_success
    future_connection_success.set_result(lifecycle_connect_success_data)

def on_lifecycle_stopped(lifecycle_stopped_data: mqtt5.LifecycleStoppedData):
    """
    Callback for when the MQTT5 client stops.
    
    Args:
        lifecycle_stopped_data: Data about the stop event.
    """
    print("Client Stopped.")
    is_sample_done.set()

# ----------------------
# Provisioning Callbacks
# ----------------------
def on_publish_register_thing(future):
    """
    Callback for when the RegisterThing request is published.
    
    Args:
        future: Future object representing the publish operation.
    """
    try:
        future.result()
        print("Published RegisterThing request..")
    except Exception as e:
        print("Failed to publish RegisterThing request.")
        exit(e)

def on_publish_create_keys_and_certificate(future):
    """
    Callback for when the CreateKeysAndCertificate request is published.
    
    Args:
        future: Future object representing the publish operation.
    """
    try:
        future.result()
        print("Published CreateKeysAndCertificate request..")
    except Exception as e:
        print("Failed to publish CreateKeysAndCertificate request.")
        exit(e)

def createkeysandcertificate_execution_accepted(response):
    """
    Callback for when the CreateKeysAndCertificate request is accepted.
    Stores the response containing the new certificate and keys, and saves them to files.
    
    Args:
        response: The response containing the new certificate and keys.
    """
    global createKeysAndCertificateResponse
    createKeysAndCertificateResponse = response
    # print("Received CreateKeysAndCertificate response:", response)

    # Save the new certificate and keys to files
    new_cert = response.certificate_pem
    new_private_key = response.private_key
    with open(f"{client_id}-certificate.pem.crt", "w") as f:
        f.write(new_cert)
    with open(f"{client_id}-private.pem.key", "w") as f:
        f.write(new_private_key)
    print("Saved new device certificate and keys.")
    
def createkeysandcertificate_execution_rejected(rejected):
    """
    Callback for when the CreateKeysAndCertificate request is rejected.
    Exits the script with the error details.
    
    Args:
        rejected: The rejection response with error details.
    """
    exit("CreateKeysAndCertificate Request rejected with code:'{}' message:'{}' status code:'{}'".format(
        rejected.error_code, rejected.error_message, rejected.status_code))

def registerthing_execution_accepted(response):
    """
    Callback for when the RegisterThing request is accepted.
    Stores the response and proceeds to post-provisioning steps.
    
    Args:
        response: The response containing the provisioning result.
    """
    global registerThingResponse
    registerThingResponse = response
    print("Received RegisterThing response:", response)

def registerthing_execution_rejected(rejected):
    """
    Callback for when the RegisterThing request is rejected.
    Exits the script with the error details.
    
    Args:
        rejected: The rejection response with error details.
    """
    exit("RegisterThing Request rejected with code:'{}' message:'{}' status code:'{}'".format(
        rejected.error_code, rejected.error_message, rejected.status_code))

# ----------------------
# Post-Provisioning Functions
# ----------------------
def fetch_temporary_credentials():
    """
    Fetches temporary AWS credentials using the new device certificate.
    These credentials are used for updating the Device Shadow via boto3.
    
    Returns:
        dict: Temporary credentials (access_key, secret_key, session_token), or None if failed.
    """
    try:
        credentials_endpoint = f"https://{CREDENTIALS_ENDPOINT.replace('-ats.', '.credentials.')}/role-aliases/{ROLE_ALIAS}/credentials"
        headers = {
            "x-amzn-iot-thing": client_id
        }
        cert = (f"{client_id}-certificate.pem.crt", f"{client_id}-private.pem.key")
        response = requests.get(credentials_endpoint, headers=headers, cert=cert, verify=ROOT_CA_PATH)
        response.raise_for_status()
        creds = response.json()
        print("Successfully fetched temporary credentials.")
        return {
            "access_key": creds["credentials"]["accessKeyId"],
            "secret_key": creds["credentials"]["secretAccessKey"],
            "session_token": creds["credentials"]["sessionToken"]
        }
    except Exception as e:
        print("Failed to fetch temporary credentials:", str(e))
        return None

def get_thing_attributes():
    """
    Retrieves the thing attributes (site_id, tenant_id, customer_id) using boto3.
    
    Returns:
        dict: Dictionary containing the thing attributes, or None if failed.
    """
    temp_creds = fetch_temporary_credentials()
    if not temp_creds:
        print("Cannot retrieve thing attributes due to failure in fetching temporary credentials.")
        return None

    iot_client = boto3.client(
        'iot',
        region_name=REGION,
        aws_access_key_id=temp_creds["access_key"],
        aws_secret_access_key=temp_creds["secret_key"],
        aws_session_token=temp_creds["session_token"]
    )

    try:
        response = iot_client.describe_thing(thingName=client_id)
        attributes = response.get('attributes', {})
        print("Retrieved thing attributes:", attributes)
        return attributes
    except Exception as e:
        print("Failed to retrieve thing attributes:", str(e))
        return None

def update_device_shadow(attributes):
    """
    Updates the Device Shadow with the thing attributes (site_id, tenant_id, customer_id).
    
    Args:
        attributes: Dictionary containing the thing attributes.
    """
    temp_creds = fetch_temporary_credentials()
    if not temp_creds:
        print("Cannot update Device Shadow due to failure in fetching temporary credentials.")
        return

    iot_data_client = boto3.client(
        'iot-data',
        region_name=REGION,
        aws_access_key_id=temp_creds["access_key"],
        aws_secret_access_key=temp_creds["secret_key"],
        aws_session_token=temp_creds["session_token"]
    )

    # Construct the shadow payload using the thing attributes
    shadow_payload = {
        "state": {
            "desired": {
                "site_id": attributes.get('site_id', 'unknown_site'),
                "tenant_id": attributes.get('tenant_id', 'unknown_tenant'),
                "customer_id": attributes.get('customer_id', 'unknown_customer')
            }
        }
    }

    try:
        response = iot_data_client.update_thing_shadow(
            thingName=client_id,
            payload=json.dumps(shadow_payload).encode('utf-8')
        )
        print("Successfully updated Device Shadow with attributes:", shadow_payload["state"]["desired"])
    except Exception as e:
        print("Failed to update Device Shadow:", str(e))

def post_provisioning():
    """
    Performs post-provisioning steps after successful provisioning:
    - Reconnects using the new device certificate.
    - Retrieves thing attributes (site_id, tenant_id, customer_id) using boto3.
    - Updates the Device Shadow with the retrieved attributes.
    """
    print("Reconnecting with new device certificate...")
    
    # Retrieve thing attributes
    attributes = get_thing_attributes()
    config.update(attributes)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent = 4)
    if attributes:
        # Update the Device Shadow with the attributes
        update_device_shadow(attributes)
    else:
        print("Skipping Device Shadow update due to failure in retrieving attributes.")
        
# ----------------------
# Wait Functions
# ----------------------
def waitForCreateKeysAndCertificateResponse():
    """
    Waits for the CreateKeysAndCertificate response from AWS IoT Core.
    This response contains the new device certificate and keys.
    
    Raises:
        Exception: If the response isn’t received within the timeout.
    """
    loopCount = 0
    while loopCount < 20 and createKeysAndCertificateResponse is None:
        print('Waiting for CreateKeysAndCertificateResponse...')
        loopCount += 1
        time.sleep(1)
    if createKeysAndCertificateResponse is None:
        raise Exception('CreateKeysAndCertificate API did not succeed')

def waitForRegisterThingResponse():
    """
    Waits for the RegisterThing response from AWS IoT Core and proceeds to post-provisioning.
    This response confirms that the device has been provisioned as a thing.
    
    Raises:
        Exception: If the response isn’t received within the timeout.
    """
    loopCount = 0
    while loopCount < 20 and registerThingResponse is None:
        print('Waiting for RegisterThingResponse...')
        loopCount += 1
        time.sleep(1)
    if registerThingResponse is None:
        raise Exception('RegisterThing API did not succeed')
    post_provisioning()

# ----------------------
# Main Execution
# ----------------------
if __name__ == '__main__':
    # Create a MQTT connection using the shared claim certificate
    mqtt5_client = mqtt5_client_builder.mtls_from_path(
        endpoint=ENDPOINT,
        port=8883,
        cert_filepath=CLAIM_CERT_PATH,
        pri_key_filepath=CLAIM_KEY_PATH,
        ca_filepath=ROOT_CA_PATH,
        client_id=client_id,
        clean_session=False,
        keep_alive_secs=30,
        on_lifecycle_connection_success=on_lifecycle_connection_success,
        on_lifecycle_stopped=on_lifecycle_stopped)

    print(f"Connecting to {ENDPOINT} with client ID '{client_id}'...")

    # Start the MQTT5 client
    mqtt5_client.start()

    # Create an identity client for Fleet Provisioning operations
    identity_client = iotidentity.IotIdentityClient(mqtt5_client)

    # Wait for connection to be fully established
    future_connection_success.result()
    print("Connected!")

    try:
        # Subscribe to necessary topics
        # These subscriptions handle the responses for CreateKeysAndCertificate and RegisterThing requests
        createkeysandcertificate_subscription_request = iotidentity.CreateKeysAndCertificateSubscriptionRequest()

        print("Subscribing to CreateKeysAndCertificate Accepted topic...")
        createkeysandcertificate_subscribed_accepted_future, _ = identity_client.subscribe_to_create_keys_and_certificate_accepted(
            request=createkeysandcertificate_subscription_request,
            qos=mqtt5.QoS.AT_LEAST_ONCE,
            callback=createkeysandcertificate_execution_accepted)

        createkeysandcertificate_subscribed_accepted_future.result()

        print("Subscribing to CreateKeysAndCertificate Rejected topic...")
        createkeysandcertificate_subscribed_rejected_future, _ = identity_client.subscribe_to_create_keys_and_certificate_rejected(
            request=createkeysandcertificate_subscription_request,
            qos=mqtt5.QoS.AT_LEAST_ONCE,
            callback=createkeysandcertificate_execution_rejected)

        createkeysandcertificate_subscribed_rejected_future.result()

        registerthing_subscription_request = iotidentity.RegisterThingSubscriptionRequest(
            template_name=TEMPLATE_NAME)

        print("Subscribing to RegisterThing Accepted topic...")
        registerthing_subscribed_accepted_future, _ = identity_client.subscribe_to_register_thing_accepted(
            request=registerthing_subscription_request,
            qos=mqtt5.QoS.AT_LEAST_ONCE,
            callback=registerthing_execution_accepted)

        registerthing_subscribed_accepted_future.result()

        print("Subscribing to RegisterThing Rejected topic...")
        registerthing_subscribed_rejected_future, _ = identity_client.subscribe_to_register_thing_rejected(
            request=registerthing_subscription_request,
            qos=mqtt5.QoS.AT_LEAST_ONCE,
            callback=registerthing_execution_rejected)

        registerthing_subscribed_rejected_future.result()

        # Publish CreateKeysAndCertificate request to generate a new certificate and keys
        print("Publishing to CreateKeysAndCertificate...")
        publish_future = identity_client.publish_create_keys_and_certificate(
            request=iotidentity.CreateKeysAndCertificateRequest(),
            qos=mqtt5.QoS.AT_LEAST_ONCE
        )
        publish_future.add_done_callback(on_publish_create_keys_and_certificate)

        # Wait for the CreateKeysAndCertificate response
        waitForCreateKeysAndCertificateResponse()

        if createKeysAndCertificateResponse is None:
            raise Exception('CreateKeysAndCertificate API did not succeed')

        # Create the RegisterThing request to provision the device as a thing
        registerThingRequest = iotidentity.RegisterThingRequest(
            template_name=TEMPLATE_NAME,
            certificate_ownership_token=createKeysAndCertificateResponse.certificate_ownership_token,
            parameters={"SerialNumber": client_id}
        )
        
        print("Publishing to RegisterThing topic...")
        registerthing_publish_future = identity_client.publish_register_thing(
            request=registerThingRequest,
            qos=mqtt5.QoS.AT_LEAST_ONCE
        )
        registerthing_publish_future.add_done_callback(on_publish_register_thing)

        
        waitForRegisterThingResponse()
        exit("success")
       
    except Exception as e:
        exit(e)

    # Wait for the sample to finish
    is_sample_done.wait()