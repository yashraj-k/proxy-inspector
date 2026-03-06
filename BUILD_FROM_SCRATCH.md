# Build This Project From Scratch

This document explains how to build the **High-Performance HTTP & WebSocket Proxy** from scratch and what each part of the code does.

---

## 1. What You’re Building

A **production-style HTTP/WebSocket proxy** that:

- Forwards all HTTP requests to a configurable upstream (e.g. JSONPlaceholder or a local target service).
- Tunnels WebSocket connections to an upstream WebSocket server.
- Adds **latency** (configurable delay) to simulate slow networks.
- Injects **debug headers** (e.g. `X-Proxy-Observed`, `X-Debug-Session-ID`) on outgoing requests.
- Optionally **fails a percentage of requests** (503/504) to test retries and resilience.
- Uses a **global connection pool** (one shared `httpx.AsyncClient`) for performance.
- Logs **structured JSON** (trace_id, method, path, status, latency) for observability.

---

## 2. Prerequisites

- **Python 3.10+**
- **pip** and **venv**
- (Optional) **Docker** and **Docker Compose** for running proxy + target service together

---

## 3. Project Layout (Create These First)

Create the following structure:

```
proxy-inspector/
├── main.py              # FastAPI app, routes, lifespan, logging
├── config.py            # Environment-based configuration
├── requirements.txt     # Dependencies
├── .env.example         # Example env vars
├── middleware/
│   ├── __init__.py      # Export middleware classes
│   ├── trace_id.py      # Sets trace_id and start_ns per request
│   ├── headers.py       # Injects debug headers into request.state
│   ├── latency.py       # Adds configurable delay
│   └── flakiness.py     # Random 503/504 before upstream
├── proxy/
│   ├── __init__.py      # Export proxy_http_request, websocket_tunnel
│   ├── http_proxy.py    # HTTP forwarding using shared client
│   └── websocket_proxy.py  # WebSocket tunnel to upstream
├── target_service/      # Optional: minimal upstream for testing
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── Dockerfile           # Proxy image
└── docker-compose.yml   # proxy + target-service
```

---

## 4. Step-by-Step: What Each File Does

### 4.1 `requirements.txt`

Lists dependencies:

- **fastapi** – Web framework (routes, middleware, WebSocket).
- **starlette** – Underlying ASGI app and middleware base.
- **uvicorn** – ASGI server to run the app.
- **httpx** – Async HTTP client for upstream requests (connection pooling).
- **websockets** – Client for connecting to upstream WebSocket servers.
- **python-dotenv** – Loads `.env` into `os.environ`.
- **python-json-logger** – Optional; formats proxy/flakiness logs as JSON.

### 4.2 `config.py` – What Each Line Does

| Line / block | Purpose |
|--------------|--------|
| `import os` | Read environment variables with `os.getenv()`. |
| `from dotenv import load_dotenv` / `load_dotenv()` | Load `.env` from the project root so later `os.getenv()` calls see those values. |
| `get_env_int(key, default)` | Read an env var, convert to int; return default if missing or invalid. |
| `get_env_float(key, default)` | Same for float; strips whitespace so values like `"20\n"` work. |
| `UPSTREAM_BASE_URL` | Base URL for HTTP proxy (e.g. `https://jsonplaceholder.typicode.com` or `http://target-service:8080`). |
| `LATENCY_SIMULATION_SECONDS` | Delay in seconds applied to every request (from `PROXY_LATENCY_MS` in ms, divided by 1000). |
| `UPSTREAM_TIMEOUT_SECONDS` | Timeout for upstream HTTP requests; after this, the proxy returns 504. |
| `WS_UPSTREAM_BASE_URL` | Base URL for WebSocket upstream (e.g. `wss://echo.websocket.org`). |
| `FLAKINESS_PERCENTAGE` | Percentage (0–100) of non-health requests to fail with 503/504; 0 = disabled. |

### 4.3 `main.py` – What Each Part Does

| Part | Purpose |
|------|--------|
| **Imports** | `logging`, `sys`, `asynccontextmanager`, `AsyncGenerator`, `httpx`, `FastAPI`, `Request`, `WebSocket`, `config`, middleware classes, `proxy_http_request`, `websocket_tunnel`. |
| **logging.basicConfig(...)** | Set default log level (INFO), format, and stdout. |
| **try/except pythonjsonlogger** | If installed, attach a JSON formatter to the `proxy` and `middleware.flakiness` loggers so their logs are one JSON object per line. |
| **lifespan(app)** | On startup: create one `httpx.AsyncClient` with connection limits and timeout, store it in `app.state.http_client`. On shutdown: `await app.state.http_client.aclose()`. |
| **app = FastAPI(..., lifespan=lifespan)** | Create the FastAPI app and register the lifespan so the shared client is created/closed with the app. |
| **app.add_middleware(...)** | Register middleware in order. Last added runs first (outermost). Order: Flakiness → Latency → Debug → TraceId. So: TraceId runs first (sets trace_id, start_ns), then Debug (debug_headers), then Latency (sleep), then Flakiness (maybe 503/504), then the route. |
| **@app.get("/health")** | Always return `{"status":"ok","service":"proxy"}`. Never failed by flakiness. |
| **@app.websocket("/ws/{path:path}")** | Accept WebSocket at `/ws/...` and delegate to `websocket_tunnel(websocket, path)`. |
| **@app.api_route("/{path:path}", methods=[...])** | Catch-all HTTP route; delegate to `proxy_http_request(request)` which uses `request.app.state.http_client`. |
| **if __name__ == "__main__"** | When run as `python main.py`, start uvicorn on `0.0.0.0:8000`. |

