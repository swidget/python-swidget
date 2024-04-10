from swidget.swidgetdevice import (
    DeviceType,
    SwidgetDevice
)


class SwidgetOutlet(SwidgetDevice):

    def __init__(self, host,  token_name: str, secret_key: str, use_https: bool, use_websockets: bool) -> None:
        super().__init__(host=host, token_name=token_name, secret_key=secret_key, use_https=use_https, use_websockets=use_websockets)
        self._device_type = DeviceType.Outlet