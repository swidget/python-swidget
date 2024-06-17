"""This dumps the state/ summary/ name of the device."""
import logging
from collections import defaultdict, namedtuple

import asyncclick as click

from swidget.discovery import SwidgetDiscoveredDevice, discover_devices

Call = namedtuple("Call", "module method")


def default_to_regular(d):
    """Convert nested defaultdicts to regular ones.

    From https://stackoverflow.com/a/26496899
    """
    if isinstance(d, defaultdict):
        d = {k: default_to_regular(v) for k, v in d.items()}
    return d


@click.command()
@click.option("-d", "--debug", is_flag=True)
async def cli(debug):
    """Generate devinfo file for given device."""
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    discovered_devices: dict[str, SwidgetDiscoveredDevice] = await discover_devices(
        timeout=15
    )
    for mac, device in discovered_devices.items():
        click.echo(click.style(f"== {device.friendly_name}", bold=True))
        click.echo(f"\tIP Address: {device.host}")
        click.echo(f"\tDevice Type: {device.host_type}")
        click.echo(f"\tInsert Type: {device.insert_type}")
        print()


if __name__ == "__main__":
    cli()
