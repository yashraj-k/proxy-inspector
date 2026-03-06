"""
Configuration for the HTTP/WebSocket proxy.

Loads settings from environment variables with sensible defaults,
supporting containerized and local deployment.
"""

import os  # For reading environment variables (os.getenv)
from typing import Optional  # For optional WS_UPSTREAM_BASE_URL

from dotenv import load_dotenv  # Load .env file from project root into os.environ

load_dotenv()  # Call once at import time so .env values are available to os.getenv below


def get_env_int(key: str, default: int) -> int:
    """Parse integer from environment with default; returns default if missing or invalid."""
    value = os.getenv(key)  # Read env var (None if not set)
    if value is None:
        return default
    try:
        return int(value)  # Convert to int; raises ValueError if not a number
    except ValueError:
        return default  # Invalid value (e.g. "abc") -> use default


def get_env_float(key: str, default: float) -> float:
    """Parse float from environment with default; strips whitespace; returns default if missing or invalid."""
    value = os.getenv(key)
    if value is None:
        return default
    value = value.strip()  # Remove leading/trailing spaces and newlines (e.g. "20\n" -> "20")
    if value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


# --- HTTP proxy upstream: base URL to which all proxied requests are sent ---
UPSTREAM_BASE_URL: str = os.getenv("UPSTREAM_BASE_URL", "https://jsonplaceholder.typicode.com")

# --- Latency simulation: delay in seconds applied to every request (PROXY_LATENCY_MS in ms, converted to seconds) ---
LATENCY_SIMULATION_SECONDS: float = get_env_float("PROXY_LATENCY_MS", 100.0) / 1000.0

# --- Upstream request timeout: after this many seconds, request fails with 504 ---
UPSTREAM_TIMEOUT_SECONDS: float = get_env_float("UPSTREAM_TIMEOUT_SECONDS", 30.0)

# --- WebSocket upstream base URL (e.g. wss://echo.websocket.org); None means use default in websocket_proxy ---
WS_UPSTREAM_BASE_URL: Optional[str] = os.getenv("WS_UPSTREAM_BASE_URL")

# --- Flakiness: percentage (0–100) of non-health requests to fail with 503/504; 0 = disabled ---
FLAKINESS_PERCENTAGE: float = get_env_float("FLAKINESS_PERCENTAGE", 0.0)

# --- Server port for production (used by deploy/run.sh and systemd); default 8000 ---
PORT: int = get_env_int("PORT", 8000)
