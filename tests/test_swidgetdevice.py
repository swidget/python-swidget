"""Tests for the SwidgetDevice class."""
import pytest
from aioresponses import aioresponses

from swidget.swidgetdevice import (
    DeviceConfiguration,
    DeviceType,
    InsertType,
    SwidgetDevice,
)

# Sample data for testing
sample_summary = {
    "model": "SwidgetModel",
    "mac": "00:11:22:33:44:55",
    "version": "1.0",
    "host": {
        "type": "switch",
        "components": [{"id": "0", "functions": ["toggle", "power"]}],
    },
    "insert": {"type": "USB", "components": [{"id": "usb", "functions": ["toggle"]}]},
}

sample_state = {
    "connection": {"rssi": -60},
    "host": {"components": {"0": {"toggle": {"state": "off"}}}},
    "insert": {"components": {"usb": {"toggle": {"state": "off"}}}},
}


def test_initialization():
    """Test SwidgetDevice __init__() function."""
    device = SwidgetDevice(
        "127.0.0.1", "token_name", "secret_key", use_https=True, use_websockets=True
    )
    assert device.ip_address == "127.0.0.1"
    assert device.token_name == "token_name"
    assert device.secret_key == "secret_key"
    assert device.use_https is True
    assert device.use_websockets is True


@pytest.mark.asyncio
async def test_get_summary():
    """Test summary device information."""
    device = SwidgetDevice(
        "127.0.0.1", "token_name", "secret_key", use_https=True, use_websockets=False
    )
    with aioresponses() as m:
        m.get("https://127.0.0.1/api/v1/summary", payload=sample_summary)
        await device.get_summary()
        assert device.model == "SwidgetModel"
        assert device.mac_address == "00:11:22:33:44:55"
        assert device.version == "1.0"
        assert device.device_type == DeviceType.Switch
        assert device.insert_type == InsertType.USB


@pytest.fixture
def sample_config():
    """Fixture for testing device configuration."""
    return {
        "access": {"device_key": "none", "site_key": "none", "user_key": "none"},
        "configServer": {"debugEnabled": True},
        "host": {"components": {"0": {"log_rate": 300000, "maxBrightness": 80}}},
        "insert": {"components": {"video": {"motion": {"sensitivity": 100}}}},
        "l_ctrl": {"name": "Swidget Video"},
    }


def test_update_config(sample_config):
    """Test updating device configuration."""
    # Create a DeviceConfiguration instance with the sample configuration
    device_config = DeviceConfiguration(sample_config)

    # Update the log rate for component '0'
    device_config.update_config({"host.components.0.log_rate": 600000})

    # Update the max brightness for component '0'
    device_config.update_config({"host.components.0.maxBrightness": 90})

    # Update the sensitivity for video motion
    device_config.update_config({"insert.components.video.motion.sensitivity": 50})

    # Get the updated configuration
    updated_config = device_config.config

    # Assert that the updated values are correct
    assert updated_config["host"]["components"]["0"]["log_rate"] == 600000
    assert updated_config["host"]["components"]["0"]["maxBrightness"] == 90
    assert (
        updated_config["insert"]["components"]["video"]["motion"]["sensitivity"] == 50
    )


def test_update_config_multiple(sample_config):
    """Test updating multiple configuration properties."""
    # Create a DeviceConfiguration instance with the sample configuration
    device_config = DeviceConfiguration(sample_config)

    # Update multiple configurations at once
    device_config.update_config(
        {
            "host.components.0.log_rate": 600000,
            "host.components.0.maxBrightness": 90,
            "insert.components.video.motion.sensitivity": 50,
        }
    )

    # Get the updated configuration
    updated_config = device_config.config

    # Assert that the updated values are correct
    assert updated_config["host"]["components"]["0"]["log_rate"] == 600000
    assert updated_config["host"]["components"]["0"]["maxBrightness"] == 90
    assert (
        updated_config["insert"]["components"]["video"]["motion"]["sensitivity"] == 50
    )
