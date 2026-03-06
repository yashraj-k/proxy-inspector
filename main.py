"""
High-Performance HTTP and WebSocket Proxy.

Developer infrastructure tool that forwards HTTP requests and tunnels WebSocket
connections. Used for request tracing, latency simulation, and remote debugging
session simulation (e.g. BrowserStack-like environments).

Run with: uvicorn main:app --host 0.0.0.0 --port 8000
"""

# --- Standard library imports ---
import logging  # For structured and JSON logging (INFO level, format, handlers)
import sys  # For sending log output to stdout
from contextlib import asynccontextmanager  # For lifespan context manager (startup/shutdown)
from typing import AsyncGenerator  # Type hint for async generator (lifespan)

# --- Third-party imports ---
import httpx  # Async HTTP client used for connection-pooled upstream requests
from fastapi import FastAPI, Request, WebSocket  # Web framework: app, request object, WebSocket

# --- Local application imports ---
import config  # Environment-based settings (UPSTREAM_BASE_URL, timeouts, FLAKINESS_PERCENTAGE, etc.)
from middleware import (  # Custom middleware: flakiness, latency, debug headers, trace ID
    DebugHeaderMiddleware,
    FlakinessSimulatorMiddleware,
    LatencySimulatorMiddleware,
    TraceIdMiddleware,
)
from proxy import proxy_http_request, websocket_tunnel  # HTTP proxy handler and WebSocket tunnel

# --- Logging setup: default format for all loggers ---
logging.basicConfig(
    level=logging.INFO,  # Only INFO and above (WARNING, ERROR) are logged
    format="%(asctime)s %(levelname)s %(name)s %(message)s",  # Human-readable log line format
    stream=sys.stdout,  # Logs go to standard output (visible in terminal / container logs)
    datefmt="%Y-%m-%dT%H:%M:%S",  # ISO-like timestamp format
)
# --- Optional: structured JSON logging for proxy and flakiness (ELK, Datadog, Loki) ---
try:
    from pythonjsonlogger import jsonlogger  # Optional dependency: outputs log records as JSON

    json_handler = logging.StreamHandler(sys.stdout)  # Send JSON logs to stdout
    json_handler.setFormatter(  # Format log records as a single JSON object
        jsonlogger.JsonFormatter(
            "%(timestamp)s %(trace_id)s %(method)s %(path)s %(upstream_url)s %(status_code)s %(internal_latency_ms)s %(event)s %(message)s"
        )
    )
    for name in ("proxy", "middleware.flakiness"):  # Apply JSON formatter only to these loggers
        log = logging.getLogger(name)
        log.propagate = False  # Prevent duplicate lines (do not bubble up to root logger)
        log.addHandler(json_handler)
        log.setLevel(logging.INFO)
except ImportError:  # If python-json-logger is not installed, skip JSON logging
    pass

logger = logging.getLogger(__name__)  # Logger for this module (main)


# --- Lifespan: runs once when the app starts and once when it shuts down ---
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create global HTTP client on startup; close on shutdown."""
    if config.FLAKINESS_PERCENTAGE > 0:  # Log when flakiness simulator is active
        logger.info("Flakiness simulator enabled: %.1f%% of requests may return 503/504", config.FLAKINESS_PERCENTAGE)
    limits = httpx.Limits(max_connections=1000, max_keepalive_connections=200)  # Connection pool size and keep-alive
    timeout = httpx.Timeout(config.UPSTREAM_TIMEOUT_SECONDS)  # Timeout for each upstream request
    app.state.http_client = httpx.AsyncClient(  # Store shared client so all proxy requests reuse it
        limits=limits,
        timeout=timeout,
    )
    yield  # Application runs here (handles requests)
    await app.state.http_client.aclose()  # On shutdown: close the client and release connections


# --- FastAPI application instance ---
app = FastAPI(
    title="HTTP/WebSocket Proxy",
    description="High-performance proxy with latency simulation and observability",
    version="1.0.0",
    lifespan=lifespan,  # Use the lifespan above for startup/shutdown
)

# --- Middleware order: last added runs first (outermost). Execution: TraceId -> Debug -> Latency -> Flakiness -> route ---
app.add_middleware(FlakinessSimulatorMiddleware)  # Outermost: may return 503/504 before hitting upstream
app.add_middleware(LatencySimulatorMiddleware)   # Adds configurable delay (PROXY_LATENCY_MS)
app.add_middleware(DebugHeaderMiddleware)        # Injects X-Proxy-Observed, X-Debug-Session-ID into request.state
app.add_middleware(TraceIdMiddleware)            # Innermost (runs first): sets trace_id and start_ns for logging


# --- Health check route: always returns 200; never affected by flakiness ---
@app.get("/health")
async def health() -> dict:
    """Health check for load balancers and container orchestration."""
    return {"status": "ok", "service": "proxy"}


# --- WebSocket tunnel: must be registered before catch-all so /ws/... is matched ---
@app.websocket("/ws/{path:path}")
async def websocket_proxy(websocket: WebSocket, path: str) -> None:
    """
    Tunnel WebSocket connection to upstream server.
    path is the upstream path (e.g. '' or 'echo'). Full URL is built from WS_UPSTREAM_BASE_URL.
    """
    await websocket_tunnel(websocket, path)  # Delegate to proxy/websocket_proxy.py


# --- Catch-all HTTP proxy: forward all methods to upstream (registered after /ws/ so paths don't collide) ---
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_catch_all(request: Request, path: str):
    """Forward HTTP request to configured upstream; path and query are forwarded; X-Internal-Latency is added."""
    return await proxy_http_request(request)  # Delegate to proxy/http_proxy.py (uses app.state.http_client)


# --- Entry point when running this file directly (e.g. python main.py) ---
if __name__ == "__main__":
    import uvicorn  # ASGI server
    uvicorn.run(
        "main:app",  # Application object in main module
        host="0.0.0.0",  # Bind to all interfaces (required for EC2/Docker)
        port=config.PORT,
        reload=False,
    )
