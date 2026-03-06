"""
Debug header injection middleware.

Injects X-Proxy-Observed and X-Debug-Session-ID into the request state
so that the proxy layer can add them to outgoing upstream requests.
This enables request tracing and simulates debugging sessions in
remote infrastructure tools.
"""

import uuid  # For generating a unique session ID per request
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Header names and values added to upstream requests for observability
PROXY_OBSERVED_HEADER = "X-Proxy-Observed"
PROXY_OBSERVED_VALUE = "True"
DEBUG_SESSION_HEADER = "X-Debug-Session-ID"


class DebugHeaderMiddleware(BaseHTTPMiddleware):
    """
    Sets request.state.debug_headers so the HTTP proxy can add X-Proxy-Observed and X-Debug-Session-ID to upstream requests.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        session_id = str(uuid.uuid4())  # New UUID per request (e.g. "550e8400-e29b-41d4-a716-446655440000")
        request.state.debug_headers = {
            PROXY_OBSERVED_HEADER: PROXY_OBSERVED_VALUE,
            DEBUG_SESSION_HEADER: session_id,
        }
        return await call_next(request)
