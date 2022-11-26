from swidget.swidgetdevice import (
    DeviceType,
)
from swidget.swidgetswitch import SwidgetSwitch


class SwidgetTimerSwitch(SwidgetSwitch):

    def __init__(self, host,  secret_key: str, ssl: bool, use_websockets: bool) -> None:
        super().__init__(host=host, secret_key=secret_key, ssl=ssl, use_websockets=use_websockets)
        self._device_type = DeviceType.TimerSwitch

    async def set_countdown_timer(self, minutes):
        """Set the countdown timer."""
        await self.send_command(
            assembly="host", component="0", function="timer", command={"duration": minutes}
        )