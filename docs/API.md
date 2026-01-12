API Overview
============

This document summarizes the public surface of the python-swidget library. All network calls are local to the device; no cloud access is required.

Core types
----------
- `SwidgetDevice`: base class for devices. Shared HTTP/websocket plumbing and state.
- `SwidgetDimmer`: dimmer-capable host.
- `SwidgetOutlet`: outlet host.
- `SwidgetSwitch`: switch host.
- `SwidgetTimerSwitch`: timer-capable switch (20/40/60 style).
- `discover_devices(timeout=5)`: SSDP discovery; returns `dict[mac, SwidgetDiscoveredDevice]`.
- `discover_single(host, token_name, password, use_https, use_websockets)`: probe a host and return the correct device subclass.
- `provision_wifi(device_name, ssid, network_password, secret_key)`: provision via the device AP (TLS verification disabled by design for AP mode).

Construction
------------
```python
SwidgetDevice(host, token_name, secret_key, use_https=True, use_websockets=True, verify_ssl=False)
```
- `use_https`: select http/https scheme.
- `use_websockets`: enable realtime websocket use.
- `verify_ssl`: set True if you have valid TLS certs; defaults False for local devices.

Common properties
-----------------
- `device_type`, `insert_type`, `friendly_name`
- `assemblies`: host/insert assemblies with components/functions
- `hw_info`: dict of version, mac, type, id, model, insert info, rssi
- `realtime_values`: merged sensor/power values
- `host_features`, `insert_features`
- `is_outlet`, `is_switch`, `is_dimmer`, `is_dimmable`, `is_pana_switch`

Lifecycle
---------
- `start()`: connect websocket (if enabled) and perform `update()`.
- `update()`: fetch summary + state (+ friendly name/config on first call).
- `stop()/close()/disconnect()`: close websocket (if any) and HTTP session.
- `connect()`: websocket connect only (advanced).

Data fetch
----------
- `get_summary()`: populate model, mac, version, assemblies, types.
- `get_state()`: populate power/sensor state.
- `get_device_config()`: fetch configuration (HTTP).
- `get_friendly_name()`: fetch name (HTTP fallback).

Control
-------
- `send_command(assembly, component, function, command_dict)`: generic command (websocket when connected, otherwise HTTP).
- `send_config(payload)`: websocket-only config push (raises in HTTP-only mode).
- `turn_on()/turn_off()`: host toggle.
- `turn_on_usb_insert()/turn_off_usb_insert()`: USB insert toggle (where applicable).
- `set_brightness()/set_default_brightness()`: dimmer brightness controls.
- `set_countdown_timer(minutes)`: timer switch duration.
- `ping()`, `blink()`, `enable_debug_server()`, `restart_device()`, `factory_reset()`, `check_for_updates()`, `update_version()`.

Media helpers (video-capable inserts)
-------------------------------------
- `stream_url` (property): RTSP URL.
- `snapshot_url` (property): snapshot URL.
- `get_snapshot_bytes(width=None, height=None)`: fetch snapshot bytes.

Websocket
---------
- `SwidgetWebsocket(host, token_name, secret_key, callback, session=None, use_security=True, verify_ssl=False, retry_interval=30, max_retries=None)`
- Methods: `connect()`, `send_str()`, `receive()`, `close()`, `reconnect()`, `run()`, `status`, `connected`.

Discovery
---------
- `discover_devices(timeout=5)`: SSDP broadcast; returns mapping of MAC → `SwidgetDiscoveredDevice` with `mac`, `host`, `friendly_name`, `host_type`, `insert_type`.
- `discover_single(...)`: probes a host over HTTP summary and returns the correct device subclass instance (websocket flag is passed through).

Provisioning
------------
- `provision_wifi(device_name, ssid, network_password, secret_key)`
  - Connect to the device AP (`https://10.123.45.1`), sends credentials, polls until success, and triggers setup completion.
  - TLS verification is disabled by design for AP mode.
  - Retries are time.sleep based; see `swidget/provision.py` for details.

CLI
---
Entry point: `swidget` (asyncclick).
Key commands:
- `discover` (SSDP scan)
- `state`, `on`, `off`, `brightness`, `ping`, `blink`
- `wifi join` (AP provisioning)
- `check_for_updates`, `upgrade`

Development & testing
---------------------
- Run tests: `pytest`
- Lint: `black --check .`
- Git hook: `git config core.hooksPath githooks` (hook runs black + pytest)
- Integration (real devices) is kept separate: `devtools/synthetic_test.py`
