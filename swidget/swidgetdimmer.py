import logging

from swidget.swidgetdevice import (
    DeviceType,
    SwidgetDevice
)
from swidget.exceptions import SwidgetException



log = logging.getLogger(__name__)

class SwidgetDimmer(SwidgetDevice):

    def __init__(self, host,  secret_key: str, ssl: bool, use_websockets: bool) -> None:
        super().__init__(host=host, secret_key=secret_key, ssl=ssl, use_websockets=use_websockets)
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

    async def set_brightness(self, brightness):
        """Set the brightness of the device."""
        await self.send_command(
            assembly="host", component="0", function="level", command={"now": brightness}
        )

    async def set_default_brightness(self, brightness):
        await self.send_command(
            assembly="host", component="0", function="level", command={"default": brightness}
        )

    @property  # type: ignore
    def is_dimmable(self) -> bool:
        """Whether the switch supports brightness changes."""
        return True