"""
Latency simulator middleware.

Simulates global network latency using asyncio.sleep() so that every request
passing through the proxy experiences configurable delay. This models the
network throttling behavior used in BrowserStack-like remote infrastructure.
"""

import asyncio  # For asyncio.sleep (non-blocking delay)
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import config  # LATENCY_SIMULATION_SECONDS


class LatencySimulatorMiddleware(BaseHTTPMiddleware):
    """
    Injects a configurable delay (asyncio.sleep) into every request.
    Delay is read from config.LATENCY_SIMULATION_SECONDS (default 100ms).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        await asyncio.sleep(config.LATENCY_SIMULATION_SECONDS)  # Block this request for N seconds (other requests unaffected)
        return await call_next(request)
