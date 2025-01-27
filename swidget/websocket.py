"""Module to handle websocket connections to Swidget devices."""
import asyncio
import logging
import socket
from typing import Any, Awaitable, Callable, Union

import aiohttp
from aiohttp import (
    ClientConnectionError,
    ClientWebSocketResponse,
    WSMsgType,
    WSServerHandshakeError,
)

_LOGGER = logging.getLogger(__name__)


class SwidgetWebsocket:
    """A websocket connection to a Swidget Device."""

    def __init__(
        self,
        host: str,
        token_name: str,
        secret_key: str,
        callback: Union[Callable[[Any], None], Callable[[Any], Awaitable[None]]],
        session: aiohttp.ClientSession | None = None,
        use_security: bool = True,
        retry_interval: int = 30,  # Initial retry interval in seconds
        max_retries: int = 200,  # Maximum number of reconnection attempts
    ):
        """Initialize the SwidgetWebsocket.

        Args:
            host: The hostname or IP address of the Swidget device.
            token_name: The name of the authentication token.
            secret_key: The secret key for authentication.
            callback: A callable that will be called with received messages.
            session: An optional aiohttp.ClientSession to use.
            use_security: Whether to use wss:// (True) or ws:// (False).
            retry_interval: Initial interval for reconnection attempts.
            max_retries: Maximum number of reconnection attempts.
        """
        self.host = host
        self.token_name = token_name or "x-secret-key"
        self.secret_key = secret_key or ""
        self.session = session or aiohttp.ClientSession()
        self.use_security = use_security
        self.callback = callback
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self.retry_count = 0
        self._verify_ssl = False
        self.uri = self._get_uri()

        # self._client= None
        self.is_running = True
        self._closing = False
        self._client: ClientWebSocketResponse | None = None
        self._receiver_task: asyncio.Task | None = None
        self._closing = False

    def _get_uri(self) -> str:
        """Generate the websocket URI."""
        protocol = "wss" if self.use_security else "ws"
        return (
            f"{protocol}://{self.host}/api/v1/sock?{self.token_name}={self.secret_key}"
        )

    async def connect(self) -> None:
        """Connect to the websocket server."""
        _LOGGER.debug("websocket.connect() called")

        if self.connected:
            _LOGGER.debug("Websocket already connected")
            return

        if self._client is not None:
            raise ConnectionError("Already connected")

        if not self.session:
            raise ConnectionError("No aiohttp session available")

        headers = {"Connection": "Upgrade", self.token_name: self.secret_key}

        try:
            _LOGGER.debug(f"Trying to connect to {self.host}")
            self._client = await self.session.ws_connect(
                url=self.uri,
                headers=headers,
                verify_ssl=self._verify_ssl,
                heartbeat=30,
            )
            self.retry_count = 0
            _LOGGER.debug("Websocket now connected")
        except (ClientConnectionError, WSServerHandshakeError):
            _LOGGER.error("Error connecting to websocket")
            self._client = None
        except socket.gaierror as e:
            _LOGGER.error(f"Error resolving host: {e}")
            self._client = None
        except Exception as e:
            _LOGGER.error(f"An unexpected error occurred: {e}")
            self._client = None

    async def send_str(self, message: str) -> None:
        """Send a string message through the websocket with retry attempts."""
        _LOGGER.debug("websocket.send_str() called")
        max_send_retries = 3
        for attempt in range(max_send_retries):
            try:
                if self._client is not None:
                    await self._client.send_str(message)
                    return
                else:
                    _LOGGER.warning("Websocket is not connected, not sending")
                    return
            except Exception as e:
                _LOGGER.warning(
                    f"Error sending message, attempt {attempt}/{max_send_retries}: {e}"
                )
                if attempt < max_send_retries - 1:
                    await asyncio.sleep(5**attempt)
                else:
                    _LOGGER.error(
                        f"Failed to send message after {max_send_retries} attempts."
                    )

    async def receive(self):
        """Receive a message from the WebSocket server."""
        _LOGGER.debug("websocket.receive() called")
        try:
            if self._client is not None:
                message = await self._client.receive()
                if message.type == WSMsgType.TEXT:
                    message_data = message.json()
                    _LOGGER.debug(f"[{self.host}] Received message: {message_data}")
                    return message_data
                elif message.type == WSMsgType.CLOSED:
                    _LOGGER.error("Websocket client is closed")
                    self._client = None
                elif message.type == WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error.")
                    self._client = None
        except Exception as e:
            _LOGGER.error(f"Error receiving message: {e}")

    async def close(self):
        """Close the WebSocket connection."""
        _LOGGER.debug("websocket.close() called")
        self.is_running = False
        self._closing = True
        if self._client is not None:
            await self._client.close()
        self._client = None
        if self.session and not self.session.closed:
            await self.session.close()

    async def reconnect(self):
        """Reconnect to the WebSocket server after a delay."""
        _LOGGER.debug("websocket.reconnect() called")
        if self.max_retries is not None and self.retry_count >= self.max_retries:
            _LOGGER.warning("Max retries reached. Stopping reconnect attempts.")
            self.is_running = False
            return

        self.retry_count += 1
        delay = self.retry_interval * (2 ** (self.retry_count - 1))
        _LOGGER.warning(
            f"Reconnecting in {delay} seconds (attempt {self.retry_count})..."
        )
        await asyncio.sleep(delay)
        await self.connect()

    async def run(self):
        """Run the WebSocket client to handle messages and reconnections."""
        while self.is_running:
            if self._client is None:
                await self.reconnect()
            if self._client is not None:
                message = await self.receive()
                if message and self.callback:
                    if asyncio.iscoroutinefunction(self.callback):
                        await self.callback(message)
                    else:
                        self.callback(message)

    def status(self) -> dict:
        """Return the current status of the websocket connection."""
        _LOGGER.debug("websocket.status() called")
        return {
            "host": self.host,
            "connected": self._client is not None,
            "closing": self._closing,
            "retry_interval": self.retry_interval,
            "max_retries": self.max_retries,
        }

    @property
    def connected(self) -> bool:
        """Return the status of the connection."""
        return self._client is not None and not self._client.closed

    def __repr__(self) -> str:
        """Return the representation."""
        prefix = "" if self.connected else "not "
        return f"{type(self).__name__}(ws_server_url={self.host}, {prefix}connected)"
