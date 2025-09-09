"""Module to discover Swidget devices."""
import asyncio
import logging
import socket
from typing import Any, Type
from urllib.parse import urlparse

import ssdp  # type: ignore

from swidget.swidgetdevice import DeviceType, SwidgetDevice

from .exceptions import SwidgetException
from .swidgetdimmer import SwidgetDimmer
from .swidgetoutlet import SwidgetOutlet
from .swidgetswitch import SwidgetSwitch
from .swidgettimerswitch import SwidgetTimerSwitch

RESPONSE_SEC = 5
SWIDGET_ST = "urn:swidget:pico:1"
_LOGGER = logging.getLogger(__name__)
devices = dict()


class SwidgetDiscoveredDevice:
    """Stub class to capture details about discovered devices."""

    def __init__(
        self,
        mac: str,
        host: str,
        host_type: str,
        insert_type: str,
        friendly_name: str = "Swidget Discovered Device",
        host_id: str = "",
    ):
        self.mac = mac
        self.host = host
        self.friendly_name = friendly_name
        self.host_type = host_type
        self.insert_type = insert_type
        self.host_id = host_id


class SwidgetProtocol(ssdp.SimpleServiceDiscoveryProtocol):
    """Protocol to handle responses and requests."""

    def response_received(self, response: ssdp.SSDPResponse, addr: tuple):
        """Handle an incoming response."""
        headers = {h[0]: h[1] for h in response.headers}
        mac_address = headers["USN"].split("-")[-1]
        ip_address = urlparse(headers["LOCATION"]).hostname
        if headers["ST"] == SWIDGET_ST:
            device_type = headers["SERVER"].split(" ")[1].split("+")[0]
            insert_type = headers["SERVER"].split(" ")[1].split("+")[1].split("/")[0]
            friendly_name = headers["SERVER"].split("/")[2].strip('"')
            devices[mac_address] = SwidgetDiscoveredDevice(
                mac=mac_address,
                host=ip_address,
                friendly_name=friendly_name,
                host_type=device_type,
                insert_type=insert_type,
            )
            _LOGGER.debug(
                f"Discovered Swidget device via SSDP: '{friendly_name}' at {ip_address} Type:{device_type}/{insert_type}"
            )


async def discover_devices(timeout=RESPONSE_SEC):
    """Discover devices via SSDP."""
    global devices
    loop = asyncio.get_event_loop()
    devices = dict()
    transport, protocol = await loop.create_datagram_endpoint(
        SwidgetProtocol, family=socket.AF_INET
    )

    # Send out an M-SEARCH request, requesting Swidget service types.
    search_request = ssdp.SSDPRequest(
        "M-SEARCH",
        headers={
            "HOST": "239.255.255.250:1900",
            "MAN": '"ssdp:discover"',
            "MX": timeout,
            "ST": SWIDGET_ST,
        },
    )
    search_request.sendto(transport, (SwidgetProtocol.MULTICAST_ADDRESS, 1900))
    await asyncio.sleep(timeout)
    return devices


async def discover_single(
    host: str, token_name: str, password: str, use_https: bool, use_websockets: bool
) -> Any:
    """Discover a single device by the given IP address.

    :param host: Hostname of device to query
    :rtype: SwidgetDevice
    :return: Object for querying/controlling found device.
    """
    _LOGGER.debug(f"Checking for device at {host}")
    swidget_device = SwidgetDevice(
        host, token_name, password, use_https, use_websockets=False
    )
    _LOGGER.debug(f"Asking {host} for summary data")
    await swidget_device.get_summary()
    device_type = swidget_device.device_type
    _LOGGER.debug(f"{host} is of type {device_type}")
    await swidget_device.stop()

    _LOGGER.debug(f"Creating new device class of type: {device_type}")
    device_class = _get_device_class(device_type)
    _LOGGER.debug(f"{device_class} created")
    dev = device_class(host, token_name, password, use_https, use_websockets)
    return dev


def _get_device_class(device_type: DeviceType) -> Type[SwidgetDevice]:
    """Find SmartDevice subclass for device described by passed data."""
    if device_type == DeviceType.Outlet:
        return SwidgetOutlet
    elif device_type == DeviceType.Switch:
        return SwidgetSwitch
    elif device_type == DeviceType.Dimmer:
        return SwidgetDimmer
    elif device_type == DeviceType.TimerSwitch:  # This is the timer switch
        return SwidgetTimerSwitch
    elif device_type == DeviceType.RelaySwitch:
        return SwidgetSwitch
    raise SwidgetException("Unknown device type: %s" % device_type)
