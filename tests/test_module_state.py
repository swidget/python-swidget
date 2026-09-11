"""Regression tests for fan module state across device summary refreshes."""

from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Any

import pytest

from swidget.swidgetdevice import SwidgetDevice


@pytest.fixture
def fan_summary() -> dict[str, Any]:
    """Mirror a fan's schema: modules are separate from function tags."""
    return {
        "request_id": "summary",
        "model": "FAN_PICO_S3",
        "mac": "001122334455",
        "version": "1.6.125",
        "host": {
            "type": "pesna_fv05",
            "id": "test-fan",
            "components": [
                {
                    "id": "0",
                    "functions": ["exhaust", "light"],
                    "modules": ["motion", "condensation"],
                }
            ],
        },
        "insert": {"type": "control", "components": []},
    }


@pytest.fixture
async def device() -> AsyncIterator[SwidgetDevice]:
    """Construct a device without connecting to a network endpoint."""
    dev = SwidgetDevice(
        "127.0.0.1", "token", "secret", use_https=False, use_websockets=False
    )
    try:
        yield dev
    finally:
        await dev.stop()


def module_state(modules: dict[str, str] | str | None) -> dict[str, Any]:
    """Build a state message containing the module datapoints."""
    return {
        "request_id": "state",
        "host": {"components": {"0": {"modules": modules}}},
        "insert": {"components": {}},
    }


@pytest.mark.parametrize("motion", ["triggered", "dormant"])
@pytest.mark.parametrize("condensation", ["triggered", "dormant"])
@pytest.mark.asyncio
async def test_summary_callback_preserves_module_readings(
    device: SwidgetDevice,
    fan_summary: dict[str, Any],
    motion: str,
    condensation: str,
) -> None:
    """Subscribers must not see missing readings between summary and state."""
    readings = {"motion": motion, "condensation": condensation}
    await device.message_callback(fan_summary)
    await device.message_callback(module_state(readings))
    observed: list[dict[str, str] | None] = []

    async def record_state(message: dict[str, Any]) -> None:
        component = device.assemblies["host"].components["0"]
        observed.append(deepcopy(component.functions.get("modules")))

    device.add_event_callback(record_state)
    for _ in range(2):
        await device.message_callback(deepcopy(fan_summary))
        await device.message_callback(module_state(readings))
    assert observed == [readings] * 4
    component = device.assemblies["host"].components["0"]
    assert component.summary_functions == ("exhaust", "light")

    changed = {"motion": "dormant" if motion == "triggered" else "triggered"}
    changed["condensation"] = "dormant" if condensation == "triggered" else "triggered"
    await device.message_callback(module_state(changed))
    await device.message_callback(deepcopy(fan_summary))
    assert observed[-2:] == [changed, changed]


@pytest.mark.parametrize(
    ("installed", "expected"),
    [
        (["motion"], {"motion": "triggered"}),
        (["condensation"], {"condensation": "dormant"}),
        (["motion", "new_sensor"], {"motion": "triggered"}),
        ([], None),
        (None, None),
    ],
)
@pytest.mark.asyncio
async def test_summary_retains_only_installed_modules(
    device: SwidgetDevice,
    fan_summary: dict[str, Any],
    installed: list[str] | None,
    expected: dict[str, str] | None,
) -> None:
    """Drop removed readings and leave newly installed sensors unknown."""
    await device.process_summary(fan_summary)
    await device.process_state(
        module_state({"motion": "triggered", "condensation": "dormant"})
    )
    component = fan_summary["host"]["components"][0]
    if installed is None:
        component.pop("modules")
    else:
        component["modules"] = installed
    await device.process_summary(fan_summary)
    assert (
        device.assemblies["host"].components["0"].functions.get("modules") == expected
    )


@pytest.mark.parametrize("readings", [None, "unavailable", {}])
@pytest.mark.asyncio
async def test_summary_does_not_invent_module_readings(
    device: SwidgetDevice,
    fan_summary: dict[str, Any],
    readings: dict[str, str] | str | None,
) -> None:
    """Missing or malformed cached state must not create sensor readings."""
    await device.process_summary(fan_summary)
    await device.process_state(module_state(readings))
    await device.process_summary(fan_summary)
    assert not device.assemblies["host"].components["0"].functions.get("modules")


@pytest.mark.parametrize("change", ["host_id", "host_type", "component"])
@pytest.mark.asyncio
async def test_summary_does_not_copy_modules_to_another_host(
    device: SwidgetDevice, fan_summary: dict[str, Any], change: str
) -> None:
    """A new host or component must wait for its own sensor state."""
    await device.process_summary(fan_summary)
    await device.process_state(module_state({"motion": "triggered"}))
    host = fan_summary["host"]
    if change == "host_id":
        host["id"] = "replacement-fan"
    elif change == "host_type":
        host["type"] = "pesna_fv15"
    else:
        host["components"][0]["id"] = "1"
    await device.process_summary(fan_summary)
    component_id = host["components"][0]["id"]
    assert "modules" not in device.assemblies["host"].components[component_id].functions


@pytest.mark.asyncio
async def test_summary_preserves_only_declared_function_state(
    device: SwidgetDevice, fan_summary: dict[str, Any]
) -> None:
    """Retaining module data must not resurrect removed function tags."""
    await device.process_summary(fan_summary)
    state = module_state({"motion": "triggered"})
    state["host"]["components"]["0"].update(
        {"exhaust": {"cfm": 150}, "light": {"on": True}}
    )
    await device.process_state(state)
    fan_summary["host"]["components"][0]["functions"] = ["exhaust", "boost"]
    await device.process_summary(fan_summary)
    functions = device.assemblies["host"].components["0"].functions
    assert functions["exhaust"] == {"cfm": 150}
    assert functions["boost"] is None
    assert "light" not in functions
    assert functions["modules"] == {"motion": "triggered"}
