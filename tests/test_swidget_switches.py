"""Tests for Swidget outlet/switch variants."""
from unittest.mock import AsyncMock

import pytest

from swidget.exceptions import SwidgetException
from swidget.swidgetdevice import DeviceType
from swidget.swidgetoutlet import SwidgetOutlet
from swidget.swidgetswitch import SwidgetSwitch
from swidget.swidgettimerswitch import SwidgetTimerSwitch


@pytest.mark.asyncio
async def test_outlet_initialization():
    """Outlet initializes with correct device type."""
    dev = SwidgetOutlet(
        "127.0.0.1", "token", "secret", use_https=True, use_websockets=True
    )
    try:
        assert (
            dev._device_type == DeviceType.Outlet
            or dev.device_type == DeviceType.Outlet
        )
    finally:
        await dev.stop()


@pytest.mark.asyncio
async def test_outlet_on_off_commands():
    """Outlet on/off should delegate to send_command."""
    dev = SwidgetOutlet(
        "127.0.0.1", "token", "secret", use_https=True, use_websockets=True
    )
    try:
        dev.send_command = AsyncMock()
        await dev.turn_on()
        dev.send_command.assert_awaited_with(
            assembly="host", component="0", function="toggle", command={"state": "on"}
        )
        dev.send_command.reset_mock()
        await dev.turn_off()
        dev.send_command.assert_awaited_with(
            assembly="host", component="0", function="toggle", command={"state": "off"}
        )
    finally:
        await dev.stop()


@pytest.mark.asyncio
async def test_switch_on_off_commands():
    """Switch on/off delegates to send_command."""
    dev = SwidgetSwitch(
        "127.0.0.1", "token", "secret", use_https=True, use_websockets=True
    )
    try:
        dev.send_command = AsyncMock()
        await dev.turn_on()
        dev.send_command.assert_awaited_with(
            assembly="host", component="0", function="toggle", command={"state": "on"}
        )
        dev.send_command.reset_mock()
        await dev.turn_off()
        dev.send_command.assert_awaited_with(
            assembly="host", component="0", function="toggle", command={"state": "off"}
        )
    finally:
        await dev.stop()


@pytest.mark.asyncio
async def test_timer_switch_countdown_command():
    """Timer switch set_countdown_timer delegates to send_command."""
    dev = SwidgetTimerSwitch(
        "127.0.0.1", "token", "secret", use_https=True, use_websockets=True
    )
    try:
        dev.send_command = AsyncMock()
        await dev.set_countdown_timer(15)
        dev.send_command.assert_awaited_with(
            assembly="host",
            component="0",
            function="timer",
            command={"duration": 15},
        )
    finally:
        await dev.stop()


@pytest.mark.asyncio
async def test_timer_switch_initialization():
    """Timer switch initializes with correct device type marker."""
    dev = SwidgetTimerSwitch(
        "127.0.0.1", "token", "secret", use_https=True, use_websockets=True
    )
    try:
        assert (
            dev._device_type == DeviceType.TimerSwitch
            or dev.device_type == DeviceType.TimerSwitch
        )
    finally:
        await dev.stop()


@pytest.mark.asyncio
async def test_send_config_not_available_without_websockets():
    """send_config should raise when websockets are disabled."""
    dev = SwidgetSwitch(
        "127.0.0.1", "token", "secret", use_https=True, use_websockets=False
    )
    with pytest.raises(SwidgetException):
        await dev.send_config({"key": "value"})
    await dev.stop()
