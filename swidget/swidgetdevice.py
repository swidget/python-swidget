import json
import logging
import time

from aiohttp import ClientSession, TCPConnector
import asyncio
from enum import Enum
from typing import Dict, List, Set

from .exceptions import SwidgetException
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


class SwidgetDevice:
    def __init__(self, host, token_name, secret_key, use_https=True, use_websockets=True):
        self.token_name = token_name
        self.ip_address = host

        self.use_https = use_https
        self.uri_scheme = 'https' if self.use_https is True else 'http'
        self.secret_key = secret_key
        self.use_websockets = use_websockets
        self.device_type = DeviceType.Unknown
        self._friendly_name = "Unknown Swidget Device"
        headers = {self.token_name: self.secret_key,
                   'Connection': 'keep-alive'}
        connector = TCPConnector(verify_ssl=False, force_close=True)
        self._session = ClientSession(headers=headers, connector=connector)
        self._last_update = None
        if self.use_websockets:
            self._websocket = SwidgetWebsocket(
                host=self.ip_address,
                token_name=self.token_name,
                secret_key=self.secret_key,
                callback=self.message_callback,
                session=self._session)

    def get_websocket(self):
        if self.use_websockets:
            return self._websocket
        return None

    def set_countdown_timer(self, minutes):
        raise NotImplementedError()

    async def connect(self):
        await self._websocket.connect()

    async def start(self):
        """Start the websocket."""
        _LOGGER.debug("SwidgetDevice.start()")
        if self.use_websockets:
            _LOGGER.debug("Calling self._websocket.connect()")
            await self._websocket.connect()
            _LOGGER.debug("Calling self._websocket.listen() ")
            asyncio.create_task(self._websocket.listen())

    async def stop(self):
        """Stop the websocket."""
        _LOGGER.debug("SwidgetDevice.stop()")
        if hasattr(self, '_websocket'):
            await self._websocket.close()
        await self._session.close()

    async def message_callback(self, message):
        """Entrypoint for a websocket callback"""
        _LOGGER.debug("SwidgetDevice.message_callback() called")
        if message["request_id"] == "summary":
            _LOGGER.debug("Calling SwidgetDevice.process_summary()")
            await self.process_summary(message)
        elif message["request_id"] == "state" or message["request_id"] == "DYNAMIC_UPDATE" or message["request_id"] == "command":
            _LOGGER.debug("Calling SwidgetDevice.process_state()")
            await self.process_state(message)
        else:
            _LOGGER.error(f"Unknown message type from websocket. Type given was: {message["request_id"]}")

    async def get_summary(self):
        """Get a summary of the device over HTTP"""
        _LOGGER.debug("SwidgetDevice.get_summary() called")
        if self.use_websockets:
            _LOGGER.debug("In websocket mode. Sending get_summary() command over websocket")
            await self._websocket.send_str(json.dumps({"type": "summary", "request_id": "summary"}))
        else:
            _LOGGER.debug("In http mode. Sending get_summary() command over http")
            async with self._session.get(
                url=f"{self.uri_scheme}://{self.ip_address}/api/v1/summary", ssl=False
            ) as response:
                summary = await response.json()
            await self.process_summary(summary)

    async def process_summary(self, summary):
        """ Process the data around the summary of the device"""
        _LOGGER.debug("SwidgetDevice.process_summary() called")
        _LOGGER.debug(f"Summary to process: {summary}")
        self.model = summary["model"]
        self.mac_address = summary["mac"]
        self.version = summary["version"]
        self.assemblies = {
            "host": SwidgetAssembly(summary["host"]),
            "insert": SwidgetAssembly(summary["insert"]),
        }
        self.device_type = self.assemblies['host'].type
        self.insert_type = self.assemblies['insert'].type
        self.id = self.assemblies['host'].id
        self._last_update = int(time.time())

    async def get_friendly_name(self):
        _LOGGER.debug("SwidgetDevice.get_friendly_name() called")
        try:
            async with self._session.get(
                url=f"{self.uri_scheme}://{self.ip_address}/api/v1/name", ssl=False
            ) as response:
                name = await response.json()
        except Exception:
            name = {"name": f"Swidget {self.device_type} w/{self.insert_type} insert"}
        await self.process_friendly_name(name['name'])

    async def process_friendly_name(self, name):
        _LOGGER.debug("SwidgetDevice.process_friendly_name() called")
        self._friendly_name = name
        self._last_update = int(time.time())

    async def get_state(self):
        """ Get the state of the device over HTTP"""
        _LOGGER.debug("SwidgetDevice.get_state() called")
        if self.use_websockets:
            _LOGGER.debug("In websocket mode. Sending get_summary() command over websocket")
            await self._websocket.send_str(json.dumps({"type": "state", "request_id": "state"}))
        else:
            _LOGGER.debug("In http mode. Sending get_summary() command over http")
            async with self._session.get(
                url=f"{self.uri_scheme}://{self.ip_address}/api/v1/state", ssl=False
            ) as response:
                state = await response.json()
            await self.process_state(state)

    async def process_state(self, state):
        """ Process any information about the state of the device or insert"""
        # State is not always in the state (during callback)
        _LOGGER.debug("SwidgetDevice.process_state() called")
        _LOGGER.debug(f"State to process: {state}")
        try:
            self.rssi = state["connection"]["rssi"]
        except:
            pass
        for assembly in self.assemblies:
            for id, component in self.assemblies[assembly].components.items():
                try:
                    component.functions.update(state[assembly]["components"][id])
                except:
                    pass
        self._last_update = int(time.time())

    async def update(self):
        _LOGGER.debug("SwidgetDevice.update() called")
        if self._last_update is None:
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

    async def send_config(self, payload: dict):
        _LOGGER.debug("SwidgetDevice.send_config() called")
        data = json.dumps({"type":"config","request_id":"send_config", "payload": payload})
        await self._websocket.send_str(data)

    async def send_command(
        self, assembly: str, component: str, function: str, command: dict
    ):
        _LOGGER.debug("SwidgetDevice.send_command() called")
        """Send a command to the Swidget device either using a HTTP call or the existing websocket"""
        data = {assembly: {"components": {component: {function: command}}}}
        _LOGGER.debug(f"Command to send: {data}")
        if self.use_websockets:
            _LOGGER.debug("In websocket mode. Sending command over websocket")
            data = json.dumps({"type": "command",
                               "request_id": "command",
                               "payload": data
                               })
            await self._websocket.send_str(data)
        else:
            _LOGGER.debug("NOT in websocket mode, sending command over HTTP")
            async with self._session.post(
                url=f"{self.uri_scheme}://{self.ip_address}/api/v1/command",
                ssl=False,
                data=json.dumps(data),
            ) as response:
                state = await response.json()

            # Do a hard set of the new state of the device. May change this in the future
            function_value = state[assembly]["components"][component][function]
            self.assemblies[assembly].components[component].functions[function] = function_value  # fmt: skip

    async def ping(self):
        """Ping the device to ensure it's devices

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        _LOGGER.debug("SwidgetDevice.ping() called")
        try:
            async with self._session.get(
                url=f"{self.uri_scheme}://{self.ip_address}/ping",
                ssl=False
            ) as response:
                return response.status
        except:
            raise SwidgetException

    async def blink(self):
        """Make the device LED blink

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        _LOGGER.debug("SwidgetDevice.blink() called")
        try:
            async with self._session.get(
                url=f"{self.uri_scheme}://{self.ip_address}/blink",
                ssl=False
            ) as response:
                return await response.json()
        except:
            raise SwidgetException

    async def enable_debug_server(self):
        """Enable the Swidget local debug server

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        _LOGGER.debug("SwidgetDevice.enable_debug_server() called")
        try:
            async with self._session.get(
                url=f"{self.uri_scheme}://{self.ip_address}/debug?x-secret-key={self.secret_key}",
                ssl=False
            ) as response:
                return await response.json()
        except:
            raise SwidgetException

    async def factory_reset(self):
        """Factory reset the Swidget device

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        try:

            async with self._session.delete(
                url=f"{self.uri_scheme}://{self.ip_address}/api/v1/reset",
                ssl=False
            ) as response:
                return await response.json()
        except:
            raise SwidgetException

    async def check_for_updates(self):
        """Tell the device to contact the Swidget servers to see if there is an available update

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        try:

            async with self._session.get(
                url=f"{self.uri_scheme}://{self.ip_address}/api/v1/update",
                ssl=False
            ) as response:
                return await response.json()
        except:
            raise SwidgetException

    async def update_version(self, version):
        """Tell the device to download and apply an update

        :raises SwidgetException: Raise the exception if there we are unable to connect to the Swidget device
        """
        try:
            data = {
                "version": version
            }
            async with self._session.post(
                url=f"{self.uri_scheme}://{self.ip_address}/api/v1/update",
                ssl=False,
                data=json.dumps(data)
            ) as response:
                return await response
        except:
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
            "rssi": self.rssi
        }

    async def get_child_consumption(self, plug_id=0):
        """Get the power consumption of a plug in watts."""
        if plug_id == "all":
            return_dict = {}
            for id, properties in self.assemblies['host'].components.items():
                try:
                    return_dict[f"power_{id}"] = properties.functions['power']['current']
                except KeyError: # Hits this when there is no power metering
                    return None
            return return_dict
        return self.assemblies['host'].components[str(plug_id)].functions['power']['current']

    async def total_consumption(self):
        """Get the total power consumption in watts."""
        total_consumption = 0
        for id, properties in self.assemblies['host'].components.items():
            total_consumption += properties.functions['power']['current']
        return total_consumption

    @property
    async def realtime_values(self):
        """Get a dict of realtime value attributes from the insert and host

        :return: A dictionary of insert sensor values and power consumption values
        :rtype: dict
        """
        return_dict = {}
        for feature in self.insert_features:
            return_dict.update(self.get_function_values(feature))
        return_dict.update({'rssi': self.rssi})
        power_values = await self.get_child_consumption("all")
        if power_values:
            return_dict.update(power_values)
        return return_dict

    @property
    def host_features(self) -> List[str]:
        """Return a set of features that the host supports."""
        try:
            return list(self.assemblies['host'].components['0'].functions.keys())
        except KeyError:
            return set()

    @property
    def insert_features(self) -> List[str]:
        """Return a set of features that the insert supports."""
        try:
            return list(self.assemblies['insert'].components.keys())
        except KeyError:
            return set()

    def get_function_values(self, function: str):
        """Return the values of an insert function."""
        return_values = dict()
        for function, data in self.assemblies['insert'].components[function].functions.items():
            if function == "occupied":
                return_values[function] = data['state']
            elif function == "toggle":
                pass
            else:
                return_values[function] = data['now']
        return return_values

    def get_sensor_value(self, function, sensor):
        """Return the value of a sensor given a function and sensor"""
        if sensor == "occupied":
            return self.assemblies['insert'].components[function].functions['occupied']['state']
        else:
            return self.assemblies['insert'].components[function].functions[sensor]['now']

    @property
    def is_outlet(self) -> bool:
        """Return True if the device is an outlet."""
        return self.device_type == "outlet"

    @property
    def is_switch(self) -> bool:
        """Return True if the device is a switch"""
        return self.device_type == "switch" or self.device_type == "pana_switch" or self.device_type == "relay_switch"

    @property
    def is_pana_switch(self) -> bool:
        """Return True if the device is a pana_switch"""
        return self.device_type == "pana_switch"

    @property
    def is_dimmer(self) -> bool:
        """Return True if the device is a dimmer"""
        return self.device_type == "dimmer"

    @property
    def is_dimmable(self) -> bool:
        """Return  True if the device is dimmable."""
        return self.is_dimmer

    @property  # type: ignore
    def friendly_name(self) -> str:
        """Return a friendly description of the device"""
        return self._friendly_name

    @property  # type: ignore
    def is_on(self) -> bool:
        """Return whether device is on."""
        dimmer_state = self.assemblies['host'].components["0"].functions['toggle']["state"]
        if dimmer_state == "on":
            return True
        return False

    async def turn_on(self):
        """Turn the device on."""
        _LOGGER.debug("SwidgetDevice.turn_on() called")
        await self.send_command(
            assembly="host", component="0", function="toggle", command={"state": "on"}
        )

    async def turn_off(self):
        """Turn the device off."""
        _LOGGER.debug("SwidgetDevice.turn_off() called")
        await self.send_command(
            assembly="host", component="0", function="toggle", command={"state": "off"}
        )

    async def turn_on_usb_insert(self):
        """Turn the USB insert on."""
        await self.send_command(
            assembly="insert", component="usb", function="toggle", command={"state": "on"}
        )

    async def turn_off_usb_insert(self):
        """Turn the USB insert off."""
        await self.send_command(
            assembly="insert", component="usb", function="toggle", command={"state": "off"}
        )

    @property  # type: ignore
    def usb_is_on(self) -> bool:
        """Return whether USB is on."""
        usb_state = self.assemblies['insert'].components["usb"].functions['toggle']["state"]
        if usb_state == "on":
            return True
        return False

    def __repr__(self):
        if self._last_update is None:
            return f"<{self.device_type} at {self.ip_address} - update() needed>"
        return f"<{self.device_type} model {self.model} at {self.ip_address}>"


class SwidgetAssembly:
    def __init__(self, summary: dict):
        self.type = summary["type"]
        self.components = {
            c["id"]: SwidgetComponent(c["functions"]) for c in summary["components"]
        }
        self.id = summary.get("id")
        self.error = summary.get("error")


class SwidgetComponent:
    def __init__(self, functions):
        self.functions = {f: None for f in functions}
