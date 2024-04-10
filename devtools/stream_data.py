"""A simple utility to stream websocket data from Swidget devices
"""
import json
import logging

from aiohttp import ClientSession, TCPConnector
import asyncclick as click

from swidget.websocket import SwidgetWebsocket


@click.command()
@click.argument("host")
@click.option("-p", "--password", is_flag=False)
@click.option("-d", "--debug", is_flag=True)
@click.version_option(package_name="python-swidget")
async def cli(host, password, debug):
    """Generate devinfo file for given device."""
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    headers = {"x-secret-key": password}
    connector = TCPConnector(force_close=True)
    _session = ClientSession(headers=headers, connector=connector)
    websocket = SwidgetWebsocket(host=host, token_name='x-secret-key', secret_key=password, session=_session, callback=print_message)
    try:
        print("Attempting to connect...")
        await websocket.connect()
        print("Now listening...")
        await websocket.listen()
    except:
        print("Error: Unable to connect to Swidget device")
        await websocket.close()


async def print_message(message):
    print(json.dumps(message, sort_keys=True, indent=2))


if __name__ == "__main__":
    cli()
