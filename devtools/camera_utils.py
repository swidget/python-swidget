"""Module to do some basic camera debugging."""
import logging
from pprint import pprint

import asyncclick as click

from swidget import SwidgetDevice


@click.command()
@click.argument("host")
@click.option("-p", "--password", is_flag=False)
@click.option("-d", "--debug", is_flag=True)
async def cli(host, password, debug):
    """Generate devinfo file for given device."""
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    device = SwidgetDevice(
        host=host,
        token_name="x-secret-key",
        secret_key=password,
        use_https=False,
        use_websockets=False,
    )

    await device.update()
    await device.get_device_config()
    pprint(device.device_config.config)
    print(device.available_streams_types)
    print(device.stream_url)
    print(device.snapshot_url)
    snapshot_1 = await device.get_snapshot_bytes()
    print(len(snapshot_1))
    snapshot_2 = await device.get_snapshot_bytes(1440, 1440)
    print(len(snapshot_2))
    snapshot_3 = await device.get_snapshot_bytes(2048, 2048)
    print(len(snapshot_3))
    await device.close()


if __name__ == "__main__":
    cli()
