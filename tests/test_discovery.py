"""Unit-tests for the Swidget discovery module."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from swidget.discovery import _get_device_class, discover_devices, discover_single
from swidget.exceptions import SwidgetException
from swidget.swidgetdevice import DeviceType
from swidget.swidgetdimmer import SwidgetDimmer
from swidget.swidgetoutlet import SwidgetOutlet
from swidget.swidgetswitch import SwidgetSwitch
from swidget.swidgettimerswitch import SwidgetTimerSwitch


@pytest.fixture
def mock_response_headers():
    """Mock response headers for SSDP packet."""
    return [
        ("USN", "uuid:1234"),
        ("LOCATION", "http://192.168.1.100"),
        ("ST", "urn:swidget:pico:1"),
        ("SERVER", "SwidgetSwitch+Outlet/1.0"),
    ]


async def test_discover_devices_empty(mocker):
    """Basic empty discovery test."""
    # Mock asyncio.sleep to avoid actual sleep during test
    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    # Mock ssdp.SimpleServiceDiscoveryProtocol methods
    protocol_mock = AsyncMock()
    protocol_mock.response_received = AsyncMock()
    mocker.patch("swidget.discovery.SwidgetProtocol", return_value=protocol_mock)

    # Mock transport creation to avoid real sockets
    dummy_transport = mocker.MagicMock()
    mocker.patch.object(
        asyncio.get_event_loop(),
        "create_datagram_endpoint",
        AsyncMock(return_value=(dummy_transport, protocol_mock)),
    )

    # Run the discovery
    await discover_devices()

    # Assert no calls were made to response_received indicating no devices found
    assert not protocol_mock.response_received.called


def test_get_device_class():
    """Tests for DeviceType to device class."""
    assert _get_device_class(DeviceType.Outlet) == SwidgetOutlet
    assert _get_device_class(DeviceType.Switch) == SwidgetSwitch
    assert _get_device_class(DeviceType.Dimmer) == SwidgetDimmer
    assert _get_device_class(DeviceType.TimerSwitch) == SwidgetTimerSwitch
    assert _get_device_class(DeviceType.RelaySwitch) == SwidgetSwitch
    with pytest.raises(SwidgetException):
        _get_device_class("UnknownDeviceType")


@pytest.mark.asyncio
@patch("swidget.discovery.SwidgetDevice", autospec=True)
async def test_discover_single_outlet(MockSwidgetDevice):
    """Test for basic manual discovery of an outlet device."""
    mock_device = MockSwidgetDevice.return_value
    mock_device.device_type = DeviceType.Outlet

    device = await discover_single("192.168.1.2", "token", "password", True, False)

    MockSwidgetDevice.assert_called_once_with(
        "192.168.1.2", "token", "password", True, use_websockets=False
    )
    mock_device.get_summary.assert_awaited_once()
    mock_device.stop.assert_awaited_once()

    assert isinstance(device, SwidgetOutlet)


@pytest.mark.asyncio
@patch("swidget.discovery.SwidgetDevice", autospec=True)
async def test_discover_single_switch(MockSwidgetDevice):
    """Test for basic manual discovery of a switch device."""
    mock_device = MockSwidgetDevice.return_value
    mock_device.device_type = DeviceType.Switch

    device = await discover_single("192.168.1.3", "token", "password", True, False)

    MockSwidgetDevice.assert_called_once_with(
        "192.168.1.3", "token", "password", True, use_websockets=False
    )
    mock_device.get_summary.assert_awaited_once()
    mock_device.stop.assert_awaited_once()

    assert isinstance(device, SwidgetSwitch)


@pytest.mark.asyncio
@patch("swidget.discovery.SwidgetDevice", autospec=True)
async def test_discover_single_dimmer(MockSwidgetDevice):
    """Test for basic manual discovery of a dimmer device."""
    mock_device = MockSwidgetDevice.return_value
    mock_device.device_type = DeviceType.Dimmer

    device = await discover_single("192.168.1.4", "token", "password", True, False)

    MockSwidgetDevice.assert_called_once_with(
        "192.168.1.4", "token", "password", True, use_websockets=False
    )
    mock_device.get_summary.assert_awaited_once()
    mock_device.stop.assert_awaited_once()

    assert isinstance(device, SwidgetDimmer)


@pytest.mark.asyncio
@patch("swidget.discovery.SwidgetDevice", autospec=True)
async def test_discover_single_timer_switch(MockSwidgetDevice):
    """Test for basic manual discovery of a timer device."""
    mock_device = MockSwidgetDevice.return_value
    mock_device.device_type = DeviceType.TimerSwitch

    device = await discover_single("192.168.1.5", "token", "password", True, False)

    MockSwidgetDevice.assert_called_once_with(
        "192.168.1.5", "token", "password", True, use_websockets=False
    )
    mock_device.get_summary.assert_awaited_once()
    mock_device.stop.assert_awaited_once()

    assert isinstance(device, SwidgetTimerSwitch)


@pytest.mark.asyncio
@patch("swidget.discovery.SwidgetDevice", autospec=True)
async def test_discover_single_unknown_device(MockSwidgetDevice):
    """Test for error condition when it's not possible to work out the type of device."""
    mock_device = MockSwidgetDevice.return_value
    mock_device.device_type = "UnknownDevice"

    with pytest.raises(SwidgetException):
        await discover_single("192.168.1.6", "token", "password", True, False)

    MockSwidgetDevice.assert_called_once_with(
        "192.168.1.6", "token", "password", True, use_websockets=False
    )
    mock_device.get_summary.assert_awaited_once()
    mock_device.stop.assert_awaited_once()
