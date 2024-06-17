"""Provision the Swidget device in local-only mode."""
import time
from enum import Enum

import requests  # type: ignore
import urllib3

urllib3.disable_warnings()


class DeviceConnectionResult(str, Enum):
    """Enum class for provisioning results."""

    NoStarted = ("NotInitiated",)
    InProgress = ("AttemptingConnect",)
    Success = ("Success",)
    AuthenticationFailure = ("AuthFail",)
    SSIDNotFound = ("SSIDNotFound",)
    NoIp = ("NoIpReceived",)
    ConnectionFailure = "FailedToConnect"


def send_credentials(device_name, ssid, network_password, secret_key):
    """Send the credentials to the Swidget device."""
    payload = {
        "name": device_name,
        "ssid": ssid,
        "password": network_password,
        "secretKey": secret_key,
    }
    url = "https://10.123.45.1/network"
    sentProvisionRequestAttempts = 0

    while True:
        print(f"Provision Attempt: {sentProvisionRequestAttempts}")
        if sentProvisionRequestAttempts >= 5:
            print("Provision failed, Ensure you're connected to the device's hotspot.")
            return False, None
        try:
            initial_provision = requests.post(url, json=payload, verify=False)
            if initial_provision.status_code == 200:
                print("Provision Success")
                return True, initial_provision.json()["secretKey"]
            else:
                print("Provision Failed: {initial_provision.json()}")
                return False, None
        except Exception as e:
            print("Error", e)
            time.sleep(5)
            sentProvisionRequestAttempts += 1


def verify_connect_result(key):
    """Function to query the device and verify if the device is successfully provisioned."""
    headers = {"x-secret-key": key}
    connect_verification_attempts = 0
    while connect_verification_attempts < 5:
        url = "https://10.123.45.1/network"
        try:
            verify_connection = requests.get(url, headers=headers, verify=False)
            print(f"Verify Response: {verify_connection.json()}")
            if verify_connection.status_code == 200:
                print(f"Verification request success: {verify_connection.json()}")
                connect_status = verify_connection.json()["status"]
                if connect_status == "Success":
                    return (
                        True,
                        verify_connection.json()["ip"],
                        verify_connection.json()["mac"],
                        None,
                    )
                elif connect_status == "InProgress":
                    time.sleep(5)
                    connect_verification_attempts += 1
                    continue
                else:
                    return False, None, None, connect_status
            else:
                print(f"Verification request failure: {verify_connection.json()}")
                time.sleep(5)
        except Exception as e:
            print(e)
            time.sleep(5)
        connect_verification_attempts += 1
    return False, None, None, "Internal server error"


def provision_wifi(device_name, ssid, network_password, secret_key):
    """Main function to provision credentials to the Swidget device."""
    print(f"Device_name: {device_name}")
    print(f"SSID: {ssid}")
    print("Network Password: <redacted>")
    print("Swidget Secret Key: <redacted>")

    send_success, key = send_credentials(
        device_name, ssid, network_password, secret_key
    )
    if not send_success:
        return False
    secret_key = key  # we set the key to whatever was returned from the device. this handles the case of an empty string (which causes insert to generate a key)

    verify_success, ip, mac, errorMessage = verify_connect_result(secret_key)
    if not verify_success:
        print(f"Verify Error: {errorMessage}")
        return False
    print(f"Verified Connection: {ip} {mac}")
    headers = {"x-secret-key": secret_key}
    # the device will remain in AP mode for 60 seconds before switching over to control mode. This is to allow time to send requests to update the device
    # without swiching networks.

    # issuing the setup_complete request will skip the 60s time
    complete_setup = requests.get(
        "https://10.123.45.1/setup_complete", headers=headers, verify=False
    )
    if complete_setup.status_code == 200:
        print("Setup complete, enabled control server")
    else:
        return False

    # alternatively, sleep for some time
    print("Device has been configured, switch your wifi network off `Swidget-` now")
    time.sleep(30)

    # must connect to the main network before issuing control requests
    getNameSuccess = False
    while not getNameSuccess:
        try:
            url = f"https://{ip}/api/v1/name"
            verify_name = requests.get(url, headers=headers, verify=False).json()
            print(
                f"Verifying device name has been set: {verify_name}. Provisioning complete"
            )
            return True
        except Exception:
            print("Connect to provided network")
        time.sleep(5)
