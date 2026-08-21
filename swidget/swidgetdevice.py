"""Module (main-class) that represents a Swidget device."""

import json
import logging
import time
from collections.abc import Callable
from enum import Enum
from types import TracebackType
from typing import Any, Dict, List, Optional, Union

from aiohttp import ClientSession, TCPConnector
from aiohttp.client_exceptions import ClientConnectorError

from .exceptions import (
    SwidgetAuthenticationException,
    SwidgetConnectionException,
    SwidgetException,
)
from .websocket import SwidgetWebsocket

_LOGGER = logging.getLogger(__name__)


class DeviceType(Enum):
    """Device type enum.

    Values mirror the host ``type`` strings documented in
    ``swidget-sdk/docs/summary_description.md``. Add new entries here
    when firmware introduces a new host type rather than letting it
    silently resolve to ``Unknown``.
    """

    Dimmer = "dimmer"
    MultiDimmer = "multi_dimmer"
    Outlet = "outlet"
    Outlet20A = "outlet_20a"
    Switch = "switch"
    TimerSwitch = "pana_switch"
    RelaySwitch = "relay_switch"
    PesnaFV05 = "pesna_fv05"
    PesnaFV15 = "pesna_fv15"
    PesnaFV15Plus = "pesna_fv15_plus"
    PesnaFV20 = "pesna_fv20"
    PesnaIB150 = "pesna_IB150"
    PesnaIB160 = "pesna_IB160"
    PesnaFV05G5 = "pesna_fv05_G5"
    PesnaFV05WrongSlot = "pesna_fv05_wrong_slot"
    PesnaUnrecognized = "pesna_unrecognized"
    PesnaError = "pesna_error"
    Alarm = "alarm"
    XE300 = "xe300"
    MalmosetBarrel = "malmoset_barrel"
    Invalid = "invalid"
    Unknown = -1

    @classmethod
    def _missing_(cls, value: object) -> "DeviceType":
        """Map unknown values to ``Unknown`` instead of raising ValueError.

        Lets the SDK report "Unknown device type: ..." with a usable
        message rather than crashing on a future firmware variant.
        """
        return cls.Unknown


class InsertType(Enum):
    """Insert type enum.

    Values mirror the insert ``type`` strings documented in
    ``swidget-sdk/docs/summary_description.md``. Add new entries here
    when firmware introduces a new insert type rather than letting it
    silently resolve to ``Unknown``.
    """

    CONTROL = "control"
    USB = "USB"
    USB_C = "USB C"
    GL = "GUIDE LIGHT"
    ADV_GUIDE = "ADV GUIDE"
    PO = "POWER OUT"
    MOTION = "MOTION"
    AQ = "AIR QUALITY"
    TH = "TEMP HUMI"
    THM = "TEMP HUMI MOTION"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    SECURITY = "SECURITY"
    CO2 = "CO2"
    PM = "PM"
    PM_CO2 = "PM CO2"
    WD = "WATER DETECTOR"
    LIGHT_SENSOR = "LIGHT SENSOR"
    DISTANCE = "DISTANCE"
    DIRECT_LIGHTS = "DIRECT LIGHTS"
    DUAL_LV_RELAY = "DUAL LV RELAY"
    SINGLE_LV_RELAY = "SINGLE LV RELAY"
    SAS = "SAS"
    SPEAKER = "SPEAKER"
    VIDEO = "video"  # This is not a mistake.
    INVALID = "invalid"
    Unknown = -1

    @classmethod
    def _missing_(cls, value: object) -> "InsertType":
        """Map unknown values to ``Unknown`` instead of raising ValueError."""
        return cls.Unknown


class SelfDiagnosticErrorCodes(Enum):
    """Self-Diagnostic error codes."""

    UNUSED = 0
    AQ = 1
    GUIDELIGHT = 2
    LIGHT_SENSOR = 3
    MOTION = 4
    POWER_OUT = 5
    PRESSURE = 6
    TEMP = 7
    USB = 8
    VIBRATION = 9
    VIDEO = 10
    ADVANCED_GL = 11
    HUMI = 12
    CO2 = 13
    PART_MATTER = 14


