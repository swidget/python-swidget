"""Python interface for Swidget smart home devices.

All common, shared functionalities are available through `SwidgetDevice` class::

    x = SwidgetDevice("192.168.1.1", "mypassword")
    print(x.sys_info)

For device type specific actions `SwidgetDimmer`, `SwidgetOutlet`, or `SwidgetSwitch`
 should be used instead.

Module-specific errors are raised as `SwidgetException` and are expected
to be handled by the user of the library.
"""
from importlib_metadata import version  # type: ignore

from swidget.discovery import discover_devices, discover_single, SwidgetDiscoveredDevice
from swidget.exceptions import SwidgetException
from swidget.swidgetdevice import DeviceType, SwidgetAssembly, SwidgetDevice, SwidgetComponent
from swidget.swidgetdimmer import SwidgetDimmer
from swidget.swidgetoutlet import SwidgetOutlet
from swidget.swidgetswitch import SwidgetSwitch
from swidget.swidgettimerswitch import SwidgetTimerSwitch


__version__ = version("python-swidget")


__all__ = [
    "discover_devices",
    "discover_single",
    "SwidgetDiscoveredDevice",
    "SwidgetException",
    "DeviceType",
    "SwidgetAssembly",
    "SwidgetDevice",
    "SwidgetComponent",
    "SwidgetDimmer",
    "SwidgetOutlet",
    "SwidgetSwitch",
    "SwidgetTimerSwitch",
]