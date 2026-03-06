"""
WebSocket proxy tunneling.

Establishes a bi-directional bridge between the client and a remote WebSocket server.
Forwards text and binary frames and handles connection closing gracefully.
Simulates remote device tunneling used in BrowserStack-like infrastructure.
"""

import asyncio  # For asyncio.gather (run two bridge tasks concurrently)
import logging

from fastapi import WebSocket, WebSocketDisconnect  # WebSocket object; exception when client disconnects
from starlette.websockets import WebSocketState  # To check client state (CONNECTED, DISCONNECTED)
import websockets  # Library for connecting to upstream WebSocket server
from websockets.exceptions import ConnectionClosed  # When upstream closes connection

import config  # WS_UPSTREAM_BASE_URL

logger = logging.getLogger(__name__)


def _build_ws_upstream_url(path: str) -> str:
    """Build upstream WebSocket URL from path and config base; ensure scheme is ws:// or wss://."""
    base = (config.WS_UPSTREAM_BASE_URL or "wss://echo.websocket.org").rstrip("/")
    path = path if path.startswith("/") else f"/{path}"
    if not base.startswith(("ws://", "wss://")):
        base = "wss://" + base.replace("https://", "").replace("http://", "")
    return f"{base}{path}"


async def _bridge_client_to_upstream(
    client_ws: WebSocket,
    upstream_ws: websockets.WebSocketClientProtocol,
) -> None:
    """Forward frames from client to upstream until either side closes or disconnects."""
    try:
        while True:
            try:
                data = await client_ws.receive()  # Wait for message from client
            except WebSocketDisconnect:
                break
            if client_ws.client_state == WebSocketState.DISCONNECTED:
                break
            if "text" in data:
                await upstream_ws.send(data["text"])
            elif "bytes" in data:
                await upstream_ws.send(data["bytes"])
            elif data.get("type") == "websocket.disconnect":
                break
    except ConnectionClosed:
        pass
    except Exception as e:
        logger.debug("Client->upstream bridge error: %s", e)
    finally:
        try:
            await upstream_ws.close()
        except Exception:
            pass


async def _bridge_upstream_to_client(
    client_ws: WebSocket,
    upstream_ws: websockets.WebSocketClientProtocol,
) -> None:
    """Forward frames from upstream to client until either side closes or client disconnects."""
    try:
        async for message in upstream_ws:
            if client_ws.client_state != WebSocketState.CONNECTED:
                break
            if isinstance(message, str):
                await client_ws.send_text(message)
            else:
                await client_ws.send_bytes(message)
    except ConnectionClosed:
        pass
    except Exception as e:
        logger.debug("Upstream->client bridge error: %s", e)
    finally:
        try:
            if client_ws.client_state == WebSocketState.CONNECTED:
                await client_ws.close()
        except Exception:
            pass


async def websocket_tunnel(websocket: WebSocket, path: str) -> None:
    """
    WebSocket proxy tunnel: accept client connection, connect to upstream, run two concurrent bridges (client<->upstream).
    """
    await websocket.accept()  # Complete the WebSocket handshake with the client
    url = _build_ws_upstream_url(path)
    logger.info("[WS-PROXY] Connect %s -> %s", path or "/", url)

    try:
        async with websockets.connect(
            url,
            close_timeout=2,
            open_timeout=10,
        ) as upstream_ws:
            await asyncio.gather(
                _bridge_client_to_upstream(websocket, upstream_ws),
                _bridge_upstream_to_client(websocket, upstream_ws),
            )
    except asyncio.TimeoutError:
        logger.warning("[WS-PROXY] Upstream connect timeout: %s", url)
        try:
            await websocket.close(code=1011, reason="Upstream connection timeout")
        except Exception:
            pass
    except OSError as e:
        logger.warning("[WS-PROXY] Upstream connection error: %s — %s", url, e)
        try:
            await websocket.close(code=1011, reason="Upstream unreachable")
        except Exception:
            pass
    except Exception as e:
        logger.exception("[WS-PROXY] Tunnel error: %s", e)
        try:
            await websocket.close(code=1011, reason="Proxy error")
        except Exception:
            pass
    finally:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception:
            pass
        logger.info("[WS-PROXY] Disconnect %s", path or "/")
