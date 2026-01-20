"""Example: Timer switch countdown."""
import asyncio

from swidget import SwidgetTimerSwitch


async def main():
    """Set a countdown timer on the switch."""
    dev = SwidgetTimerSwitch(
        host="192.168.1.61",
        token_name="x-secret-key",
        secret_key="password",
        use_https=True,
        use_websockets=False,
    )
    await dev.set_countdown_timer(20)
    await dev.close()


if __name__ == "__main__":
    asyncio.run(main())
