"""
Minimal HTTP target service for local proxy testing.

Responds to GET /hello with "Hello from target service".
Used by docker-compose to validate proxy forwarding.
"""

from fastapi import FastAPI

app = FastAPI()


@app.get("/hello")
async def hello() -> str:
    """Return a simple greeting for proxy tests."""
    return "Hello from target service"


@app.get("/health")
async def health() -> dict:
    """Health check for the target service."""
    return {"status": "ok", "service": "target-service"}
