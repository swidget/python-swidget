"""Tests for SwidgetWebsocket class.."""
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientSession, ClientWebSocketResponse, WSMessage, WSMsgType

from swidget.websocket import SwidgetWebsocket


@pytest.fixture
def swidget_websocket():
    """Mock SwidgetWebsocket object."""
    callback = AsyncMock()
    return SwidgetWebsocket(
        host="127.0.0.1",
        token_name="token_name",
        secret_key="secret_key",
        callback=callback,
        use_security=True,
    )


@pytest.mark.asyncio
async def test_connect(swidget_websocket):
    """Test that a connection to the websocket server can be made."""
    async with ClientSession() as session:
        swidget_websocket.session = session
        with patch.object(
            session, "ws_connect", new_callable=AsyncMock
        ) as mock_ws_connect, patch.object(
            swidget_websocket, "listen", new_callable=AsyncMock
        ):  # Mock listen to prevent side effects
            mock_ws_connect.return_value = AsyncMock(spec=ClientWebSocketResponse)
            mock_ws_connect.return_value.closed = False  # Simulate an open connection
            await swidget_websocket.connect()
            assert swidget_websocket.connected

            await swidget_websocket.disconnect()
            assert not swidget_websocket.connected


@pytest.mark.asyncio
async def test_send_str(swidget_websocket):
    """Test sending a string over the websocket."""
    async with ClientSession() as session:
        swidget_websocket.session = session
        with patch.object(
            session, "ws_connect", new_callable=AsyncMock
        ) as mock_ws_connect, patch.object(
            swidget_websocket, "listen", new_callable=AsyncMock
        ):
            mock_ws_connect.return_value = AsyncMock(spec=ClientWebSocketResponse)
            mock_ws_connect.return_value.closed = False  # Simulate an open connection
            await swidget_websocket.connect()
            await swidget_websocket.send_str("test message")
            mock_ws_connect.return_value.send_str.assert_awaited_with("test message")


@pytest.mark.asyncio
async def test_receive_message_or_raise(swidget_websocket):
    """Test for recieving a message."""
    async with ClientSession() as session:
        swidget_websocket.session = session
        with patch.object(
            session, "ws_connect", new_callable=AsyncMock
        ) as mock_ws_connect, patch.object(
            swidget_websocket, "listen", new_callable=AsyncMock
        ):
            ws_response = AsyncMock(spec=ClientWebSocketResponse)
            ws_response.closed = False  # Simulate an open connection
            ws_response.receive = AsyncMock(
                return_value=WSMessage(
                    type=WSMsgType.TEXT, data='{"key": "value"}', extra=""
                )
            )
            mock_ws_connect.return_value = ws_response
            await swidget_websocket.connect()
            message = await swidget_websocket.receive_message_or_raise()
            assert message == {"key": "value"}


@pytest.mark.asyncio
async def test_disconnect(swidget_websocket):
    """Test websocket disconnect."""
    async with ClientSession() as session:
        swidget_websocket.session = session
        with patch.object(
            session, "ws_connect", new_callable=AsyncMock
        ) as mock_ws_connect, patch.object(
            swidget_websocket, "listen", new_callable=AsyncMock
        ):
            mock_ws_connect.return_value = AsyncMock(spec=ClientWebSocketResponse)
            mock_ws_connect.return_value.closed = False  # Simulate an open connection
            await swidget_websocket.connect()
            assert swidget_websocket.connected
            await swidget_websocket.disconnect()
            assert not swidget_websocket.connected


@pytest.mark.asyncio
async def test_close(swidget_websocket):
    """Test the websocket being closed."""
    async with ClientSession() as session:
        swidget_websocket.session = session
        with patch.object(
            session, "ws_connect", new_callable=AsyncMock
        ) as mock_ws_connect, patch.object(
            swidget_websocket, "listen", new_callable=AsyncMock
        ):
            mock_ws_connect.return_value = AsyncMock(spec=ClientWebSocketResponse)
            mock_ws_connect.return_value.closed = False  # Simulate an open connection
            await swidget_websocket.connect()
            await swidget_websocket.close()
            assert not swidget_websocket.connected


@pytest.mark.asyncio
async def test_connect_and_listen(swidget_websocket):
    """Test connecting and listening."""
    async with ClientSession() as session:
        swidget_websocket.session = session
        with patch.object(
            session, "ws_connect", new_callable=AsyncMock
        ) as mock_ws_connect:
            ws_response = AsyncMock(spec=ClientWebSocketResponse)
            ws_response.closed = False  # Simulate an open connection
            mock_ws_connect.return_value = ws_response
            await swidget_websocket.connect()
            print(
                "WebSocket connected:", swidget_websocket.connected
            )  # Debug statement

            # Simulate receiving a message
            async def mock_receive():
                yield WSMessage(type=WSMsgType.TEXT, data='{"key": "value"}', extra="")
                yield WSMessage(type=WSMsgType.CLOSE, data=None, extra="")

            ws_response.receive = mock_receive().__anext__

            # Ensure connection is established before listening
            assert swidget_websocket.connected
