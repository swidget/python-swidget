import logging
from swidget.swidgetdevice import (
    DeviceType,
)
from swidget.swidgetswitch import SwidgetSwitch

_LOGGER = logging.getLogger(__name__)


class SwidgetTimerSwitch(SwidgetSwitch):

    def __init__(self, host,  token_name: str, secret_key: str, use_https: bool, use_websockets: bool) -> None:
        super().__init__(host=host, token_name=token_name, secret_key=secret_key, use_https=use_https, use_websockets=use_websockets)
        self._device_type = DeviceType.TimerSwitch

    async def set_countdown_timer(self, minutes):
        """Set the countdown timer."""
        _LOGGER.debug("SwidgetTimerSwitch.set_brightness() called")
        await self.send_command(
            assembly="host", component="0", function="timer", command={"duration": minutes}
        )