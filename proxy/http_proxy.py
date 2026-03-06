"""
HTTP proxy forwarding logic.

Forwards incoming requests to the configured upstream using a shared
httpx.AsyncClient (app.state.http_client), preserving method, headers,
query params, and body. Measures internal latency and handles upstream
failures (timeout → 504, connection refused → error response).
Logs structured JSON for observability (ELK, Datadog, Loki, CloudWatch).
"""

import logging  # For structured/JSON log output
import time  # For measuring request duration (perf_counter_ns)
from datetime import datetime, timezone  # For UTC timestamp in logs
from typing import Dict  # Type hint for headers dict

import httpx  # Async HTTP client (used via request.app.state.http_client)
from fastapi import Request, Response  # Request object and generic Response
from starlette.responses import JSONResponse  # For error responses with JSON body

import config  # UPSTREAM_BASE_URL, etc.

logger = logging.getLogger(__name__)  # Logger for this module

# Headers we do not forward to upstream (hop-by-hop or proxy-specific; RFC 2616)
SKIP_HEADERS = frozenset(
    {
        "host",  # Upstream has its own host
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)

INTERNAL_LATENCY_HEADER = "X-Internal-Latency"  # Response header added to every proxied response (ms)


def _build_upstream_url(path: str, query: str) -> str:
    """Build full upstream URL from base URL, path, and query string."""
    base = config.UPSTREAM_BASE_URL.rstrip("/")  # Avoid double slash
    path = path if path.startswith("/") else f"/{path}"  # Ensure path starts with /
    url = f"{base}{path}"
    if query:
        url = f"{url}?{query}"  # Append query string
    return url


def _forward_headers(request: Request) -> Dict[str, str]:
    """Build headers for the upstream request: copy incoming (except skip list) and add debug headers from request.state."""
    headers: Dict[str, str] = {}
    for name, value in request.headers.items():
        if name.lower() in SKIP_HEADERS:
            continue
        headers[name] = value
    if hasattr(request.state, "debug_headers"):  # Set by DebugHeaderMiddleware
        headers.update(request.state.debug_headers)
    return headers


def _log_request(
    request: Request,
    upstream_url: str,
    status_code: int,
    internal_latency_ms: int,
    event: str = "proxied",
) -> None:
    """Emit structured JSON log (or standard log) with trace_id, method, path, upstream_url, status_code, latency, timestamp, event."""
    trace_id = getattr(request.state, "trace_id", "")
    logger.info(
        event,
        extra={
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path or "/",
            "upstream_url": upstream_url,
            "status_code": status_code,
            "internal_latency_ms": internal_latency_ms,
            "timestamp": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event,
        },
    )


async def proxy_http_request(request: Request) -> Response:
    """
    Catch-all HTTP proxy handler. Uses app.state.http_client; forwards to upstream; adds X-Internal-Latency; logs; handles errors.
    """
    start_ns = time.perf_counter_ns()  # Start time for internal latency
    path = request.url.path
    query = request.url.query
    method = request.method
    url = _build_upstream_url(path, query)

    headers = _forward_headers(request)

    try:
        body = await request.body()  # Read raw body (bytes)
    except Exception as e:
        logger.exception("Failed to read request body: %s", e)
        return JSONResponse(
            status_code=400,
            content={"error": "Failed to read request body", "detail": str(e)},
        )

    client: httpx.AsyncClient = request.app.state.http_client  # Global connection-pooled client from lifespan

    try:
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            content=body,
        )
    except httpx.TimeoutException:
        logger.warning("Upstream timeout: %s %s", method, url)
        elapsed_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
        _log_request(request, url, 504, elapsed_ms, event="upstream_timeout")
        return Response(
            status_code=504,
            content=b'{"error":"Gateway Timeout","detail":"Upstream request timed out"}',
            media_type="application/json",
            headers={INTERNAL_LATENCY_HEADER: str(elapsed_ms)},
        )
    except (ConnectionRefusedError, OSError, httpx.ConnectError) as e:
        logger.warning("Upstream connection error: %s %s — %s", method, url, e)
        elapsed_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
        _log_request(request, url, 503, elapsed_ms, event="upstream_connection_error")
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service Unavailable",
                "detail": "Upstream connection refused or unreachable",
                "upstream": config.UPSTREAM_BASE_URL,
            },
            headers={INTERNAL_LATENCY_HEADER: str(elapsed_ms)},
        )
    except Exception as e:
        logger.exception("Upstream request failed: %s %s", method, url)
        elapsed_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
        _log_request(request, url, 502, elapsed_ms, event="upstream_error")
        return JSONResponse(
            status_code=502,
            content={"error": "Bad Gateway", "detail": str(e)},
            headers={INTERNAL_LATENCY_HEADER: str(elapsed_ms)},
        )

    elapsed_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
    _log_request(request, url, response.status_code, elapsed_ms)

    response_headers: Dict[str, str] = dict(response.headers)
    response_headers[INTERNAL_LATENCY_HEADER] = str(elapsed_ms)

    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response_headers,
        media_type=response.headers.get("content-type"),
    )
