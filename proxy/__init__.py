"""
Proxy engine and WebSocket tunneling.

Provides HTTP request forwarding and WebSocket bi-directional bridging
for the developer infrastructure tool.
"""

from .http_proxy import proxy_http_request  # Catch-all HTTP proxy handler (uses app.state.http_client)
from .websocket_proxy import websocket_tunnel  # WebSocket tunnel to upstream

__all__ = ["proxy_http_request", "websocket_tunnel"]
