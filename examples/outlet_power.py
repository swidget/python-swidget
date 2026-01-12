"""Example: Outlet power reading and toggle."""
import asyncio

from swidget import SwidgetOutlet


async def main():
    """Fetch realtime values and toggle an outlet."""
    dev = SwidgetOutlet(
        host="192.168.1.60",
        token_name="x-secret-key",
        secret_key="password",
        use_https=True,
        use_websockets=False,
    )
    await dev.update()
    print("Realtime values:", dev.realtime_values)
    await dev.turn_on()
    await dev.turn_off()
    await dev.close()


if __name__ == "__main__":
    asyncio.run(main())
