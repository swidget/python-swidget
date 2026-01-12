"""Module (main-class) that represents a Swidget device."""

import json
import logging
import time
from collections.abc import Callable
from enum import Enum
from types import TracebackType
from typing import Any, Dict, List, Optional

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
    """Device type enum."""

    Dimmer = "dimmer"
    Outlet = "outlet"
    Switch = "switch"
    TimerSwitch = "pana_switch"
    RelaySwitch = "relay_switch"
    Unknown = -1


class InsertType(Enum):
    """Insert type enum."""

    USB = "USB"
    THM = "TEMP HUMI MOTION"
    TH = "TEMP HUMI"
    AQ = "AIR QUALITY"
    GL = "GUIDE LIGHT"
    PO = "POWER OUT"
    VIDEO = "video"  # This is not a mistake.
    USBC = "USBC"
    WD = "WATER DETECTOR"
    Unknown = -1


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
        _LOGGER.debug(f"Sending {http_method} request to: {url}")

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
                        return {}
                    return await response.json()
                elif response.status == 403:
                    _LOGGER.error(
                        f"Authentication failed for {http_method} '{endpoint}'"
                    )
                    raise SwidgetAuthenticationException
                else:
                    response.raise_for_status()
                return {}
        except ClientConnectorError as e:
            _LOGGER.error(f"Connection error while requesting '{endpoint}': {e}")
            raise SwidgetConnectionException from e

    async def get_device_config(self) -> Any:
        """Get the config of the device."""
        _LOGGER.debug("SwidgetDevice.get_device_config() called")
        _LOGGER.debug("Sending get_summary() command over http")
        config = await self.make_http_request("GET", "device_config")
        self.device_config = DeviceConfiguration(config)
        self._last_update = int(time.time())

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
        self.assemblies = {
            "host": SwidgetAssembly(summary["host"]),
            "insert": SwidgetAssembly(summary["insert"]),
        }
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
            await self.make_http_request("GET", "state")

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
                except Exception:
                    pass
        self._last_update = int(time.time())

    async def update(self) -> None:
        """Update the state, summary, config and name of the device."""
        _LOGGER.debug("SwidgetDevice.update() called")
        if self._last_update == 0:
            _LOGGER.debug("Performing the initial update to obtain sysinfo")
            await self.get_summary()
            await self.get_state()
            if self._friendly_name == "Unknown Swidget Device":
                await self.get_friendly_name()
            if not self.device_config.config_populated():
                await self.get_device_config()
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
        self, assembly: str, component: str, function: str, command: dict
    ) -> None:
        """Send a command to the Swidget device either using a HTTP call or the existing websocket."""
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
            response = await self.make_http_request("GET", "ping")
            return True if response == {} else bool(response)
        except Exception:
            return False

    async def blink(self) -> Any:
        """Make the device LED blink.

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        _LOGGER.debug("SwidgetDevice.blink() called")
        return await self.make_http_request("GET", "blink")
        # try:

        #     async with self._session.get(
        #         url=f"{self.uri_scheme}://{self.ip_address}/blink", ssl=False
        #     ) as response:
        #         return await response.json()
        # except Exception:
        #     raise SwidgetException

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
        """Return True if the device is an outlet."""
        return self.device_type == DeviceType.Outlet

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
            c["id"]: SwidgetComponent(c["functions"]) for c in summary["components"]
        }
        self.id = summary.get("id")
        self.error = summary.get("error")


class SwidgetComponent:
    """Component-level representation of a Swidget Assembly."""

    def __init__(self, functions):
        self.functions = {f: None for f in functions}


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
