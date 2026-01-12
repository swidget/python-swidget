"""Example: HTTP-only dimmer control."""
import asyncio

from swidget import SwidgetDimmer


async def main():
    """Toggle a dimmer on and off using HTTP mode."""
    dev = SwidgetDimmer(
        host="192.168.1.50",
        token_name="x-secret-key",
        secret_key="password",
        use_https=True,
        use_websockets=False,
    )
    await dev.update()
    await dev.turn_on()
    await dev.turn_off()
    await dev.close()


if __name__ == "__main__":
    asyncio.run(main())
