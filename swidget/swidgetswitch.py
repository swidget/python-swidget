"""Module for a generic SwidgetSwitch."""
from swidget.swidgetdevice import DeviceType, SwidgetDevice


class SwidgetSwitch(SwidgetDevice):
    """Representation of a Swidget Switch device."""

    def __init__(
        self,
        host,
        token_name: str,
        secret_key: str,
        use_https: bool,
        use_websockets: bool,
    ) -> None:
        super().__init__(
            host=host,
            token_name=token_name,
            secret_key=secret_key,
            use_https=use_https,
            use_websockets=use_websockets,
        )
        self._device_type = DeviceType.Switch
