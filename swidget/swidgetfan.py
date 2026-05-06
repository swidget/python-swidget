"""Module for SwidgetFan.

Covers the Pesna* host family (Panasonic FV05/FV15/FV20/IB150/IB160 and
G5/error/unrecognised variants). All variants share the same request
surface; per-model differences (max CFM, available modes, module
slots) are reported by the device itself in the summary/datapoint.

Function tags (``exhaust``, ``supply``, ``mode``, ``speed``, ``boost``,
``timer``, ``light``, ``dutyCycle``, ``filter``, ``raw``) and their
request/response shapes are documented in
``swidget-sdk/docs/request_handling.md`` (§"Fan-only host functions")
and ``swidget-sdk/docs/datapoint_description.md`` (§"Fan-only
functions"). This class is a thin wrapper around those — it does not
re-validate the device's capability set; callers should consult
``component.functions`` (populated from the summary) before invoking a
function the host doesn't expose.
"""
import logging
from typing import Any, Dict, List, Optional

from swidget.exceptions import SwidgetException
from swidget.swidgetdevice import DeviceType, SwidgetDevice

_LOGGER = logging.getLogger(__name__)


_FAN_FUNCTION_TAGS = frozenset(
    {
        "exhaust",
        "supply",
        "mode",
        "speed",
        "boost",
        "timer",
        "light",
        "dutyCycle",
        "filter",
        "indoors",
        "outdoors",
        "balancing",
        "modules",
        "error",
        "status",
        "raw",
    }
)


