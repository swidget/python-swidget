"""Module to discover Swidget devices."""
import asyncio
import logging
import socket
from typing import Any, Type
from urllib.parse import urlparse

import ssdp
from aiohttp import ClientError, ClientSession, ClientTimeout, TCPConnector

from swidget.swidgetdevice import DeviceType, SwidgetDevice

from .exceptions import SwidgetException
from .swidgetdimmer import SwidgetDimmer
from .swidgetoutlet import SwidgetOutlet
from .swidgetswitch import SwidgetSwitch
from .swidgettimerswitch import SwidgetTimerSwitch

RESPONSE_SEC = 5
SWIDGET_STS = ("urn:swidget:pico:1", "urn:swidget:video:1")

# Per-ST raw device-id length (in hex chars) before any UUID padding. The
# firmware embeds the device id in the SSDP USN differently per family:
# pico uses a fixed UUID prefix + the 12-char id as the last segment;
# video pads the 24-char id with zeros to fit a 32-char UUID. Both can
# be recovered as long as we know the original length per ST.
_USN_DEVICE_ID_LENGTH = {
    "urn:swidget:pico:1": 12,
    "urn:swidget:video:1": 24,
}


def device_id_from_ssdp(usn: str, st: str) -> Optional[str]:
    """Extract the canonical device id from an SSDP USN/ST pair.

    Returns None when the inputs aren't recognized — callers should treat
    that as "skip this discovery" rather than synthesizing an id.
    """
    if not usn or not usn.startswith("uuid:") or st not in _USN_DEVICE_ID_LENGTH:
        return None
    uuid_part = usn[len("uuid:") :]
    expected_len = _USN_DEVICE_ID_LENGTH[st]
    if st == "urn:swidget:pico:1":
        # Last hyphenated segment carries the real 12-char MAC.
        last = uuid_part.rsplit("-", 1)[-1]
        return last if len(last) == expected_len else None
    # Video (and any future variant that pads): dehyphenate, take the
    # leading expected_len chars, ignore the trailing zero padding.
    flat = uuid_part.replace("-", "")
    return flat[:expected_len] if len(flat) >= expected_len else None
# Generous timeout: TLS handshakes on the device's MCU can take several
# seconds on first connection.
DETECT_TIMEOUT_SEC = 10
_LOGGER = logging.getLogger(__name__)
devices = dict()


async def detect_secure(host: str, timeout: float = DETECT_TIMEOUT_SEC) -> bool:
    """Determine whether a Swidget device requires HTTPS+auth.

    Probes ``/api/v1/summary`` over HTTPS first (no credentials). A 403
    response means the firmware enforces auth — the device is in secure
    mode. If HTTPS is unreachable, falls back to HTTP; a 200 there means
    the device is in plaintext mode.

    :param host: Hostname or IP of the device.
    :param timeout: Per-request timeout in seconds. Defaults are generous
        because the device performs TLS termination on a low-power MCU
        and the first handshake can be several seconds.
    :return: True if the device requires HTTPS+auth, False if plaintext.
    :raises SwidgetException: If neither protocol returns a usable response.
    """
    timeout_obj = ClientTimeout(total=timeout)
    connector = TCPConnector(ssl=False, force_close=True)
    async with ClientSession(connector=connector, timeout=timeout_obj) as session:
        # Try plaintext first: it's the cheap path (no TLS handshake on the
        # MCU) and a 200 response unambiguously means plaintext mode.
        try:
            async with session.get(f"http://{host}/api/v1/summary") as resp:
                if resp.status == 200:
                    return False
        except (ClientError, asyncio.TimeoutError):
            pass

        # Fall back to HTTPS. A 403 means the firmware is enforcing auth.
        try:
            async with session.get(f"https://{host}/api/v1/summary") as resp:
                if resp.status == 403:
                    return True
        except (ClientError, asyncio.TimeoutError):
            pass

    raise SwidgetException(f"Could not reach Swidget device at {host}")


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
        st = headers.get("ST", "")
        if st not in SWIDGET_STS:
            return
        device_id = device_id_from_ssdp(headers.get("USN", ""), st)
        if not device_id:
            _LOGGER.debug("Skipping SSDP response with unparseable USN: %s", headers)
            return
        ip_address = urlparse(headers["LOCATION"]).hostname
        device_type = headers["SERVER"].split(" ")[1].split("+")[0]
        insert_type = headers["SERVER"].split(" ")[1].split("+")[1].split("/")[0]
        friendly_name = headers["SERVER"].split("/")[2].strip('"')
        devices[device_id] = SwidgetDiscoveredDevice(
            mac=device_id,
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

    # SSDP M-SEARCH matches one ST per request, so emit one packet per
    # supported service type. Devices reply only to their matching ST.
    for st in SWIDGET_STS:
        search_request = ssdp.SSDPRequest(
            "M-SEARCH",
            headers={
                "HOST": "239.255.255.250:1900",
                "MAN": '"ssdp:discover"',
                "MX": timeout,
                "ST": st,
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
    if device_type in (DeviceType.Outlet, DeviceType.Outlet20A):
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