### 4.4 `middleware/trace_id.py`

- **TraceIdMiddleware**: For every request, set `request.state.trace_id` (12-char hex from UUID) and `request.state.start_ns` (current time in nanoseconds). Downstream code uses these for logging and for `X-Internal-Latency` (elapsed ms).

### 4.5 `middleware/headers.py`

- **DebugHeaderMiddleware**: Set `request.state.debug_headers` to a dict with `X-Proxy-Observed: True` and `X-Debug-Session-ID: <uuid>`. The HTTP proxy in `proxy/http_proxy.py` adds these to outgoing upstream requests.

### 4.6 `middleware/latency.py`

- **LatencySimulatorMiddleware**: Before calling the next handler, `await asyncio.sleep(config.LATENCY_SIMULATION_SECONDS)`. This simulates network delay without blocking other requests.

### 4.7 `middleware/flakiness.py`

- **FlakinessSimulatorMiddleware**: If path is `/health`, always call next. Otherwise, with probability `FLAKINESS_PERCENTAGE/100`, return 503 or 504 (50/50) with body `{"error":"Simulated upstream failure"}` and log a structured “simulated_failure” event. Otherwise call next. Failure happens before the request reaches the upstream.

### 4.8 `proxy/http_proxy.py` – What Each Part Does

| Part | Purpose |
|------|--------|
| **SKIP_HEADERS** | Set of header names not forwarded to upstream (host, connection, etc.). |
| **_build_upstream_url(path, query)** | Build full URL: `config.UPSTREAM_BASE_URL` + path + `?` + query. |
| **_forward_headers(request)** | Copy request headers except skip list; add `request.state.debug_headers` if set. |
| **_log_request(...)** | Log one line with trace_id, method, path, upstream_url, status_code, internal_latency_ms, timestamp, event (used for both success and error paths). |
| **proxy_http_request(request)** | Read body; get `client = request.app.state.http_client`; send request to upstream with `client.request(...)`. On success: copy status, headers, body; add `X-Internal-Latency`; call `_log_request`. On timeout: return 504 and log. On connection error: return 503 and log. On other errors: return 502 and log. |

### 4.9 `proxy/websocket_proxy.py` – What Each Part Does

| Part | Purpose |
|------|--------|
| **_build_ws_upstream_url(path)** | Build upstream WebSocket URL from `config.WS_UPSTREAM_BASE_URL` and path; ensure scheme is ws/wss. |
| **_bridge_client_to_upstream** | Loop: receive from client WebSocket; if text or bytes, send to upstream; stop on disconnect or upstream close. |
| **_bridge_upstream_to_client** | Loop: receive from upstream; send to client as text or bytes; stop when client disconnects or upstream closes. |
| **websocket_tunnel(websocket, path)** | Accept client WebSocket; connect to upstream URL; run `_bridge_client_to_upstream` and `_bridge_upstream_to_client` concurrently with `asyncio.gather`. On timeout or connection error, close client with an appropriate reason. |

---

## 5. How to Build and Run From Scratch

### 5.1 Local (no Docker)

```bash
# 1. Create project directory and virtual environment
mkdir proxy-inspector && cd proxy-inspector
python3.10 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Create requirements.txt (see repo) and install
pip install -r requirements.txt

# 3. Copy .env.example to .env and set UPSTREAM_BASE_URL, FLAKINESS_PERCENTAGE, etc.
cp .env.example .env

# 4. Run the app
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 5.2 With Docker (proxy + target service)

```bash
# From project root
docker compose up --build
```

- Proxy listens on host port 8000.
- `docker-compose.yml` sets `UPSTREAM_BASE_URL=http://target-service:8080` and optionally `FLAKINESS_PERCENTAGE=20`.
- Target service exposes only port 8080 inside the Docker network.

---

## 6. Quick Test Commands

| What you’re testing | Command |
|---------------------|--------|
| Health (no flakiness) | `curl -s http://localhost:8000/health` |
| HTTP proxy (local default upstream) | `curl -s http://localhost:8000/posts/1` |
| HTTP proxy (Docker target-service) | `curl -s http://localhost:8000/hello` |
| Observability header | `curl -sI http://localhost:8000/health` → check `X-Internal-Latency` |
| Flakiness (set FLAKINESS_PERCENTAGE=20, restart, run many times) | `for i in $(seq 1 30); do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/hello; done` |
| WebSocket | `websocat ws://localhost:8000/ws/` |

---

## 7. Summary: Request Flow (What Runs When)

1. **TraceIdMiddleware**: Sets `request.state.trace_id` and `request.state.start_ns`.
2. **DebugHeaderMiddleware**: Sets `request.state.debug_headers`.
3. **LatencySimulatorMiddleware**: `await asyncio.sleep(LATENCY_SIMULATION_SECONDS)`.
4. **FlakinessSimulatorMiddleware**: For non-health paths, with probability `FLAKINESS_PERCENTAGE%`, return 503/504 and stop; otherwise continue.
5. **Route**: Either `/health` (return JSON), `/ws/{path}` (WebSocket tunnel), or `/{path:path}` (HTTP proxy).
6. **HTTP proxy** (`proxy_http_request`): Build upstream URL, forward headers and body with `app.state.http_client`, return response with `X-Internal-Latency`, and log (trace_id, method, path, upstream_url, status_code, internal_latency_ms, timestamp, event).

Using this guide you can recreate the project from scratch and understand what each file and each part of the code is responsible for.
