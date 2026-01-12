"""Tests for the provision module."""
from unittest.mock import MagicMock, patch

from swidget.provision import provision_wifi, send_credentials, verify_connect_result


@patch("swidget.provision.requests.post")
def test_send_credentials_success(mock_post):
    """Test the successful send of WiFi credentials."""
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"secretKey": "dummy_secret_key"}

    device_name = "device1"
    ssid = "wifi_ssid"
    network_password = "wifi_password"
    secret_key = "dummy_secret_key"

    success, key = send_credentials(device_name, ssid, network_password, secret_key)

    assert success is True
    assert key == "dummy_secret_key"


@patch("swidget.provision.requests.post")
def test_send_credentials_failure(mock_post):
    """Test the successful send of WiFi credentials."""
    mock_post.return_value.status_code = 500
    mock_post.return_value.json.return_value = {"error": "Internal server error"}

    device_name = "device1"
    ssid = "wifi_ssid"
    network_password = "wifi_password"
    secret_key = "dummy_secret_key"

    success, key = send_credentials(device_name, ssid, network_password, secret_key)

    assert success is False
    assert key is None


@patch("swidget.provision.time.sleep", return_value=None)
@patch("swidget.provision.requests.get")
def test_verify_connect_result_success(mock_get, mock_sleep):
    """Test successful provision."""
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "status": "Success",
        "ip": "192.168.1.100",
        "mac": "00:11:22:33:44:55",
    }

    key = "dummy_secret_key"

    success, ip, mac, error_message = verify_connect_result(key)

    assert success is True
    assert ip == "192.168.1.100"
    assert mac == "00:11:22:33:44:55"
    assert error_message is None


@patch("swidget.provision.time.sleep", return_value=None)
@patch("swidget.provision.requests.get")
def test_verify_connect_result_failure(mock_get, mock_sleep):
    """Test failed provision."""
    mock_get.return_value.status_code = 500
    mock_get.return_value.json.return_value = {"error": "Internal server error"}

    key = "dummy_secret_key"

    success, ip, mac, error_message = verify_connect_result(key)

    assert success is False
    assert ip is None
    assert mac is None
    assert error_message == "Internal server error"


@patch("swidget.provision.time.sleep", return_value=None)
@patch("swidget.provision.requests.get")
@patch("swidget.provision.requests.post")
def test_provision_wifi_success(mock_post, mock_get, mock_sleep):
    """Test extended provision."""
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"secretKey": "dummy_secret_key"}

    # Mock response objects for the side effects
    response_in_progress = MagicMock()
    response_in_progress.status_code = 200
    response_in_progress.json.return_value = {"status": "InProgress"}

    response_success = MagicMock()
    response_success.status_code = 200
    response_success.json.return_value = {
        "status": "Success",
        "ip": "192.168.1.100",
        "mac": "00:11:22:33:44:55",
    }

    response_setup_complete = MagicMock()
    response_setup_complete.status_code = 200
    response_setup_complete.json.return_value = {"status": "Success"}

    response_get_name = MagicMock()
    response_get_name.status_code = 200
    response_get_name.json.return_value = {"device_name": "device1"}

    # Mocking the sequence of get requests
    # Simulate multiple "InProgress" responses before a "Success"
    mock_get.side_effect = [
        response_in_progress,
        response_in_progress,
        response_in_progress,
        response_in_progress,
        response_success,
        response_setup_complete,
        response_get_name,
    ]

    device_name = "device1"
    ssid = "wifi_ssid"
    network_password = "wifi_password"
    secret_key = "dummy_secret_key"

    assert provision_wifi(device_name, ssid, network_password, secret_key) is True


@patch("swidget.provision.time.sleep", return_value=None)
@patch("swidget.provision.requests.get")
@patch("swidget.provision.requests.post")
def test_provision_wifi_failure(mock_post, mock_get, mock_sleep):
    """Test failed provision."""
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"secretKey": "dummy_secret_key"}

    mock_get.return_value.status_code = 500
    mock_get.return_value.json.return_value = {"error": "Internal server error"}

    device_name = "device1"
    ssid = "wifi_ssid"
    network_password = "wifi_password"
    secret_key = "dummy_secret_key"

    assert provision_wifi(device_name, ssid, network_password, secret_key) is False
