"""Tests for SwidgetWebsocket class."""
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientSession, ClientWebSocketResponse, WSMessage, WSMsgType

from swidget.websocket import SwidgetWebsocket


@pytest.fixture
async def swidget_websocket():
    """Mock SwidgetWebsocket object with a real session (created in async)."""
    callback = AsyncMock()
    async with ClientSession() as session:
        ws = SwidgetWebsocket(
            host="127.0.0.1",
            token_name="token_name",
            secret_key="secret_key",
            callback=callback,
            use_security=True,
            verify_ssl=True,
            session=session,
        )
        yield ws
        await ws.close()


@pytest.mark.asyncio
async def test_connect(swidget_websocket):
    """Test that a connection to the websocket server can be made."""
    with patch.object(
        swidget_websocket.session, "ws_connect", new_callable=AsyncMock
    ) as mock_ws_connect:
        mock_ws_connect.return_value = AsyncMock(spec=ClientWebSocketResponse)
        mock_ws_connect.return_value.closed = False
        await swidget_websocket.connect()
        assert swidget_websocket.connected
        await swidget_websocket.close()
        assert not swidget_websocket.connected


@pytest.mark.asyncio
async def test_send_str(swidget_websocket):
    """Test sending a string over the websocket."""
    mock_client = AsyncMock(spec=ClientWebSocketResponse)
    mock_client.closed = False
    swidget_websocket._client = mock_client
    await swidget_websocket.send_str("test message")
    mock_client.send_str.assert_awaited_with("test message")


@pytest.mark.asyncio
async def test_receive_text_message(swidget_websocket):
    """Test receiving a JSON text message."""
    ws_message = WSMessage(type=WSMsgType.TEXT, data='{"key": "value"}', extra="")
    mock_client = AsyncMock(spec=ClientWebSocketResponse)
    mock_client.closed = False
    mock_client.receive = AsyncMock(return_value=ws_message)
    swidget_websocket._client = mock_client

    message = await swidget_websocket.receive()
    assert message == {"key": "value"}


@pytest.mark.asyncio
async def test_disconnect(swidget_websocket):
    """Test websocket disconnect using close()."""
    mock_client = AsyncMock(spec=ClientWebSocketResponse)
    mock_client.closed = False
    swidget_websocket._client = mock_client
    await swidget_websocket.close()
    assert not swidget_websocket.connected
    mock_client.close.assert_awaited()


@pytest.mark.asyncio
async def test_close_closes_session(swidget_websocket):
    """Close should close session when present."""
    mock_client = AsyncMock(spec=ClientWebSocketResponse)
    mock_client.closed = False
    swidget_websocket._client = mock_client
    swidget_websocket.session = AsyncMock(spec=ClientSession)
    swidget_websocket.session.closed = False

    await swidget_websocket.close()

    mock_client.close.assert_awaited()
    swidget_websocket.session.close.assert_awaited()
    assert swidget_websocket.connected is False


@pytest.mark.asyncio
async def test_connect_sets_verify_ssl(swidget_websocket):
    """Connect should honor verify_ssl flag."""
    with patch.object(
        swidget_websocket.session, "ws_connect", new_callable=AsyncMock
    ) as mock_ws_connect:
        mock_ws_connect.return_value = AsyncMock(spec=ClientWebSocketResponse)
        mock_ws_connect.return_value.closed = False
        await swidget_websocket.connect()
        _, kwargs = mock_ws_connect.await_args
        assert kwargs["verify_ssl"] is True
