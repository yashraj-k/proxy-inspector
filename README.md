# High-Performance HTTP & WebSocket Proxy

A production-style developer infrastructure tool that acts as an HTTP and WebSocket proxy with latency simulation, observability, and resilience. Suited for Backend Engineer roles (e.g. BrowserStack) where networking, async concurrency, and operational visibility matter.

## Features

- **Proxy engine**: Catch-all `/{path:path}` forwarding for all HTTP methods via a **global connection-pooled** `httpx.AsyncClient`
- **Middleware**: Configurable latency simulation (`PROXY_LATENCY_MS`), debug header injection (`X-Proxy-Observed`, `X-Debug-Session-ID`), optional **flakiness simulator** (random 503/504)
- **WebSocket tunneling**: Bi-directional bridge at `/ws/{path:path}` for text and binary frames
- **Observability**: **Structured JSON logging** (trace_id, method, path, upstream_url, status_code, internal_latency_ms, timestamp), `X-Internal-Latency` response header
- **Resilience**: 504 on upstream timeout, 503 on connection refused / connect errors; simulated failures for testing retries and circuit breakers

## Technology Stack

- Python 3.10+
- FastAPI, Starlette, Uvicorn
- HTTPX (AsyncClient), websockets, asyncio

## Project Structure

```
.
├── main.py              # FastAPI app, routes, logging config
├── config.py            # Env-based settings (upstream URL, latency, timeout)
├── requirements.txt
├── middleware/
│   ├── __init__.py
│   ├── latency.py      # Latency simulator (asyncio.sleep)
│   ├── headers.py      # Debug/session header injection
│   ├── trace_id.py     # Trace ID + start time for structured logs
│   └── flakiness.py    # Optional random 503/504 failure injection
├── proxy/
│   ├── __init__.py
│   ├── http_proxy.py   # HTTP forward + observability + error handling
│   └── websocket_proxy.py  # WebSocket tunnel
├── target_service/      # Minimal HTTP service for local/docker testing
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── Dockerfile           # Proxy image
├── docker-compose.yml   # proxy + target-service
├── deploy/              # AWS EC2 deployment
│   ├── run.sh           # Production run script (PORT, workers)
│   ├── install-on-ec2.sh # One-time install on EC2
│   ├── proxy-inspector.service  # Systemd unit
│   └── README.md
├── docs/
│   └── HOST_ON_AWS_FREE.md  # Step-by-step EC2 free tier hosting
├── .env.example
└── README.md
```

## Deploy to AWS EC2

The project is ready to run on AWS EC2 (free tier or any instance):

1. **Upload** the project to your EC2 instance (e.g. via SCP or git clone).
2. **One-time setup** (from project root): `chmod +x deploy/install-on-ec2.sh && ./deploy/install-on-ec2.sh`
3. **Run**: `source .venv/bin/activate && ./deploy/run.sh` (or run as a systemd service — see `deploy/README.md`).
4. Set **PORT** in `.env` if you want a port other than 8000; ensure the EC2 security group allows that port.

Full step-by-step (launch instance, SSH, install, systemd): **docs/HOST_ON_AWS_FREE.md**.

---

## Run Locally

### 1. Without Docker (default upstream: JSONPlaceholder)

```bash
# Create virtualenv and install deps
python3.10 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Optional: copy env example and tweak
cp .env.example .env

# Run proxy on port 8000
uvicorn main:app --host 0.0.0.0 --port 8000
```

Quick checks: `curl http://localhost:8000/health` | `curl http://localhost:8000/posts/1` | response headers: `X-Internal-Latency`, `X-Proxy-Observed`, `X-Debug-Session-ID`.

### 2. With Docker (proxy + target service)

```bash
# Build and start both services
docker compose up --build

# In another terminal:
curl http://localhost:8000/health
curl http://localhost:8000/hello   # Proxied to target-service → "Hello from target service"
```

Proxy is configured via `docker-compose.yml` to use `UPSTREAM_BASE_URL=http://target-service:8080` and `PROXY_LATENCY_MS=100`.

### 3. WebSocket tunnel

Default WebSocket upstream is `wss://echo.websocket.org`. Example with `websocat` or browser:

```bash
# Install websocat if needed, then:
websocat ws://localhost:8000/ws/
# Or path: ws://localhost:8000/ws/echo
```

## Testing the whole app

Run through these steps to verify all features (health, proxy, connection pooling, latency, headers, flakiness, structured logs, WebSocket).

### Prerequisites

- Proxy running locally: `uvicorn main:app --host 0.0.0.0 --port 8000`  
  **or** with Docker: `docker compose up --build` (then use `http://localhost:8000`).

### 1. Health check (always succeeds)

