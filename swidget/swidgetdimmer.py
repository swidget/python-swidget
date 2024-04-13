import logging

from swidget.swidgetdevice import (
    DeviceType,
    SwidgetDevice
)
from swidget.exceptions import SwidgetException

_LOGGER = logging.getLogger(__name__)


class SwidgetDimmer(SwidgetDevice):

    def __init__(self, host,  token_name: str, secret_key: str, use_https: bool, use_websockets: bool) -> None:
        super().__init__(host=host, token_name=token_name, secret_key=secret_key, use_https=use_https, use_websockets=use_websockets)
        self._device_type = "dimmer"

    @property  # type: ignore
    def brightness(self) -> int:
        """Return current brightness on dimmers.

        Will return a range between 0 - 100.
        """
        if not self.is_dimmable:
            raise SwidgetException("Device is not dimmable.")
        try:
            return self.assemblies['host'].components["0"].functions["level"]["now"]
        except KeyError:
            return self.assemblies['host'].components["0"].functions["level"]["default"]

    async def set_brightness(self, brightness) -> None:
        """Set the brightness of the device."""
        _LOGGER.debug("SwidgetDimmer.set_brightness() called")
        await self.send_command(
            assembly="host", component="0", function="level", command={"now": brightness}
        )

    async def set_default_brightness(self, brightness) -> None:
        _LOGGER.debug("SwidgetDimmer.set_default_brightness() called")
        await self.send_command(
            assembly="host", component="0", function="level", command={"default": brightness}
        )

    @property  # type: ignore
    def is_dimmable(self) -> bool:
        """Whether the switch supports brightness changes."""
        return True