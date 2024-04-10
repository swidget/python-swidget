import asyncio
import aiohttp
from aiohttp import ClientWebSocketResponse, WSMsgType
import logging
import socket

_LOGGER = logging.getLogger(__name__)


async def cancel_task(*tasks: asyncio.Task | None) -> None:
    """Cancel task(s)."""
    for task in tasks:
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


class SwidgetWebsocket:
    """A websocket connection to a Swidget Device"""

    # pylint: disable=too-many-instance-attributes
    _client: aiohttp.ClientWebSocketResponse | None = None

    def __init__(
        self,
        host,
        token_name,
        secret_key,
        callback,
        session=None,
        use_security=True,
    ):

        self.session = session or aiohttp.ClientSession()
        self.use_security = use_security
        self.uri = self.get_uri(host, token_name, secret_key)
        self.callback = callback
        self._verify_ssl = False
        self._state = None
        self.failed_attempts = 0
        self._error_reason = None
        self.headers = {'Connection': 'Upgrade'}
        self._receiver_task: asyncio.Task | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None and not self._client.closed

    @property
    def websocket(self) -> ClientWebSocketResponse | None:
        """Return the web socket."""
        return self._ws

    def get_uri(self, host, token_name, secret_key):
        """Generate the websocket URI"""
        if self.use_security:
            return f"wss://{host}/api/v1/sock?{token_name}={secret_key}"
        else:
            return f"ws://{host}/api/v1/sock?{token_name}={secret_key}"

    async def connect(self) -> None:
        _LOGGER.debug("websocket.connect() called")
        """Create a new connection and, optionally, start the monitor."""
        await cancel_task(self._receiver_task)
        if self.connected:
            _LOGGER.debug("Websocket already connected")
            return

        if not self.session:
            raise

        try:
            self._client = await self.session.ws_connect(url=self.uri, headers=self.headers, verify_ssl=self._verify_ssl, heartbeat=30)
            _LOGGER.debug("Websocket now connected")
        except (
            aiohttp.WSServerHandshakeError,
            aiohttp.ClientConnectionError,
            socket.gaierror,
        ) as exception:
            msg = (
                "Error occurred while communicating with WLED device"
                f" on WebSocket at {self.host}"
            )
            raise(msg)
        self._receiver_task = asyncio.ensure_future(self.listen())

    async def close(self) -> None:
        _LOGGER.debug("websocket.close() called")
        if not self._client or not self.connected:
            return
        await self._client.close()

    async def send_str(self, message):
        """Send a message through the websocket."""
        _LOGGER.debug("websocket.send_str() called")
        message = str(message)
        _LOGGER.debug(f"Sending messsage over websocket: {message}")
        await self._client.send_str(f'{message}')

    async def listen(self):
        _LOGGER.debug("websocket.listen() called")
        if not self._client or not self.connected:
            raise

        while not self._client.closed:
            message = await self._client.receive()

            if message.type == aiohttp.WSMsgType.ERROR:
                raise

            if message.type == aiohttp.WSMsgType.TEXT:
                message_data = message.json()
                await self.callback(message_data)

            if message.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.CLOSING,
            ):
                _LOGGER.debug("Connection to the Swidget WebSocket on has been closed")