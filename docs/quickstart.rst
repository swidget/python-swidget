Quickstart
==========

Install
-------

With Poetry (recommended): ::

    poetry install --with dev

With pip: ::

    pip install python-swidget
    pip install pytest pytest-asyncio aioresponses mypy

HTTP-only example
-----------------

.. code-block:: python

    from swidget import SwidgetDimmer
    import asyncio

    async def main():
        dev = SwidgetDimmer(
            host="192.168.1.50",
            token_name="x-secret-key",
            secret_key="password",
            use_https=True,
            use_websockets=False,
        )
        await dev.update()
        await dev.turn_on()
        await dev.close()

    asyncio.run(main())

Websocket example
-----------------

.. code-block:: python

    from swidget import SwidgetDimmer
    import asyncio

    async def main():
        dev = SwidgetDimmer(
            host="192.168.1.50",
            token_name="x-secret-key",
            secret_key="password",
            use_https=True,
            use_websockets=True,
        )
        await dev.start()
        await dev.turn_off()
        await dev.close()

    asyncio.run(main())

Discovery
---------

.. code-block:: python

    from swidget import discover_devices
    import asyncio

    async def main():
        devices = await discover_devices(timeout=5)
        for mac, dev in devices.items():
            print(mac, dev.host, dev.friendly_name)

    asyncio.run(main())

CLI
---

.. code-block:: bash

    swidget discover
    swidget --host 192.168.1.50 --password device_password on
    swidget --host 192.168.1.50 --password device_password brightness 75

Examples
--------
- See the ``examples/`` directory for runnable scripts:

  - ``dimmer_http.py``: HTTP-only dimmer control
  - ``outlet_power.py``: outlet control + realtime values
  - ``timer_switch.py``: set countdown timer
  - ``snapshot.py``: capture a snapshot (video-capable insert)
