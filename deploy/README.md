# Deploy to AWS EC2

This folder contains scripts and config to run the proxy on AWS EC2 (free tier or any instance).

## Quick start on a new EC2 instance

1. **Upload the project** to the instance (e.g. `~/proxy-inspector` or `~/Proxy incpetor project`).

2. **One-time install** (from project root):
   ```bash
   chmod +x deploy/install-on-ec2.sh
   ./deploy/install-on-ec2.sh
   ```

3. **Run manually** (test):
   ```bash
   source .venv/bin/activate
   ./deploy/run.sh
   ```
   Or: `uvicorn main:app --host 0.0.0.0 --port 8000`

4. **Run as a service** (survives reboot):
   ```bash
   # Edit paths in the service file to match your project path and user (ec2-user or ubuntu)
   sudo cp deploy/proxy-inspector.service /etc/systemd/system/
   sudo nano /etc/systemd/system/proxy-inspector.service   # set WorkingDirectory, User, Environment, ExecStart paths
   sudo systemctl daemon-reload
   sudo systemctl enable --now proxy-inspector
   sudo systemctl status proxy-inspector
   ```

## Environment on EC2

- **PORT**: Set in `.env` (e.g. `PORT=8000`). Use `PORT=80` only if you run the process with privileges or put Nginx in front.
- **UPSTREAM_BASE_URL**: Your upstream API (default: JSONPlaceholder).
- **FLAKINESS_PERCENTAGE**, **PROXY_LATENCY_MS**, **UPSTREAM_TIMEOUT_SECONDS**: Optional; see `.env.example`.

## Security group

Allow inbound:

- **22** (SSH) from your IP.
- **8000** (or whatever PORT you use) from `0.0.0.0/0` if the proxy should be public.

## Full guide

See **docs/HOST_ON_AWS_FREE.md** for step-by-step EC2 launch, SSH, and deployment.
