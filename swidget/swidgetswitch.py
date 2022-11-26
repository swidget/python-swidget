from swidget.swidgetdevice import (
    DeviceType,
    SwidgetDevice
)


class SwidgetSwitch(SwidgetDevice):

    def __init__(self, host,  secret_key: str, ssl: bool, use_websockets: bool) -> None:
        super().__init__(host=host, secret_key=secret_key, ssl=ssl, use_websockets=use_websockets)
        self._device_type = DeviceType.Switch

    async def current_consumption(self) -> float:
        """Get the current power consumption in watts."""
        return sum([await plug.current_consumption() for plug in self.children])