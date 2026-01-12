"""Example: Capture a snapshot from a video-capable device."""
import asyncio

from swidget import SwidgetDevice


async def main():
    """Retrieve and save a snapshot."""
    dev = SwidgetDevice(
        host="192.168.1.62",
        token_name="x-secret-key",
        secret_key="password",
        use_https=True,
        use_websockets=False,
    )
    await dev.update()
    img = await dev.get_snapshot_bytes(width=640, height=360)
    if img:
        with open("snapshot.jpg", "wb") as f:
            f.write(img)
    await dev.close()


if __name__ == "__main__":
    asyncio.run(main())
