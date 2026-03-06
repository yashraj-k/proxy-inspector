"""
Trace ID middleware.

Assigns a unique trace_id (UUID) and request start time to each request
for structured logging and observability. Must run first in the middleware
chain so trace_id and start_ns are available to all downstream middleware.
"""

import time  # For perf_counter_ns (high-resolution timer)
import uuid  # For generating unique trace IDs
from typing import Callable  # Type hint for call_next

from starlette.middleware.base import BaseHTTPMiddleware  # Base class for middleware with dispatch()
from starlette.requests import Request
from starlette.responses import Response


class TraceIdMiddleware(BaseHTTPMiddleware):
    """
    Sets request.state.trace_id (12-char UUID hex) and request.state.start_ns for each request.
    Used by the proxy and flakiness middleware for structured JSON logs.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request.state.trace_id = str(uuid.uuid4()).replace("-", "")[:12]  # Short ID for logs (e.g. "a1b2c3d4e5f6")
        request.state.start_ns = time.perf_counter_ns()  # Start time so downstream can compute elapsed_ms
        return await call_next(request)  # Pass request to next middleware or route
