"""python-swidget cli tool."""
import asyncio
import logging
import sys
from pprint import pformat as pf
from typing import cast

import asyncclick as click

from swidget import (
    discover_devices,
    discover_single,
    SwidgetDevice,
    SwidgetDimmer,
    SwidgetSwitch,
    SwidgetOutlet,
    SwidgetTimerSwitch
)

TYPE_TO_CLASS = {
    "dimmer": SwidgetDimmer,
    "switch": SwidgetSwitch,
    "outlet": SwidgetOutlet,
    "pana_switch": SwidgetTimerSwitch
}

click.anyio_backend = "asyncio"


pass_dev = click.make_pass_decorator(SwidgetDevice)


@click.group(invoke_without_command=True)
@click.option(
    "--host",
    envvar="SWIDGET_HOST",
    required=False,
    help="The host name or IP address of the device to connect to.",
)
@click.option(
    "--password",
    envvar="SWIDGET_PASSWORD",
    required=False,
    help="The password of the device to connect to.",
)
@click.option("-d", "--debug",
    envvar="SWIDGET_DEBUG",
    default=False,
    is_flag=True)
@click.option(
    "--type",
    envvar="SWIDGET_TYPE",
    default=None,
    type=click.Choice(list(TYPE_TO_CLASS), case_sensitive=False),
)
@click.version_option(package_name="python-swidget")
@click.pass_context
async def cli(ctx, host, password, debug, type):
    """A tool for controlling Swidget smart home devices."""  # noqa
    # no need to perform any checks if we are just displaying the help
    if sys.argv[-1] == "--help":
        # Context object is required to avoid crashing on sub-groups
        ctx.obj = SwidgetDevice(None)
        return

    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if ctx.invoked_subcommand == "discover":
        return

    if host is None:
        click.echo("No host name given, trying discovery..")
        await ctx.invoke(discover)
        return

    if type is not None:
        dev = TYPE_TO_CLASS[type](host, password, False, False)
    else:
        click.echo("No --type defined, discovering..")
        dev = await discover_single(host, password, False, False)

    await dev.update()
    ctx.obj = dev

    if ctx.invoked_subcommand is None:
        await ctx.invoke(state)


@cli.group()
@pass_dev
def wifi(dev):
    """Commands to control wifi settings."""

@wifi.command()
@click.argument("ssid")
@click.option("--password", prompt=True, hide_input=True)
@click.option("--keytype", default=3)
@pass_dev
async def join(dev: SwidgetDevice, ssid, password, keytype):
    """Join the given wifi network."""
    click.echo(f"Asking the device to connect to {ssid}..")
    res = await dev.wifi_join(ssid, password, keytype=keytype)
    click.echo(
        f"Response: {res} - if the device is not able to join the network, it will revert back to its previous state."
    )

    return res


@cli.command()
@click.option("--timeout", default=5, required=False)
@click.pass_context
async def discover(ctx, timeout):
    """Discover devices in the network."""
    click.echo(f"Discovering devices via SSDP...waiting up to {timeout} seconds")

    devices = await discover_devices(timeout)
    for device in devices.values():
        click.echo(f"{device.host}[{device.mac}] - {device.friendly_name}")

@cli.command()
@pass_dev
async def hwinfo(dev):
    """Print out full system information."""
    click.echo(click.style("== HW info ==", bold=True))
    click.echo(pf(dev.hw_info))
    return dev.hw_info


@cli.command()
@pass_dev
async def state(dev: SwidgetDevice):
    """Print out device state and versions."""
    click.echo(click.style(f"== {dev.friendly_name} - {dev.model} ==", bold=True))
    click.echo(f"\tHost: {dev.ip_address}")
    click.echo(
        click.style(
            "\tDevice state: {}\n".format("ON" if dev.is_on else "OFF"),
            fg="green" if dev.is_on else "red",
        )
    )

    click.echo(click.style("\t== Generic information ==", bold=True))
    click.echo(f"\tHardware:     {dev.hw_info['model']}")
    click.echo(f"\tSoftware:     {dev.hw_info['version']}")
    click.echo(f"\tMAC (rssi):   {dev.mac_address} ({dev.rssi})")

    click.echo(click.style("\n\t== Current State ==", bold=True))
    for info_name, info_data in dev.realtime_values.items():
        if isinstance(info_data, list):
            click.echo(f"\t{info_name}:")
            for item in info_data:
                click.echo(f"\t\t{item}")
        else:
            click.echo(f"\t{info_name}: {info_data}")

    click.echo(click.style("\n\t== Host Features ==", bold=True))
    for function in dev.host_features:
        click.echo(click.style(f"\t+ {function}", fg="green"))


    click.echo(click.style("\n\t== Insert Features ==", bold=True))
    for function in dev.insert_features:
        click.echo(click.style(f"\t+ {function}", fg="green"))



@cli.command()
@pass_dev
@click.argument("assembly")
@click.argument("component")
@click.argument("function")
@click.argument("command")
async def raw_command(dev: SwidgetDevice, assembly, component, function, command):
    """Run a raw command on the device."""
    import ast

    if parameters is not None:
        parameters = ast.literal_eval(parameters)

    res = await dev.send_command(assembly, component, function, command)

    click.echo(res)
    return res



@cli.command()
@click.argument("brightness", type=click.IntRange(0, 100), default=None, required=False)
@pass_dev
async def brightness(dev: SwidgetDimmer, brightness: int):
    """Get or set brightness."""
    if not dev.is_dimmer:
        click.echo("This device does not support brightness.")
        return

    if brightness is None:
        click.echo(f"Brightness: {dev.brightness}")
    else:
        click.echo(f"Setting brightness to {brightness}")
        return await dev.set_brightness(brightness)


@cli.command()
@pass_dev
async def blink(dev):
    """Set the device insert to blink"""
    click.echo(f"Requesting the device to blink")
    return await dev.blink()


@cli.command()
@pass_dev
async def on(dev: SwidgetDevice):
    """Turn the device on."""
    click.echo(f"Turning on {dev.friendly_name}")
    return await dev.turn_on()


@cli.command()
@pass_dev
async def off(dev: SwidgetDevice):
    """Turn the device off."""
    click.echo(f"Turning off {dev.friendly_name}")
    return await dev.turn_off()


if __name__ == "__main__":
    cli()
