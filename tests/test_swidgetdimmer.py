"""Tests for the SwidgetDimmer class."""
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from swidget.exceptions import SwidgetException
from swidget.swidgetdevice import DeviceType
from swidget.swidgetdimmer import SwidgetDimmer


@pytest.mark.asyncio
async def test_swidget_dimmer_initialization():
    """Test the creation of a dimmer device type."""
    dimmer = SwidgetDimmer(
        "127.0.0.1", "token_name", "secret_key", use_https=True, use_websockets=True
    )
    assert dimmer._device_type == DeviceType.Dimmer


@pytest.mark.asyncio
async def test_swidget_dimmer_brightness():
    """Check dimmer brightness functionality."""
    dimmer = SwidgetDimmer(
        "127.0.0.1", "token_name", "secret_key", use_https=True, use_websockets=True
    )
    dimmer.assemblies = {
        "host": {
            "components": {"0": {"functions": {"level": {"now": 50, "default": 100}}}}
        }
    }

    assert dimmer.brightness == 50

    # Test KeyError fallback
    del dimmer.assemblies["host"]["components"]["0"]["functions"]["level"]["now"]
    assert dimmer.brightness == 100

    # Test SwidgetException when not dimmable
    with patch.object(
        SwidgetDimmer, "is_dimmable", new_callable=PropertyMock
    ) as mock_is_dimmable:
        mock_is_dimmable.return_value = False
        with pytest.raises(SwidgetException):
            _ = dimmer.brightness


@pytest.mark.asyncio
async def test_swidget_dimmer_set_brightness():
    """Test setting brightness of the dummer."""
    dimmer = SwidgetDimmer(
        "127.0.0.1", "token_name", "secret_key", use_https=True, use_websockets=True
    )
    dimmer.assemblies = {
        "host": {"components": {"0": {"functions": {"level": {"now": 50}}}}}
    }

    with patch.object(
        dimmer, "send_command", new_callable=AsyncMock
    ) as mock_send_command:
        await dimmer.set_brightness(75)
        assert (
            dimmer.assemblies["host"]["components"]["0"]["functions"]["level"]["now"]
            == 75
        )
        mock_send_command.assert_awaited_once_with(
            assembly="host", component="0", function="level", command={"now": 75}
        )


@pytest.mark.asyncio
async def test_swidget_dimmer_set_default_brightness():
    """Test dimmer default brightness functionality."""
    dimmer = SwidgetDimmer(
        "127.0.0.1", "token_name", "secret_key", use_https=True, use_websockets=True
    )

    with patch.object(
        dimmer, "send_command", new_callable=AsyncMock
    ) as mock_send_command:
        await dimmer.set_default_brightness(60)
        mock_send_command.assert_awaited_once_with(
            assembly="host", component="0", function="level", command={"default": 60}
        )


@pytest.mark.asyncio
async def test_swidget_dimmer_is_dimmable():
    """Test dimmer is dimmable."""
    dimmer = SwidgetDimmer(
        "127.0.0.1", "token_name", "secret_key", use_https=True, use_websockets=True
    )
    assert dimmer.is_dimmable is True