def _deep_merge_dicts(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Return a new dict with ``updates`` deep-merged onto ``base``.

    Used by ``process_device_config`` so that partial-update websocket
    pushes don't wipe untouched top-level keys out of the cache. Lists
    and scalars are replaced (not concatenated) — this is a config tree,
    not an event log.
    """
    result: Dict[str, Any] = dict(base)
    for key, value in updates.items():
        existing = result.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            result[key] = _deep_merge_dicts(existing, value)
        else:
            result[key] = value
    return result


class SwidgetDevice:
    """Core representation of a Swidget device (base class for all device types)."""

    def __init__(
        self,
        host,
        token_name,
        secret_key,
        use_https=True,
        use_websockets=True,
        verify_ssl: bool = False,
    ) -> None:
        self.token_name = token_name
        self.ip_address = host
        self.use_https = use_https
        self.uri_scheme = "https" if self.use_https is True else "http"
        self.secret_key = secret_key
        self.use_websockets = use_websockets
        self.verify_ssl = verify_ssl
        self.device_type = DeviceType.Unknown
        self._friendly_name = "Unknown Swidget Device"
        self.assemblies: Dict[Any, Any] = dict()
        self.device_config: DeviceConfiguration = DeviceConfiguration({})
        self._subscribers: List[Any] = list()
        headers = {self.token_name: self.secret_key, "Connection": "keep-alive"}
        # aiohttp recommends using ssl context; verify_ssl is deprecated.
        ssl_flag = verify_ssl if use_https else False
        connector = TCPConnector(ssl=ssl_flag, force_close=True)
        if use_https is True:
            self._session = ClientSession(headers=headers, connector=connector)
        else:
            self._session = ClientSession(connector=connector)
        self._last_update: int = 0
        if self.use_websockets:
            self._websocket = SwidgetWebsocket(
                host=self.ip_address,
                token_name=self.token_name,
                secret_key=self.secret_key,
                callback=self.message_callback,
                session=self._session,
                use_security=self.use_https,
                verify_ssl=verify_ssl,
            )

    @property
    def connected(self) -> bool:
        """Property to represent if the client is connected to the device."""
        return hasattr(self, "_websocket") and self._websocket.connected

    def get_websocket(self) -> Optional[SwidgetWebsocket]:
        """Return the SwidgetWebsocket class instance if possible."""
        if self.use_websockets:
            return self._websocket
        raise RuntimeError("Swidget instance is not configured to use websockets")

    def set_countdown_timer(self, minutes) -> Any:
        """Set the countdown timer."""
        raise NotImplementedError()

    async def connect(self) -> None:
        """Create a new connection to the device."""
        await self._websocket.connect()

    async def start(self) -> None:
        """Start the websocket."""
        _LOGGER.debug("SwidgetDevice.start()")
        if self.use_websockets and not self.connected:
            _LOGGER.debug("Calling self._websocket.connect()")
            await self._websocket.connect()
        _LOGGER.debug("Calling self.update()")
        await self.update()

    async def stop(self) -> bool:
        """Stop the websocket."""
        _LOGGER.debug("SwidgetDevice.stop()")
        if hasattr(self, "_websocket"):
            try:
                await self._websocket.close()
            except Exception:
                return False
        try:
            await self._session.close()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Wrapper for the stop() function."""
        await self.stop()

    async def disconnect(self) -> None:
        """Wrapper for the stop() function."""
        await self.stop()

    def add_event_callback(self, callback: Callable[[Any], Any]) -> bool:
        """Register a function to be called when a new websocket message is recieved."""
        for c in self._subscribers:
            if c == callback:
                _LOGGER.warning(
                    "Callback has already been added, not adding the same callback function again"
                )
                return False
        self._subscribers.append(callback)
        return True

    def remove_event_callback(self, callback: Callable[[Any], Any]) -> bool:
        """Remove a registered callback function."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            return True
        return False

    async def message_callback(self, message) -> None:
        """Entrypoint for a websocket callback."""
        _LOGGER.debug("SwidgetDevice.message_callback() called")
        if message["request_id"] == "summary":
            _LOGGER.debug("Calling SwidgetDevice.process_summary()")
            await self.process_summary(message)
        elif (
            message["request_id"] == "state"
            or message["request_id"] == "DYNAMIC_UPDATE"
            or message["request_id"] == "command"
        ):
            _LOGGER.debug("Calling SwidgetDevice.process_state()")
            await self.process_state(message)
        elif message["request_id"] == "device_config":
            _LOGGER.debug("Calling SwidgetDevice.process_device_config()")
            await self.process_device_config(message)
        else:
            message_type = ["request_id"]
            _LOGGER.error(
                f"Unknown message type from websocket. Type given was: {message_type}"
            )
        await self.signal_callbacks(message)

    async def signal_callbacks(self, message) -> None:
        """Call any available registered callback functions."""
        _LOGGER.debug("SwidgetDevice.signal_callsbacks() called")
        for callback in self._subscribers:
            await callback(message)

    async def make_http_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make a generic HTTP request to a specified device endpoint.

        Args:
            method: The HTTP method to use (e.g., "GET", "POST").
            endpoint: The API endpoint to request (e.g., "summary", "state").
            params: Optional dictionary of URL query parameters.
            json_payload: Optional dictionary to send as a JSON request body.

        Returns:
            The JSON response from the device as a dictionary.

        Raises:
            SwidgetConnectionException: If there is a problem connecting.
            SwidgetAuthenticationException: If the device returns a 403 error.
            ValueError: If an unsupported HTTP method is provided.
        """
        http_method = method.upper()
        if http_method not in ("GET", "POST"):
            raise ValueError(f"Unsupported HTTP method: {http_method}")

        url = f"{self.uri_scheme}://{self.ip_address}/api/v1/{endpoint}"
        _LOGGER.debug(
            f"HTTP {http_method} {url} params={params} body={json_payload}"
        )

        try:
            async with self._session.request(
                method=http_method,
                url=url,
                params=params,
                json=json_payload,
                ssl=self.verify_ssl if self.use_https else False,
            ) as response:
                if response.status == 200:
                    if response.content_length == 0:
                        _LOGGER.debug(
                            f"HTTP {response.status} {url} (empty body)"
                        )
                        return {}
                    body = await response.json()
                    _LOGGER.debug(f"HTTP {response.status} {url} body={body}")
                    return body
                elif response.status == 403:
                    _LOGGER.error(
                        f"Authentication failed for {http_method} '{endpoint}'"
                    )
                    raise SwidgetAuthenticationException
                else:
                    _LOGGER.debug(
                        f"HTTP {response.status} {url} (non-success)"
                    )
                    response.raise_for_status()
                return {}
        except ClientConnectorError as e:
            _LOGGER.error(f"Connection error while requesting '{endpoint}': {e}")
            raise SwidgetConnectionException from e

    async def _make_passthrough_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Send a request to endpoints that are not part of the /api/v1/ namespace."""
        http_method = method.upper()
        url = f"{self.uri_scheme}://{self.ip_address}/{path.lstrip('/')}"
        request_params = dict(params or {})
        if (
            self.secret_key
            and self.token_name
            and self.token_name not in request_params
        ):
            request_params[self.token_name] = self.secret_key

        _LOGGER.debug(
            f"Sending {http_method} request to: {url} with params {request_params}"
        )

        try:
            async with self._session.request(
                method=http_method,
                url=url,
                params=request_params,
                ssl=self.verify_ssl if self.use_https else False,
            ) as response:
                if response.status == 200:
                    if response.content_length == 0:
                        return {}
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "application/json" in content_type:
                        return await response.json()
                    # Fallback: return text (e.g., ping returns plain "PONG")
                    text_body = await response.text()
                    try:
                        return json.loads(text_body)
                    except Exception:
                        return text_body
                response.raise_for_status()
                return {}
        except ClientConnectorError as e:
            _LOGGER.error(f"Connection error while requesting '{path}': {e}")
            raise SwidgetConnectionException from e

    async def get_device_config(self) -> Any:
        """Refresh the local device_config cache.

        Uses the websocket when available — the response lands on
        ``message_callback`` with ``request_id == "device_config"`` and
        ``process_device_config`` updates the cache. Falls back to HTTP
        before the socket is connected (e.g. during entry pre-load).
        """
        _LOGGER.debug("SwidgetDevice.get_device_config() called")
        if self.use_websockets and self.connected:
            _LOGGER.debug("In websocket mode. Sending get_device_config over websocket")
            await self._websocket.send_str(
                json.dumps(
                    {"type": "get_device_config", "request_id": "device_config"}
                )
            )
            return
        _LOGGER.debug("In http mode. Sending get_device_config over http")
        config = await self.make_http_request("GET", "device_config")
        await self.process_device_config(config)

    async def process_device_config(self, config) -> None:
        """Process a device_config payload from HTTP body or websocket message.

        Both transports use the same callback path, but the firmware
        pushes a *partial* websocket message after every config write
        (only the changed leaves) using the same request_id as the full
        GET response. Replacing the cache wholesale would let those
        partial pushes silently wipe every other top-level key, which
        in turn breaks every other config-driven entity in the consumer.

        Deep-merging the incoming dict into the existing cache gives the
        right behaviour for both shapes: a full GET overwrites every
        leaf (functionally a replace), and a partial push updates only
        what it touches.
        """
        _LOGGER.debug("SwidgetDevice.process_device_config() called")
        # Strip transport metadata so DeviceConfiguration sees the same
        # shape regardless of whether the payload arrived via HTTP or WS.
        cfg = {k: v for k, v in config.items() if k != "request_id"}
        existing = (
            self.device_config.config
            if self.device_config is not None and self.device_config.config_populated()
            else {}
        )
        merged = _deep_merge_dicts(existing, cfg)
        self.device_config = DeviceConfiguration(merged)
        self._last_update = int(time.time())

    async def set_device_config(self, updates: Dict[str, Any]) -> None:
        """POST a partial device_config update.

        The firmware accepts a sparse dict mirroring the full config tree
        (only the changed leaves), so callers should pass the same nested
        shape ``get_device_config()`` returns. After the POST succeeds the
        local cache is refreshed so reads see the new value immediately.

        We refresh via HTTP rather than ``get_device_config()`` because
        the websocket variant is fire-and-forget — it sends a request and
        returns before the response is delivered to ``message_callback``.
        Worse, the firmware also pushes a websocket message of the
        *changed leaves only* on every config write, and
        ``process_device_config`` replaces the cache wholesale rather
        than merging — so a partial push arriving after a full GET would
        silently wipe everything else out of the cache. The synchronous
        HTTP read here guarantees the cache is the full config when we
        return.
        """
        _LOGGER.debug("SwidgetDevice.set_device_config(%s) called", updates)
        await self.make_http_request("POST", "device_config", json_payload=updates)
        config = await self.make_http_request("GET", "device_config")
        await self.process_device_config(config)

    async def get_summary(self) -> None:
        """Get a summary of the device over HTTP."""
        _LOGGER.debug("SwidgetDevice.get_summary() called")
        if self.use_websockets:
            _LOGGER.debug(
                "In websocket mode. Sending get_summary() command over websocket"
            )
            await self._websocket.send_str(
                json.dumps({"type": "summary", "request_id": "summary"})
            )
        else:
            _LOGGER.debug("In http mode. Sending get_summary() command over http")
            summary = await self.make_http_request("GET", "summary")
            await self.process_summary(summary)

    async def process_summary(self, summary) -> None:
        """Process the data around the summary of the device."""
        _LOGGER.debug("SwidgetDevice.process_summary() called")
        _LOGGER.debug(f"Summary to process: {summary}")
        self.model = summary["model"]
        self.mac_address = summary["mac"]
        self.version = summary["version"]
        new_assemblies = {
            "host": SwidgetAssembly(summary["host"]),
            "insert": SwidgetAssembly(summary["insert"]),
        }
        # Carry already-populated function state forward. Rebuilding
        # assemblies wholesale resets every component's ``functions`` to
        # ``None`` placeholders until the next ``state`` message lands —
        # subscribers that read state in between (e.g. an HA coordinator
        # firing on the summary callback) would briefly see "unknown"
        # and flicker the UI.
        for assembly_key, new_assembly in new_assemblies.items():
            old_assembly = self.assemblies.get(assembly_key)
            if old_assembly is None:
                continue
            for component_id, new_component in new_assembly.components.items():
                old_component = old_assembly.components.get(component_id)
                if old_component is None:
                    continue
                for fn_name in new_component.functions:
                    if fn_name in old_component.functions:
                        new_component.functions[fn_name] = old_component.functions[
                            fn_name
                        ]
        self.assemblies = new_assemblies
        self.device_type = DeviceType(self.assemblies["host"].type)
        self.insert_type = InsertType(self.assemblies["insert"].type)
        self.id = self.assemblies["host"].id
        self._last_update = int(time.time())

    async def get_friendly_name(self) -> None:
        """Retrieve the friendly name of the device."""
        _LOGGER.debug("SwidgetDevice.get_friendly_name() called")
        try:
            name = await self.make_http_request("GET", "name")
        except Exception:
            name = {"name": f"Swidget {self.device_type} w/{self.insert_type} insert"}
        await self.process_friendly_name(name["name"])

    async def process_friendly_name(self, name) -> None:
        """Process the data retrieved from get_friendly_name() an set the device name."""
        _LOGGER.debug("SwidgetDevice.process_friendly_name() called")
        self._friendly_name = name
        self._last_update = int(time.time())

    async def get_state(self) -> None:
        """Get the state of the device over HTTP."""
        _LOGGER.debug("SwidgetDevice.get_state() called")
        if self.use_websockets:
            _LOGGER.debug(
                "In websocket mode. Sending get_state() command over websocket"
            )
            await self._websocket.send_str(
                json.dumps({"type": "state", "request_id": "state"})
            )
        else:
            _LOGGER.debug("In http mode. Sending get_state() command over http")
            state = await self.make_http_request("GET", "state")
            await self.process_state(state)

    async def process_state(self, state) -> None:
        """Process any information about the state of the device or insert."""
        # State is not always in the state (during callback)
        _LOGGER.debug("SwidgetDevice.process_state() called")
        _LOGGER.debug(f"State to process: {state}")
        try:
            self.rssi = state["connection"]["rssi"]
        except Exception:
            self.rssi = 0
        for assembly in self.assemblies:
            for id, component in self.assemblies[assembly].components.items():
                try:
                    component.functions.update(state[assembly]["components"][id])
                except Exception as exc:
                    # Don't fail the whole state-process loop on one bad
                    # component, but DO surface what was skipped — silent
                    # failures here are how is_on ends up reading from a
                    # never-populated None placeholder.
                    _LOGGER.debug(
                        f"process_state: skipped {assembly}/{id} "
                        f"({type(exc).__name__}: {exc})"
                    )
        self._last_update = int(time.time())

    async def update(self) -> None:
        """Refresh state and summary; device_config is fetched separately.

        device_config rarely changes, and a successful set_device_config
        already pushes a fresh copy into the local cache, so we don't
        re-fetch it on every coordinator poll.
        """
        _LOGGER.debug("SwidgetDevice.update() called")
        if self._last_update == 0:
            _LOGGER.debug("Performing the initial update to obtain sysinfo")
            await self.get_summary()
            await self.get_state()
            if self._friendly_name == "Unknown Swidget Device":
                await self.get_friendly_name()
        elif (int(time.time()) - self._last_update) < 5:
            _LOGGER.debug("update() recently called, not executing")
        else:
            _LOGGER.debug("Requesting an update of the device")
            await self.get_summary()
            await self.get_state()

    async def send_config(self, payload: dict) -> None:
        """Send a config block to the device."""
        _LOGGER.debug("SwidgetDevice.send_config() called")
        if self.use_websockets:
            _LOGGER.debug(
                "In websocket mode. Sending send_config() command over websocket"
            )
            data = json.dumps(
                {"type": "config", "request_id": "send_config", "payload": payload}
            )
            await self._websocket.send_str(data)
        else:
            raise SwidgetException(
                "Configuration management is not available via websocket."
            )

    async def send_command(
        self, assembly: str, component: str, function: str, command: Union[dict, str]
    ) -> None:
        """Send a command to the Swidget device either using a HTTP call or the existing websocket.

        ``command`` is placed verbatim under the function key. Most
        functions take an object, but a few (the Pesna fan ``mode`` and
        ``speed``) expect a bare string value.
        """
        _LOGGER.debug("SwidgetDevice.send_command() called")
        data = {assembly: {"components": {component: {function: command}}}}
        _LOGGER.debug(f"Command to send: {data}")
        if self.use_websockets and self.connected is True:
            _LOGGER.debug("In websocket mode. Sending command over websocket")
            command_data = json.dumps(
                {"type": "command", "request_id": "command", "payload": data}
            )
            await self._websocket.send_str(command_data)
        else:
            _LOGGER.debug("NOT in websocket mode, sending command over HTTP")
            response = await self.make_http_request(
                "POST", "command", json_payload=data
            )
            if response:
                try:
                    function_value = response[assembly]["components"][component][
                        function
                    ]
                    self.assemblies[assembly].components[component].functions[
                        function
                    ] = function_value
                except Exception:
                    _LOGGER.debug("Command response did not include state update")

    async def ping(self) -> bool:
        """Ping the device to ensure it's devices.

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        _LOGGER.debug("SwidgetDevice.ping() called")
        try:
            response = await self._make_passthrough_request("GET", "ping")
            _LOGGER.debug(f"Ping response: {response}")
            return True if response == {} else bool(response)
        except Exception:
            return False

    async def blink(self) -> Any:
        """Make the device LED blink.

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        _LOGGER.debug("SwidgetDevice.blink() called")
        return await self._make_passthrough_request("GET", "blink")

    async def enable_debug_server(self) -> Any:
        """Enable the Swidget local debug server.

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        _LOGGER.debug("SwidgetDevice.enable_debug_server() called")
        return await self.make_http_request("GET", "debug")

    async def restart_device(self) -> Any:
        """Restart the Swidget device.

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        return await self.make_http_request("POST", "reset")

    async def factory_reset(self) -> Any:
        """Factory reset the Swidget device.

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        try:

            async with self._session.delete(
                url=f"{self.uri_scheme}://{self.ip_address}/api/v1/reset", ssl=False
            ) as response:
                return await response.json()
        except Exception:
            raise SwidgetException

    async def check_for_updates(self) -> Any:
        """Tell the device to contact the Swidget servers to see if there is an available update.

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        try:
            newer_versions = await self.make_http_request("GET", "update")
            return sorted(newer_versions["updates"])
        except Exception:
            raise SwidgetException

    async def update_version(self, version) -> Any:
        """Tell the device to download and apply an update.

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        try:
            data = {"version": version}
            response = await self.make_http_request(
                "POST", "update/version", json_payload=data
            )
            return bool(response)
        except Exception:
            raise SwidgetException

    @property
    def hw_info(self) -> Dict:
        """
        Return hardware information.

        This returns just a selection of attributes that are related to hardware.
        """
        return {
            "version": self.version,
            "mac_address": self.mac_address,
            "type": self.device_type,
            "id": self.id,
            "model": self.model,
            "insert_type": self.insert_type,
            "insert_features": self.insert_features,
            "host_features": self.host_features,
            "rssi": self.rssi,
        }

    def get_child_consumption(self, plug_id=0) -> Any:
        """Get the power consumption of a plug in watts."""
        if plug_id == "all":
            return_dict = {}
            for id, properties in self.assemblies["host"].components.items():
                try:
                    return_dict[f"power_{id}"] = properties.functions["power"][
                        "current"
                    ]
                except KeyError:  # Hits this when there is no power metering
                    return None
            return return_dict
        return (
            self.assemblies["host"]
            .components[str(plug_id)]
            .functions["power"]["current"]
        )

    def total_consumption(self) -> float:
        """Get the total power consumption in watts."""
        total_consumption = 0
        for id, properties in self.assemblies["host"].components.items():
            total_consumption += properties.functions["power"]["current"]
        return total_consumption

    @property
    def realtime_values(self) -> Dict:
        """Get a dict of realtime value attributes from the insert and host.

        :return: A dictionary of insert sensor values and power consumption values
        :rtype: dict
        """
        return_dict = {}
        for feature in self.insert_features:
            return_dict.update(self.get_function_values(feature))
        return_dict.update({"rssi": self.rssi})
        power_values = self.get_child_consumption("all")
        if power_values:
            return_dict.update(power_values)
        return return_dict

    @property
    def host_features(self) -> List[str]:
        """Return a set of features that the host supports."""
        try:
            return list(self.assemblies["host"].components["0"].functions.keys())
        except KeyError:
            return list()

    @property
    def insert_features(self) -> List[str]:
        """Return a set of features that the insert supports."""
        try:
            return list(self.assemblies["insert"].components.keys())
        except KeyError:
            return list()

    def get_function_values(self, function: str) -> Dict:
        """Return the values of an insert function."""
        return_values = dict()
        for function, data in (
            self.assemblies["insert"].components[function].functions.items()
        ):
            if function == "occupied":
                return_values[function] = data["state"]
            elif function == "toggle":
                pass
            elif function == "pic" or function == "audio":
                pass
            elif function == "webrtc":
                return_values["webrtc_max_viewers"] = data["maxViewers"]
                return_values["webrtc_current_viewers"] = data["currentViewers"]
            elif function == "rtsp":
                pass
            elif function == "storage":
                pass
            elif function == "sd":
                return_values[function] = data["state"]
            elif function == "water":
                return_values[function] = data["state"]
            elif function == "buzzer":
                return_values[function] = data["mode"]
            else:
                return_values[function] = data["now"]
        return return_values

    def get_sensor_value(self, function, sensor) -> float | str:
        """Return the value of a sensor given a function and sensor."""
        if sensor == "occupied":
            return (
                self.assemblies["insert"]
                .components[function]
                .functions["occupied"]["state"]
            )
        else:
            return (
                self.assemblies["insert"].components[function].functions[sensor]["now"]
            )

    @property
    def available_streams_types(self) -> List[str]:
        """Return a list of the available stream device types the device supports."""
        stream_types = list()
        """Returns the available RTSP streams."""
        if InsertType.VIDEO.value in self.insert_features:
            for stream_type in (
                self.assemblies["insert"]
                .components["video"]
                .functions["rtsp"]["streams"]
                .values()
            ):
                stream_types.append(stream_type)
        return stream_types

    @property
    def stream_url(self, encoding: str = "ph264") -> str | NotImplementedError:
        """Returns the RTSP stream URL."""
        if InsertType.VIDEO.value in self.insert_features:
            return f"rtsp://{self.ip_address}:8554/{encoding}"
        raise NotImplementedError

    @property
    def snapshot_url(self) -> str | NotImplementedError:
        """Returns the URL to take a snapshot."""
        if InsertType.VIDEO.value in self.insert_features:
            return f"http://{self.ip_address}/api/v1/picture"
        raise NotImplementedError

    async def get_snapshot_bytes(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Returns a 640x360 jpeg or None if the snapshot could not be retrieved.

        :return: The image bytes or None if the snapshot could not be retrieved.
        :raises: NotImplementedError if the device does not support video.
        """
        _LOGGER.debug("SwidgetDevice.take_snapshot() called")
        if InsertType.VIDEO.value in self.insert_features:
            try:
                snapshot_url = self.snapshot_url
                headers = self._session.headers.copy()
                if width is not None and height is not None:
                    headers.update(
                        {"x-picture-width": str(width), "x-picture-height": str(height)}
                    )
                if isinstance(snapshot_url, str):
                    async with self._session.get(
                        url=snapshot_url, headers=headers, ssl=False
                    ) as response:
                        if response.status == 200:
                            return await response.read()
            except Exception as e:
                _LOGGER.error(f"Error fetching snapshot: {e}")
                return None
        raise NotImplementedError

    @property
    def is_outlet(self) -> bool:
        """Return True if the device is an outlet (any variant)."""
        return self.device_type in (DeviceType.Outlet, DeviceType.Outlet20A)

    @property
    def is_switch(self) -> bool:
        """Return True if the device is a switch."""
        return (
            self.device_type == DeviceType.Switch
            or self.device_type == DeviceType.TimerSwitch
            or self.device_type == DeviceType.RelaySwitch
        )

    @property
    def is_pana_switch(self) -> bool:
        """Return True if the device is a pana_switch."""
        return self.device_type == DeviceType.TimerSwitch

    @property
    def is_dimmer(self) -> bool:
        """Return True if the device is a dimmer."""
        return self.device_type == DeviceType.Dimmer

    @property
    def is_dimmable(self) -> bool:
        """Return  True if the device is dimmable."""
        return self.is_dimmer

    @property
    def friendly_name(self) -> str:
        """Return a friendly description of the device."""
        return self._friendly_name

    @property
    def is_on(self) -> bool:
        """Return whether device is on."""
        _LOGGER.debug("SwidgetDevice.is_on called")
        dimmer_state = (
            self.assemblies["host"].components["0"].functions["toggle"]["state"]
        )
        if dimmer_state == "on":
            return True
        return False

    async def turn_on(self) -> None:
        """Turn the device on."""
        _LOGGER.debug("SwidgetDevice.turn_on() called")
        await self.send_command(
            assembly="host", component="0", function="toggle", command={"state": "on"}
        )

    async def turn_off(self) -> None:
        """Turn the device off."""
        _LOGGER.debug("SwidgetDevice.turn_off() called")
        await self.send_command(
            assembly="host", component="0", function="toggle", command={"state": "off"}
        )

    async def turn_on_usb_insert(self) -> None:
        """Turn the USB insert on."""
        _LOGGER.debug("SwidgetDevice.turn_on_usb_insert() called")
        await self.send_command(
            assembly="insert",
            component="usb",
            function="toggle",
            command={"state": "on"},
        )

    async def turn_off_usb_insert(self) -> None:
        """Turn the USB insert off."""
        _LOGGER.debug("SwidgetDevice.turn_off_usb_insert() called")
        await self.send_command(
            assembly="insert",
            component="usb",
            function="toggle",
            command={"state": "off"},
        )

    @property
    def usb_is_on(self) -> bool:
        """Return whether USB is on."""
        _LOGGER.debug("SwidgetDevice.usb_is_on called")
        usb_state = (
            self.assemblies["insert"].components["usb"].functions["toggle"]["state"]
        )
        if usb_state == "on":
            return True
        return False

    @property
    def rtsp_enabled(self) -> Optional[bool]:
        """Return whether the video insert's RTSP server is enabled.

        Returns None when the config hasn't been fetched yet or the path
        isn't present (non-video insert, or older firmware that omits the
        key). Callers should treat None as "unknown" rather than False.
        """
        try:
            return bool(
                self.device_config.config["insert"]["components"]["video"]["rtsp"][
                    "enable"
                ]
            )
        except (KeyError, TypeError):
            return None

    async def set_rtsp_enabled(self, enabled: bool) -> None:
        """Enable or disable the video insert's RTSP server."""
        await self.set_device_config(
            {"insert": {"components": {"video": {"rtsp": {"enable": bool(enabled)}}}}}
        )

    @property
    def rtsp_stream_source(self) -> Optional[str]:
        """Return the device's RTSP URL, or None when unavailable.

        Path ``/ph264`` is fixed by firmware; the port comes from device
        config. None if RTSP is disabled, the insert isn't video, or the
        config hasn't been loaded yet.
        """
        if self.rtsp_enabled is not True:
            return None
        try:
            port = int(
                self.device_config.config["insert"]["components"]["video"]["rtsp"][
                    "port"
                ]
            )
        except (KeyError, TypeError, ValueError):
            return None
        return f"rtsp://{self.ip_address}:{port}/ph264"

    async def __aenter__(self) -> "SwidgetDevice":
        """Initialize and connect the Swidget Websocket client."""
        await self.connect()
        return self

    async def __aexit__(
        self, exc_type: Exception, exc_value: str, traceback: TracebackType
    ) -> None:
        """Disconnect from the websocket."""
        await self.disconnect()

    def __repr__(self) -> str:
        if self._last_update == 0:
            return f"<{self.device_type} at {self.ip_address} - update() needed>"
        return f"<{self.device_type} model {self.model} at {self.ip_address}>"


class SwidgetAssembly:
    """Class to represent parts of the Swidget device."""

    def __init__(self, summary: dict):
        self.type = summary["type"]
        self.components = {
            c["id"]: SwidgetComponent(c) for c in summary["components"]
        }
        self.id = summary.get("id")
        self.error = summary.get("error")


class SwidgetComponent:
    """Component-level representation of a Swidget Assembly.

    ``summary_functions`` is the immutable list of function tags the
    device declared in its summary — this is the schema. ``functions``
    starts as a same-keyed dict of placeholder ``None`` values and is
    later mutated by ``process_state`` to carry live datapoint values.

    Process_state also leaks in keys that aren't in the summary
    functions list (e.g. fans emit a ``modules`` map in state that
    isn't a declared function tag), so ``functions.keys()`` is *not*
    schema-stable across summary refreshes. Anything that needs a
    stable schema fingerprint (entity wiring, structure-change
    detection) must read ``summary_functions``, not ``functions``.

    ``max_cfm``, ``model_code`` and ``modules`` come from the optional
    summary-level fields fan hosts emit alongside ``functions`` —
    non-fan components don't populate them.
    """

    def __init__(self, component):
        funcs = list(component.get("functions", []))
        self.summary_functions: tuple[str, ...] = tuple(funcs)
        self.functions = {f: None for f in funcs}
        self.max_cfm = component.get("maxCFM")
        self.model_code = component.get("code")
        self.modules = list(component.get("modules", []))


class DeviceConfiguration:
    """A class to represent and manage the Swidget device configuration."""

    def __init__(self, config_dict={}):
        self._config_dict = config_dict

    def config_populated(self) -> bool:
        """Return if configuration has been retrieved from the device."""
        return self._config_dict != {}

    @property
    def config(self):
        """Return the config dictionary for the device."""
        return self._config_dict

    @config.setter
    def config(self, config_dict={}):
        self._config_dict = config_dict

    def update_config(self, updates):
        """Update configuration with the given updates."""
        for key, value in updates.items():
            self._set_nested_value(self._config_dict, key.split("."), value)

    def _set_nested_value(self, config, keys, value):
        """Set nested value in the configuration."""
        for key in keys[:-1]:
            config = config.setdefault(key, {})
        config[keys[-1]] = value
