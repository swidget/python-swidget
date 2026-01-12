python-swidget
==============

![CI](https://github.com/swidget/python-swidget/actions/workflows/ci.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/python-swidget)
![License](https://img.shields.io/pypi/l/python-swidget)

Python SDK for Swidget smart devices. It supports local HTTP control and websockets for realtime updates, along with SSDP discovery, Wi-Fi provisioning helpers, and a CLI tool (`swidget`).

Table of contents
-----------------
- Installation
- Quickstart
- Device types and helpers
- HTTP vs websocket modes
- Discovery
- Provisioning (AP mode)
- CLI usage
- Development (tests, lint, hooks)

Installation
------------
Using Poetry (preferred):
```
poetry install --with dev
```

Using pip:
```
pip install python-swidget
```

Quickstart
----------
```python
from swidget import SwidgetDimmer

dev = SwidgetDimmer(
    host="192.168.1.50",
    token_name="x-secret-key",
    secret_key="password",
    use_https=True,
    use_websockets=False,  # set True for realtime updates
)

# HTTP-only mode
await dev.update()
await dev.turn_on()
await dev.turn_off()
await dev.close()
```

Websocket mode (realtime)
```python
dev = SwidgetDimmer(
    host="192.168.1.50",
    token_name="x-secret-key",
    secret_key="password",
    use_https=True,
    use_websockets=True,
)
await dev.start()   # opens websocket and updates state
await dev.turn_on()
await dev.close()
```

Device types and helpers
------------------------
- `SwidgetDevice` – base class (shared HTTP/websocket helpers)
- `SwidgetDimmer` – brightness control (`brightness`, `set_brightness`)
- `SwidgetOutlet` – outlet control (`turn_on`, `turn_off`, power readings)
- `SwidgetSwitch` – generic switch control (`turn_on`, `turn_off`)
- `SwidgetTimerSwitch` – timer-capable switch (`set_countdown_timer`)

Common properties:
- `device_type`, `insert_type`, `friendly_name`, `hw_info`
- `realtime_values`: convenience dict of sensor/power values

Common actions:
- `turn_on()`, `turn_off()`, `blink()`, `ping()`
- `update()` to refresh summary/state/config
- `send_command(assembly, component, function, command_dict)` for raw control

HTTP vs websocket modes
-----------------------
- HTTP-only: set `use_websockets=False`. All operations go over REST (`/api/v1/...`).
- Websocket mode: set `use_websockets=True`. Summary/state updates and commands use the socket when connected; HTTP is used as fallback where applicable.
- TLS: `use_https=True` disables certificate verification by default; pass `verify_ssl=True` when constructing `SwidgetDevice` if you have valid certs.

Discovery
---------
Discover devices via SSDP:
```python
from swidget import discover_devices
devices = await discover_devices(timeout=5)
for mac, dev in devices.items():
    print(dev.host, dev.friendly_name, dev.host_type, dev.insert_type)
```

Discover a single device when you know the IP:
```python
from swidget import discover_single
dev = await discover_single(
    host="192.168.1.50",
    token_name="x-secret-key",
    password="device_password",
    use_https=True,
    use_websockets=False,
)
await dev.update()
```

Provisioning (AP mode)
----------------------
Provision a device while connected to its AP (`Swidget-...` SSID):
```python
from swidget import provision_wifi
provision_wifi(
    device_name="My Swidget",
    ssid="HomeWiFi",
    network_password="wifi-pass",
    secret_key="factory-secret",
)
```
Notes:
- Provisioning disables TLS verification; run only on the device’s AP network.
- The helper waits for connection success and triggers setup completion.

CLI usage
---------
Install the console entrypoint via Poetry/pip and run:
```
swidget --host 192.168.1.50 --password device_password --type dimmer state
swidget --host 192.168.1.50 --password device_password on
swidget --host 192.168.1.50 --password device_password brightness 80
swidget discover
```
Key options:
- `--http_only` (flag) to force HTTP-only (no websockets)
- `--type` to skip discovery when you know the device type
- `wifi join` to provision via AP (prompts for SSID/password)

Development
-----------
Run tests and lint (hook runs both):
```
pytest
black --check .
```

If you install via plain pip and want the dev toolchain (tests, typing, docs, formatting):
```
pip install pytest pytest-asyncio aioresponses mypy black sphinx sphinx-rtd-theme sphinx-autobuild
```

Enable git hook (optional):
```
git config core.hooksPath githooks
```

Code structure:
- `swidget/` core library: device models, discovery, provisioning, websocket client, CLI
- `tests/` unit tests (network mocked)
- `devtools/synthetic_test.py` optional integration script for real devices (kept separate from unit tests)
- `examples/` runnable samples (dimmer HTTP, outlet power, timer switch, snapshot)

Additional examples
-------------------

Outlet (power reading + toggle)
```
from swidget import SwidgetOutlet

dev = SwidgetOutlet(
    host="192.168.1.60",
    token_name="x-secret-key",
    secret_key="password",
    use_https=True,
    use_websockets=False,
)
await dev.update()
print("Host features:", dev.host_features)
print("Realtime values:", dev.realtime_values)
await dev.turn_on()
await dev.turn_off()
await dev.close()
```

Timer switch
```
from swidget import SwidgetTimerSwitch

dev = SwidgetTimerSwitch(
    host="192.168.1.61",
    token_name="x-secret-key",
    secret_key="password",
    use_https=True,
    use_websockets=False,
)
await dev.set_countdown_timer(20)  # minutes
await dev.close()
```

Snapshots (video-capable insert)
```
from swidget import SwidgetDevice

dev = SwidgetDevice(
    host="192.168.1.62",
    token_name="x-secret-key",
    secret_key="password",
    use_https=True,
    use_websockets=False,
)
await dev.update()
img = await dev.get_snapshot_bytes(width=640, height=360)
with open("snapshot.jpg", "wb") as f:
    f.write(img)
await dev.close()
```

Type checking
-------------
Run mypy in strict mode:
```
poetry run mypy --strict swidget
```

Docs build
----------
Generate HTML docs with Sphinx:
```
cd docs
poetry run sphinx-build -b html . _build
```
