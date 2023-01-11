from swidget.swidgetdevice import (
    DeviceType,
    SwidgetDevice
)


class SwidgetOutlet(SwidgetDevice):

    def __init__(self, host,  token_name: str, secret_key: str, ssl: bool, use_websockets: bool) -> None:
        super().__init__(host=host, token_name=token_name, secret_key=secret_key, ssl=ssl, use_websockets=use_websockets)
        self._device_type = DeviceType.Outlet