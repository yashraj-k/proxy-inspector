High-Performance HTTP & WebSocket Proxy
======================================

A production-style developer infrastructure tool that acts as an HTTP and WebSocket proxy with latency simulation, observability, and failure injection. It allows developers to route requests through a proxy to test API reliability, simulate network conditions, and observe request behavior.

Features
--------

### HTTP Proxy Engine

- Catch-all request forwarding (`/{path:path}`) for all HTTP methods using a global connection-pooled `httpx.AsyncClient`.

### WebSocket Tunneling

- Bi-directional WebSocket bridge at `/ws/{path:path}` for real-time communication.

### Latency Simulation

- Configurable artificial delay via `PROXY_LATENCY_MS` to mimic slow networks.

### Failure Injection

- Optional flakiness simulator that randomly returns **503 / 504** responses to test retry logic.

### Observability

- Structured JSON logging  
- `trace_id` request tracing  
- `X-Internal-Latency` response header  
- Debug headers (`X-Proxy-Observed`, `X-Debug-Session-ID`)

Tech Stack
----------

- Python 3.10+  
- FastAPI  
- HTTPX (AsyncClient)  
- AsyncIO  
- Docker  
- AWS EC2  

Architecture
------------

**Client → Proxy → Target API**

The proxy forwards requests to an upstream API while adding:

- latency simulation  
- structured logging  
- failure injection  
- request observability  

Live Demo
---------

**Health check:**

`http://16.171.171.108:8000/health`

**Example request:**

`http://16.171.171.108:8000/hello`

Run Locally
-----------

1. **Clone the repo**

   ```bash
   git clone https://github.com/YOUR_USERNAME/proxy-inspector.git
   cd proxy-inspector
   ```

2. **Run with Docker**

   ```bash
   docker compose up --build
   ```

   Proxy will run on:

   - `http://localhost:8000`

Use the Proxy With Your API
---------------------------

Set your API as the upstream service.

**Example `.env`:**

```bash
UPSTREAM_BASE_URL=https://api.example.com
```

Start the proxy and send requests through it:

```bash
curl http://localhost:8000/users
```

The proxy will forward the request to:

```text
https://api.example.com/users
```

while injecting latency, logging requests, and optionally simulating failures.

Example Environment Variables
-----------------------------

| Variable               | Default        | Description                          |
|------------------------|----------------|--------------------------------------|
| `UPSTREAM_BASE_URL`    | JSONPlaceholder| Upstream API                         |
| `PROXY_LATENCY_MS`     | 100            | Simulated network delay              |
| `FLAKINESS_PERCENTAGE` | 0              | % of requests to randomly fail       |
| `UPSTREAM_TIMEOUT_SECONDS` | 30        | Upstream request timeout             |
| `PORT`                 | 8000           | Server port                          |

Why This Project
----------------

This project explores core backend infrastructure concepts:

- Async concurrency  
- Reverse proxy architecture  
- Observability and tracing  
- Resilience testing  
- Containerized deployment  