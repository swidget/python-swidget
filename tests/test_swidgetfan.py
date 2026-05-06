"""Tests for the SwidgetFan class."""
from unittest.mock import AsyncMock

import pytest

from swidget.exceptions import SwidgetException
from swidget.swidgetdevice import DeviceType, SwidgetAssembly
from swidget.swidgetfan import SwidgetFan


def _make_fan_assembly(
    *,
    component_id: str = "0",
    functions=("exhaust", "supply", "mode", "boost", "timer", "light"),
    max_cfm=110,
    code="FV05",
    modules=("condensation",),
):
    """Build a host SwidgetAssembly mirroring a real fan summary payload."""
    return SwidgetAssembly(
        {
            "type": "pesna_fv05",
            "id": "abc123",
            "components": [
                {
                    "id": component_id,
                    "functions": list(functions),
                    "maxCFM": max_cfm,
                    "code": code,
                    "modules": list(modules),
                }
            ],
        }
    )


@pytest.fixture
async def fan():
    dev = SwidgetFan(
        "127.0.0.1", "token", "secret", use_https=True, use_websockets=True
    )
    dev.assemblies = {"host": _make_fan_assembly()}
    try:
        yield dev
    finally:
        await dev.stop()


@pytest.mark.asyncio
async def test_initialization_defaults_to_unrecognized():
    """Until the summary lands the fan reports as Unrecognized — not Unknown."""
    dev = SwidgetFan(
        "127.0.0.1", "token", "secret", use_https=True, use_websockets=True
    )
    try:
        assert dev.device_type == DeviceType.PesnaUnrecognized
    finally:
        await dev.stop()


@pytest.mark.asyncio
async def test_fan_component_id_scans_for_fan_function(fan):
    """Component lookup picks the first component with a fan-only function."""
    assert fan.fan_component_id == "0"


@pytest.mark.asyncio
async def test_fan_component_id_raises_when_no_fan_component():
    dev = SwidgetFan(
        "127.0.0.1", "token", "secret", use_https=True, use_websockets=True
    )
    try:
        dev.assemblies = {
            "host": SwidgetAssembly(
                {
                    "type": "pesna_fv05",
                    "id": "abc",
                    "components": [{"id": "0", "functions": ["toggle"]}],
                }
            )
        }
        with pytest.raises(SwidgetException):
            _ = dev.fan_component_id
    finally:
        await dev.stop()


@pytest.mark.asyncio
async def test_summary_extras_exposed(fan):
    """maxCFM, code and modules from the summary surface as properties."""
    assert fan.max_cfm == 110
    assert fan.model_code == "FV05"
    assert fan.detected_modules == ["condensation"]


@pytest.mark.asyncio
async def test_read_properties_after_state_update(fan):
    """Datapoint values flow through to the read-only properties."""
    component = fan.assemblies["host"].components["0"]
    component.functions.update(
        {
            "exhaust": {"cfm": 80, "allowed": [50, 80, 110]},
            "supply": {"cfm": 50, "allowed": "unavailable"},
            "mode": "continuous",
            "boost": {"mode": "timer", "minutes": 22},
            "timer": {"minutes": 5},
            "light": {"on": True},
        }
    )

    assert fan.exhaust_cfm == 80
    assert fan.allowed_exhaust_cfms == [50, 80, 110]
    assert fan.supply_cfm == 50
    # ``"unavailable"`` is the doc-sanctioned sentinel; surface as None.
    assert fan.allowed_supply_cfms is None
    assert fan.mode == "continuous"
    assert fan.boost_state == {"mode": "timer", "minutes": 22}
    assert fan.fan_timer_minutes == 5
    assert fan.light_on is True


@pytest.mark.asyncio
async def test_read_properties_before_state_update_are_none(fan):
    """Function values are placeholders until process_state runs."""
    assert fan.exhaust_cfm is None
    assert fan.mode is None
    assert fan.fan_timer_minutes is None


@pytest.mark.asyncio
async def test_set_exhaust_cfm_sends_command(fan):
    fan.send_command = AsyncMock()
    await fan.set_exhaust_cfm(80)
    fan.send_command.assert_awaited_once_with(
        assembly="host", component="0", function="exhaust", command={"cfm": 80}
    )


@pytest.mark.asyncio
async def test_set_supply_cfm_sends_command(fan):
    fan.send_command = AsyncMock()
    await fan.set_supply_cfm(50)
    fan.send_command.assert_awaited_once_with(
        assembly="host", component="0", function="supply", command={"cfm": 50}
    )


@pytest.mark.asyncio
async def test_set_mode_sends_command(fan):
    fan.send_command = AsyncMock()
    await fan.set_mode("continuous")
    fan.send_command.assert_awaited_once_with(
        assembly="host",
        component="0",
        function="mode",
        command={"mode": "continuous"},
    )


@pytest.mark.asyncio
async def test_set_boost_with_minutes(fan):
    fan.send_command = AsyncMock()
    await fan.set_boost("timer", minutes=30)
    fan.send_command.assert_awaited_once_with(
        assembly="host",
        component="0",
        function="boost",
        command={"mode": "timer", "minutes": 30},
    )


@pytest.mark.asyncio
async def test_set_boost_off_omits_minutes(fan):
    fan.send_command = AsyncMock()
    await fan.set_boost("off")
    fan.send_command.assert_awaited_once_with(
        assembly="host",
        component="0",
        function="boost",
        command={"mode": "off"},
    )


@pytest.mark.asyncio
async def test_set_light_sends_command(fan):
    fan.send_command = AsyncMock()
    await fan.set_light(True)
    fan.send_command.assert_awaited_once_with(
        assembly="host", component="0", function="light", command={"on": True}
    )


@pytest.mark.asyncio
async def test_clean_filter_sends_command(fan):
    fan.send_command = AsyncMock()
    await fan.clean_filter()
    fan.send_command.assert_awaited_once_with(
        assembly="host", component="0", function="filter", command={"clean": True}
    )


@pytest.mark.asyncio
async def test_summary_functions_are_stable_against_state_leaks(fan):
    """Regression: process_state side-effects must not change the schema.

    Firmware emits state keys (e.g. ``modules`` on FV05) that aren't
    declared in the summary's ``functions`` array. ``process_state``
    merges those into ``functions`` for runtime convenience, which
    means ``functions.keys()`` flaps as state arrives. Anything that
    needs a stable schema fingerprint reads ``summary_functions``
    instead — assert that contract here.
    """
    component = fan.assemblies["host"].components["0"]
    declared = component.summary_functions
    assert "modules" not in declared

    component.functions.update(
        {
            "modules": {"condensation": "dormant"},
            "exhaust": {"cfm": 80, "allowed": [50, 80, 110]},
        }
    )
    # functions is now polluted with the state-only ``modules`` key,
    # but summary_functions is unchanged.
    assert "modules" in component.functions
    assert component.summary_functions == declared
