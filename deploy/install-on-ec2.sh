#!/usr/bin/env bash
# One-time setup on a fresh Amazon Linux 2023 or Ubuntu EC2 instance.
# Run from the project root after uploading the project (e.g. in ~/proxy-inspector).
#
#   chmod +x deploy/install-on-ec2.sh
#   ./deploy/install-on-ec2.sh

set -e
cd "$(dirname "$0")/.."
APP_ROOT="$(pwd)"

echo "Installing in $APP_ROOT"

# Detect OS and install Python
if [ -f /etc/os-release ]; then
  . /etc/os-release
  if [[ "$ID" == "amzn" ]] || [[ "$ID" == "rhel" ]]; then
    sudo dnf install -y python3.11 python3.11-pip 2>/dev/null || sudo dnf install -y python3 python3-pip
    PYTHON=python3.11
  elif [[ "$ID" == "ubuntu" ]] || [[ "$ID" == "debian" ]]; then
    sudo apt-get update
    sudo apt-get install -y python3.11 python3.11-venv python3-pip 2>/dev/null || sudo apt-get install -y python3 python3-venv python3-pip
    PYTHON=python3.11
  else
    PYTHON=python3
  fi
else
  PYTHON=python3
fi

$PYTHON -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — edit .env if needed."
fi

echo "Done. Activate venv and run: ./deploy/run.sh   or   uvicorn main:app --host 0.0.0.0 --port 8000"
