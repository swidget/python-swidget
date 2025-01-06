"""Module to perform end-to-end tests on Swidget devices."""
import asyncio
import logging

import asyncclick as click

from swidget import DeviceType, InsertType, SwidgetDimmer

_LOGGER = logging.getLogger(__name__)


def setup_debug_logger():
    """Create a special logger to capture all informtion we may need to debug."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Add formatter to ch
    ch.setFormatter(formatter)

    # Add ch to logger
    logger.addHandler(ch)

    return logger


async def test_dimmer(host, password, use_https, use_websockets):
    """Run synthetic tests for the dimmer module."""
    _LOGGER.info("Starting test")
    try:
        dev = SwidgetDimmer(
            host=host,
            token_name="x-secret-key",
            secret_key=password,
            use_https=use_https,
            use_websockets=use_websockets,
        )
        assert dev._last_update == 0
        assert dev.use_https == use_https
        if use_https is True:
            uri_scheme = "https"
        else:
            uri_scheme = "http"
        assert dev.uri_scheme == uri_scheme
        assert dev.use_websockets == use_websockets
        if use_websockets is True:
            await dev.start()
            asyncio.create_task(dev.get_websocket().run())
        await dev.update()
        await asyncio.sleep(5)
        assert dev._friendly_name == "SFO-BATHROOM-SWIDGET-DIMMER"
        assert dev.device_type == DeviceType.Dimmer
        assert dev.version == "1.5.27"
        assert dev.is_outlet is False
        assert dev.is_switch is False
        assert dev.is_pana_switch is False
        assert dev.is_dimmer is True
        assert dev.is_dimmable is True

        assert dev.host_features == ["power", "level", "toggle"]
        assert dev.mac_address == "24a16074d25c"
        assert dev.model == "HK_PICO_1"
        assert dev.insert_type == InsertType.THM

        assert await dev.blink() == {"blink": True}
        assert await dev.ping() is True

        await dev.turn_off()
        await asyncio.sleep(1)
        assert dev.is_on is False

        await dev.turn_on()
        await asyncio.sleep(1)
        assert dev.is_on is True

        await dev.turn_off()
        await asyncio.sleep(1)
        assert dev.is_on is False
    except Exception:
        raise
    finally:
        await dev.stop()


async def test_dimmer_combinations(host, password):
    """Run a list of different dimmer tests."""
    await test_dimmer(host, password, False, False)
    await test_dimmer(host, password, True, False)
    await test_dimmer(host, password, False, True)
    await test_dimmer(host, password, True, True)


@click.command()
@click.argument("host")
@click.option("-p", "--password", is_flag=False)
@click.option("-d", "--debug", is_flag=True)
@click.option("-t", "--trace", is_flag=True)
@click.version_option(package_name="python-swidget")
async def cli(host, password, debug, trace):
    """Main function for CLI."""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    if trace:
        logging.basicConfig(level=logging.DEBUG - 5)

    await test_dimmer_combinations(host, password)


if __name__ == "__main__":
    cli()
