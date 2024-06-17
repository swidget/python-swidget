"""This dumps the state/ summary/ name of the device."""
import json
import logging
from collections import defaultdict, namedtuple

import asyncclick as click
from aiohttp import ClientSession, TCPConnector, client_exceptions

Call = namedtuple("Call", "module method")


def default_to_regular(d):
    """Convert nested defaultdicts to regular ones.

    From https://stackoverflow.com/a/26496899
    """
    if isinstance(d, defaultdict):
        d = {k: default_to_regular(v) for k, v in d.items()}
    return d


@click.command()
@click.argument("host")
@click.option("-p", "--password", is_flag=False)
@click.option("-d", "--debug", is_flag=True)
async def cli(host, password, debug):
    """Generate devinfo file for given device."""
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    headers = {}
    connector = TCPConnector(force_close=True)
    _session = ClientSession(headers=headers, connector=connector)

    # Get Summary Info
    try:
        async with _session.get(
            url=f"http://{host}/api/v1/summary",
            ssl=False,
        ) as response:
            summary = await response.json()
        click.echo(click.style("== Summary info ==", bold=True))
        click.echo(json.dumps(summary, sort_keys=True, indent=2))
        click.echo()

        # Get State Info
        async with _session.get(
            url=f"http://{host}/api/v1/state", ssl=False
        ) as response:
            state = await response.json()
        click.echo(click.style("== State info ==", bold=True))
        click.echo(json.dumps(state, sort_keys=True, indent=2))

        # Get Name Info
        async with _session.get(
            url=f"http://{host}/api/v1/name", ssl=False
        ) as response:
            name = await response.json()
        await _session.close()
        click.echo(click.style("== Name ==", bold=True))
        click.echo(json.dumps(name, sort_keys=True, indent=2))

        final = {"state": state, "summary": summary, "name": name}
        save_to = f"{summary['model']}_{summary['version']}.json"
        save = click.prompt(f"Do you want to save the above content to {save_to} (y/n)")
        if save == "y":
            click.echo(f"Saving info to {save_to}")

            with open(save_to, "w") as f:
                json.dump(final, f, sort_keys=True, indent=2)
                f.write("\n")
        else:
            click.echo("Not saving.")
    except client_exceptions.ClientConnectorError:
        await _session.close()
        click.echo("Error: Unable to connect to Swidget device")


if __name__ == "__main__":
    cli()
