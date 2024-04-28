import asyncio
import aiohttp
from aiohttp import ClientWebSocketResponse, WSMsgType
import logging
import socket
from typing import Any

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
        self.host = host
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
        return self._client

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

        if self._client is not None:
            raise ConnectionError("Already connected")

        if not self.session:
            raise ConnectionError("No aiohttp session available")

        try:
            _LOGGER.debug("Trying to connect")
            self._client = await self.session.ws_connect(url=self.uri, headers=self.headers, verify_ssl=self._verify_ssl, heartbeat=30)
            _LOGGER.debug("Websocket now connected")
        except aiohttp.WSServerHandshakeError as handshake_error:
            _LOGGER.error(f"Error occurred during websocket handshake: {handshake_error}")
            raise
        except aiohttp.ClientConnectionError as connection_error:
            _LOGGER.error(f"Error connecting to the websocket server: {connection_error}")
            raise
        except socket.gaierror as gai_error:
            _LOGGER.error(f"Error resolving host: {gai_error}")
            raise
        except Exception as e:
            _LOGGER.error(f"An unexpected error occurred: {e}")
            raise
        self._receiver_task = asyncio.ensure_future(self.listen())

    async def close(self) -> None:
        _LOGGER.debug("websocket.close() called")
        if self._client is not None and not self._client.closed:
            await self._client.close()
        self._client = None

    async def disconnect(self) -> None:
        await self.close()

    async def send_str(self, message):
        """Send a message through the websocket."""
        _LOGGER.debug("websocket.send_str() called")
        if not self.connected:
            raise ConnectionError
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
                _LOGGER.debug(f"Received from websocket: {message_data}")
                await self.callback(message_data)

            if message.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.CLOSING,
            ):
                _LOGGER.error("Connection to the Swidget WebSocket on has been closed")

    async def receive_message_or_raise(self) -> Any:
        """Receive ONE (raw) message or raise."""
        assert self._client
        ws_msg = await self._client.receive()

        if ws_msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
            raise ConnectionError("Connection was closed.")

        if ws_msg.type == WSMsgType.ERROR:
            raise ConnectionError

        if ws_msg.type != WSMsgType.TEXT:
            raise ValueError(
                f"Received non-Text message: {ws_msg.type}: {ws_msg.data}"
            )

        try:
            msg = ws_msg.json()
        except TypeError as err:
            raise TypeError(f"Received unsupported JSON: {err}") from err
        except ValueError as err:
            raise ValueError("Received invalid JSON.") from err

        _LOGGER.debug(f"Received message:\n{msg}\n")
        return msg

    def __repr__(self) -> str:
        """Return the representation."""
        prefix = "" if self.connected else "not "
        return f"{type(self).__name__}(ws_server_url={self.host}, {prefix}connected)"