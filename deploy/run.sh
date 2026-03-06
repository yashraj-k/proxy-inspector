#!/usr/bin/env bash
# Production run script for AWS EC2 (and other hosts).
# Usage: ./deploy/run.sh   or   bash deploy/run.sh
# Set PORT in .env or environment (default 8000). Uses 1 worker for t2.micro.

set -e
cd "$(dirname "$0")/.."
APP_ROOT="$(pwd)"

# Load .env so PORT and other vars are available (e.g. when run by systemd)
if [ -f "$APP_ROOT/.env" ]; then
  set -a
  . "$APP_ROOT/.env"
  set +a
fi

if [ -z "$VIRTUAL_ENV" ] && [ -d "$APP_ROOT/.venv" ]; then
  source "$APP_ROOT/.venv/bin/activate"
fi

PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"

exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers "$WORKERS" \
  --no-access-log