class SwidgetFan(SwidgetDevice):
    """Representation of a Swidget Fan-controller host (Pesna* family)."""

    def __init__(
        self,
        host,
        token_name: str,
        secret_key: str,
        use_https: bool,
        use_websockets: bool,
    ) -> None:
        super().__init__(
            host=host,
            token_name=token_name,
            secret_key=secret_key,
            use_https=use_https,
            use_websockets=use_websockets,
        )
        # Provisional. The real type is overwritten when the summary
        # arrives — at which point we'll know the exact Pesna* variant.
        self.device_type = DeviceType.PesnaUnrecognized

    # ---- component lookup ------------------------------------------------

    @property
    def fan_component_id(self) -> str:
        """Return the host component id that exposes fan functions.

        Pesna hosts typically expose a single component (``"0"``) but
        the SDK leaves room for multi-component fan controllers, so we
        scan rather than hardcoding.
        """
        host = self.assemblies.get("host")
        if host is None:
            raise SwidgetException("Host assembly not loaded yet.")
        for component_id, component in host.components.items():
            if any(fn in _FAN_FUNCTION_TAGS for fn in component.functions):
                return component_id
        raise SwidgetException("No fan-capable host component found.")

    def _function(self, name: str) -> Any:
        """Return the current value of a host function, or ``None``."""
        host = self.assemblies.get("host")
        if host is None:
            return None
        component = host.components.get(self.fan_component_id)
        if component is None:
            return None
        return component.functions.get(name)

    # ---- read-only properties -------------------------------------------

    @property
    def max_cfm(self) -> Optional[int]:
        """Maximum CFM the device hardware supports, from the summary."""
        host = self.assemblies.get("host")
        if host is None:
            return None
        component = host.components.get(self.fan_component_id)
        return getattr(component, "max_cfm", None) if component else None

    @property
    def model_code(self) -> Optional[str]:
        """Hardware-reported fan model code, from the summary."""
        host = self.assemblies.get("host")
        if host is None:
            return None
        component = host.components.get(self.fan_component_id)
        return getattr(component, "model_code", None) if component else None

    @property
    def detected_modules(self) -> List[str]:
        """Add-on modules detected at summary time (``condensation``, etc.)."""
        host = self.assemblies.get("host")
        if host is None:
            return []
        component = host.components.get(self.fan_component_id)
        return list(getattr(component, "modules", []) or []) if component else []

    @property
    def exhaust_cfm(self) -> Optional[int]:
        value = self._function("exhaust")
        return value.get("cfm") if isinstance(value, dict) else None

    @property
    def supply_cfm(self) -> Optional[int]:
        value = self._function("supply")
        return value.get("cfm") if isinstance(value, dict) else None

    @property
    def allowed_exhaust_cfms(self) -> Optional[List[int]]:
        """Discrete CFM values the exhaust accepts, or ``None`` if unavailable."""
        return self._allowed_cfms("exhaust")

    @property
    def allowed_supply_cfms(self) -> Optional[List[int]]:
        return self._allowed_cfms("supply")

    def _allowed_cfms(self, tag: str) -> Optional[List[int]]:
        value = self._function(tag)
        if not isinstance(value, dict):
            return None
        allowed = value.get("allowed")
        # Per the SDK doc, ``allowed`` may be the literal string
        # ``"unavailable"`` instead of a list — treat that as "unknown".
        if isinstance(allowed, list):
            return list(allowed)
        return None

    @property
    def mode(self) -> Optional[str]:
        value = self._function("mode")
        return value if isinstance(value, str) else None

    @property
    def status(self) -> Optional[str]:
        value = self._function("status")
        return value if isinstance(value, str) else None

    @property
    def speed(self) -> Optional[str]:
        value = self._function("speed")
        return value if isinstance(value, str) else None

    @property
    def boost_state(self) -> Optional[Dict[str, Any]]:
        value = self._function("boost")
        return dict(value) if isinstance(value, dict) else None

    @property
    def fan_timer_minutes(self) -> Optional[int]:
        """Minutes remaining on the fan timer; ``None`` when no timer is active."""
        value = self._function("timer")
        if not isinstance(value, dict):
            return None
        return value.get("minutes")

    @property
    def light_on(self) -> Optional[bool]:
        value = self._function("light")
        return value.get("on") if isinstance(value, dict) else None

    @property
    def duty_cycle_minutes(self) -> Optional[int]:
        value = self._function("dutyCycle")
        return value.get("minutes") if isinstance(value, dict) else None

    @property
    def error_code(self) -> Optional[str]:
        value = self._function("error")
        return value.get("code") if isinstance(value, dict) else None

    @property
    def filter_state(self) -> Optional[Dict[str, bool]]:
        value = self._function("filter")
        return dict(value) if isinstance(value, dict) else None

    @property
    def indoor_climate(self) -> Optional[Dict[str, float]]:
        value = self._function("indoors")
        return dict(value) if isinstance(value, dict) else None

    @property
    def outdoor_climate(self) -> Optional[Dict[str, float]]:
        value = self._function("outdoors")
        return dict(value) if isinstance(value, dict) else None

    @property
    def balancing_offset(self) -> Optional[int]:
        value = self._function("balancing")
        return value.get("offset") if isinstance(value, dict) else None

    @property
    def module_states(self) -> Dict[str, str]:
        """Live ``triggered``/``dormant`` state for each fan add-on module."""
        value = self._function("modules")
        return dict(value) if isinstance(value, dict) else {}

    # ---- commands -------------------------------------------------------

    async def set_exhaust_cfm(self, cfm: int) -> None:
        await self._send_fan_command("exhaust", {"cfm": int(cfm)})

    async def set_supply_cfm(self, cfm: int) -> None:
        await self._send_fan_command("supply", {"cfm": int(cfm)})

    async def set_mode(self, mode: str) -> None:
        await self._send_fan_command("mode", {"mode": mode})

    async def set_speed(self, speed: str) -> None:
        # ``speed`` requests are a bare string per request_handling.md,
        # but ``send_command`` always wraps the payload, so the device's
        # request envelope ends up as ``{ "speed": "<str>" }`` either
        # way (we send the value unwrapped to match).
        await self._send_fan_command("speed", speed)

    async def set_boost(
        self, mode: str, minutes: Optional[int] = None
    ) -> None:
        """Configure boost. ``mode`` is one of ``"off"``, ``"timer"``, ``"on"``."""
        payload: Dict[str, Any] = {"mode": mode}
        if minutes is not None:
            payload["minutes"] = int(minutes)
        await self._send_fan_command("boost", payload)

    async def set_fan_timer(self, minutes: int) -> None:
        await self._send_fan_command("timer", {"minutes": int(minutes)})

    async def set_light(self, on: bool) -> None:
        await self._send_fan_command("light", {"on": bool(on)})

    async def set_duty_cycle(self, minutes: int) -> None:
        await self._send_fan_command("dutyCycle", {"minutes": int(minutes)})

    async def clean_filter(self) -> None:
        await self._send_fan_command("filter", {"clean": True})

    async def send_raw(self, cmd: str) -> None:
        """Send a raw passthrough command. Diagnostic only."""
        await self._send_fan_command("raw", {"cmd": cmd})

    async def _send_fan_command(self, function: str, command: Any) -> None:
        await self.send_command(
            assembly="host",
            component=self.fan_component_id,
            function=function,
            command=command,
        )
