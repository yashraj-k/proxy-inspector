"""
Flakiness simulator middleware.

Randomly fails a configurable percentage of requests with 503 or 504
before hitting the upstream, to simulate unstable infrastructure
and test client resilience (e.g. retries, circuit breakers).
"""

import random  # For random.random() to decide whether to fail this request
import time  # For elapsed_ms (request.state.start_ns)
from datetime import datetime, timezone  # For timestamp in logs
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

import config  # FLAKINESS_PERCENTAGE

# Path that must never be failed (health checks for load balancers)
HEALTH_PATH = "/health"

import logging

logger = logging.getLogger(__name__)


def _should_simulate_failure() -> bool:
    """Return True with probability FLAKINESS_PERCENTAGE/100 (0% or 100% handled as special cases)."""
    if config.FLAKINESS_PERCENTAGE <= 0:
        return False
    if config.FLAKINESS_PERCENTAGE >= 100:
        return True
    return random.random() * 100 < config.FLAKINESS_PERCENTAGE  # e.g. 20% -> True 20% of the time


def _pick_status() -> int:
    """Return 503 or 504 with equal probability (50/50)."""
    return 503 if random.random() < 0.5 else 504


def _elapsed_ms(request: Request) -> int:
    """Compute milliseconds since request start (request.state.start_ns set by TraceIdMiddleware)."""
    if not hasattr(request.state, "start_ns"):
        return 0
    return (time.perf_counter_ns() - request.state.start_ns) // 1_000_000


def _log_simulated_failure(request: Request, status_code: int, elapsed_ms: int) -> None:
    """Emit structured log for simulated failure (event=simulated_failure) for ELK/Datadog/Loki."""
    trace_id = getattr(request.state, "trace_id", "")
    logger.info(
        "simulated_failure",
        extra={
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path or "/",
            "upstream_url": "",
            "status_code": status_code,
            "internal_latency_ms": elapsed_ms,
            "timestamp": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": "simulated_failure",
        },
    )


class FlakinessSimulatorMiddleware(BaseHTTPMiddleware):
    """
    Randomly returns 503 or 504 for FLAKINESS_PERCENTAGE of requests. Skips /health. Failure happens before upstream.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == HEALTH_PATH:  # Never fail health checks
            return await call_next(request)
        if not _should_simulate_failure():  # Decide randomly whether to fail this request
            return await call_next(request)
        status_code = _pick_status()  # 503 or 504
        elapsed_ms = _elapsed_ms(request)
        _log_simulated_failure(request, status_code, elapsed_ms)
        return JSONResponse(
            status_code=status_code,
            content={"error": "Simulated upstream failure"},
            headers={"X-Internal-Latency": str(elapsed_ms)},
        )
