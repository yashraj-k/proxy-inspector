"""
Infrastructure middleware for the proxy.

Provides latency simulation (network throttling), header injection,
trace IDs for observability, and optional flakiness (failure) simulation.
"""

from .flakiness import FlakinessSimulatorMiddleware  # Random 503/504 before upstream
from .headers import DebugHeaderMiddleware  # X-Proxy-Observed, X-Debug-Session-ID
from .latency import LatencySimulatorMiddleware  # asyncio.sleep delay
from .trace_id import TraceIdMiddleware  # trace_id and start_ns per request

__all__ = [
    "DebugHeaderMiddleware",
    "FlakinessSimulatorMiddleware",
    "LatencySimulatorMiddleware",
    "TraceIdMiddleware",
]