```bash
curl -s http://localhost:8000/health
# Expected: {"status":"ok","service":"proxy"}
```

### 2. HTTP proxy (forwarding + connection pool)

**Without Docker** (default upstream: JSONPlaceholder) — use paths that exist on that API:

```bash
curl -s http://localhost:8000/posts/1
# Expected: JSON object with userId, id, title, body
# Note: /hello does not exist on JSONPlaceholder; you may see {} or 404.
```

**With Docker** (upstream: target-service) — use the target service’s routes:

```bash
docker compose up --build   # in one terminal, then:
curl -s http://localhost:8000/hello
# Expected: "Hello from target service"
```

### 3. Observability headers

```bash
curl -sI http://localhost:8000/health
# Check for: X-Internal-Latency (present on all responses)

curl -sI http://localhost:8000/posts/1
# Check for: X-Internal-Latency; upstream may add Content-Type, etc.
```

### 4. Structured JSON logging

With `python-json-logger` installed, proxy and flakiness logs are JSON. After a request:

```bash
curl -s http://localhost:8000/posts/1 > /dev/null
```

In the server logs you should see a line like:

```json
{"timestamp": "2026-03-06T14:45:02Z", "trace_id": "f8a23c2e4f31", "method": "GET", "path": "/posts/1", "upstream_url": "https://jsonplaceholder.typicode.com/posts/1", "status_code": 200, "internal_latency_ms": 104, "event": "proxied", "message": "proxied"}
```

### 5. Flakiness simulator (optional)

Set in `.env`:

```bash
FLAKINESS_PERCENTAGE=20
```

Restart the proxy, then run multiple requests; about 20% should return 503 or 504 with body `{"error":"Simulated upstream failure"}`. Health must never fail:

```bash
# Run several times; some will fail with 503 or 504
for i in 1 2 3 4 5 6 7 8 9 10; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/hello; done

# Health must always be 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health
# Expected: 200
```

When a request is failed by the flakiness middleware, logs show `"event": "simulated_failure"` with `status_code` 503 or 504.

### 6. Latency simulation

With `PROXY_LATENCY_MS=500` in `.env`, each request is delayed by 500 ms. Check `X-Internal-Latency` (value ≥ 500):

```bash
time curl -sI http://localhost:8000/health
# X-Internal-Latency should reflect the delay
```

### 7. WebSocket tunnel

If you have `websocat` installed:

```bash
websocat ws://localhost:8000/ws/
# Type a message and press Enter; you should see it echoed back (default upstream: wss://echo.websocket.org)
```

### 8. Full local test script (optional)

```bash
# Ensure proxy is running (e.g. uvicorn main:app --host 0.0.0.0 --port 8000)

echo "1. Health"
curl -s http://localhost:8000/health | head -c 80 && echo

echo "2. Proxy (JSONPlaceholder or target-service)"
curl -s http://localhost:8000/posts/1 | head -c 120 && echo
# Or: curl -s http://localhost:8000/hello

echo "3. Headers"
curl -sI http://localhost:8000/health | grep -i x-internal

echo "Done. Check server stdout for structured JSON logs."
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Server port (for EC2/production; used by `deploy/run.sh` and `python main.py`) |
| `UPSTREAM_BASE_URL` | `https://jsonplaceholder.typicode.com` | HTTP upstream base URL |
| `PROXY_LATENCY_MS` | `100` | Simulated latency in ms (asyncio.sleep) |
| `UPSTREAM_TIMEOUT_SECONDS` | `30` | Upstream HTTP timeout (504 if exceeded) |
| `FLAKINESS_PERCENTAGE` | `0` | Percentage of requests (0–100) to fail with 503/504; `/health` is never failed |
| `WS_UPSTREAM_BASE_URL` | `wss://echo.websocket.org` | WebSocket upstream base URL |

## Observability

- **Structured JSON logging**: With `python-json-logger` installed, proxy and flakiness logs are JSON with `trace_id`, `method`, `path`, `upstream_url`, `status_code`, `internal_latency_ms`, `timestamp`, and `event` (e.g. `proxied`, `simulated_failure`).
- **Internal latency**: Each response includes `X-Internal-Latency: <ms>` (time from request entry to response).
- **Debug headers**: Outgoing proxied requests include `X-Proxy-Observed: True` and `X-Debug-Session-ID: <UUID>`.

## Error Handling

- **504 Gateway Timeout**: When upstream does not respond within `UPSTREAM_TIMEOUT_SECONDS`.
- **503 Service Unavailable**: When upstream connection is refused or unreachable (e.g. `ConnectionRefusedError`, `httpx.ConnectError`).
- **502 Bad Gateway**: For other upstream request failures (with safe error payload).

All error responses include `X-Internal-Latency` when applicable.

