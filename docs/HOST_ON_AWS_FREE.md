# How to Host This Proxy on AWS (Free Tier)

This guide gives **exact steps** to run the HTTP/WebSocket proxy on **AWS EC2 Free Tier**. You get **750 hours/month of a t2.micro instance free for 12 months** (enough for one instance running 24/7).

---

## What You Get (Free Tier)

- **EC2**: 750 hours/month of t2.micro (1 vCPU, 1 GB RAM) — one instance 24/7 = free for 12 months.
- **Data transfer**: 15 GB out/month (then paid).
- **After 12 months**: You start paying (~$8–10/month for t2.micro) unless you stop/terminate the instance.

---

## Prerequisites

- AWS account (create at https://aws.amazon.com)
- Your project code (zip or git repo) to upload to the server

---

## Step 1: Launch an EC2 Instance

1. Log in to **AWS Console** → **EC2** → **Launch Instance**.
2. **Name**: e.g. `proxy-inspector`.
3. **AMI**: **Amazon Linux 2023** (or **Ubuntu 22.04**).
4. **Instance type**: **t2.micro** (must be this for free tier).
5. **Key pair**: Create new or use existing; **download the `.pem`** and keep it safe (you need it to SSH).
6. **Network / Security group**: Create a security group that allows:
   - **SSH (22)** from your IP (or 0.0.0.0/0 only if you accept the risk).
   - **Custom TCP 8000** (or 80) from **0.0.0.0/0** so the proxy is reachable.
7. **Storage**: 8 GB (free tier allows 30 GB).
8. Click **Launch instance**.

---

## Step 2: Connect to the Instance

1. In EC2 → **Instances** → select your instance → **Connect**.
2. Note the **Public IPv4 address** (e.g. `3.14.xxx.xxx`).
3. In a terminal on your Mac, set permissions and SSH (replace `key.pem` and the IP):

```bash
chmod 400 /path/to/your-key.pem
ssh -i /path/to/your-key.pem ec2-user@YOUR_PUBLIC_IP
```

- For **Amazon Linux**: user is `ec2-user`.
- For **Ubuntu**: user is `ubuntu` → `ssh -i your-key.pem ubuntu@YOUR_PUBLIC_IP`.

---

## Step 3: Install Python 3.10+ and Dependencies (Amazon Linux 2023)

Run on the EC2 instance:

```bash
# Update packages
sudo dnf update -y

# Install Python 3.11 and pip
sudo dnf install -y python3.11 python3.11-pip

# Optional: install git if you'll clone a repo
sudo dnf install -y git
```

For **Ubuntu 22.04**:

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip git
```

---

## Step 4: Upload Your Project to the Instance

**Option A – From your laptop (using SCP):**

```bash
# From your Mac, in the project root (parent of the proxy project folder)
scp -i /path/to/your-key.pem -r "Proxy incpetor project" ec2-user@YOUR_PUBLIC_IP:~/
```

**Option B – Clone from Git:**

```bash
# On the EC2 instance
cd ~
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git proxy-inspector
cd proxy-inspector
```

**Option C – Create a zip on your Mac, then SCP the zip and unzip on the server:**

```bash
# On Mac (in folder containing the project)
zip -r proxy-inspector.zip "Proxy incpetor project"
scp -i your-key.pem proxy-inspector.zip ec2-user@YOUR_PUBLIC_IP:~/

# On EC2
cd ~ && unzip proxy-inspector.zip && cd "Proxy incpetor project"
```

---

## Step 5: Create Virtual Environment and Install Dependencies (on EC2)

```bash
cd ~/proxy-inspector
# Or: cd ~/"Proxy incpetor project"  if you kept that name

python3.11 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

# Create .env from example and edit if needed
cp .env.example .env
# Optional: nano .env  to set UPSTREAM_BASE_URL, FLAKINESS_PERCENTAGE, etc.
```

---

## Step 6: Run the Proxy (Test First)

```bash
# Still in project dir with .venv activated
uvicorn main:app --host 0.0.0.0 --port 8000
```

- From your browser or laptop: `http://YOUR_PUBLIC_IP:8000/health`  
  You should see `{"status":"ok","service":"proxy"}`.
- **Stop the server** with `Ctrl+C` before setting up the service.

---

## Step 7: Run as a System Service (So It Restarts on Reboot)

1. Create a systemd unit file:

```bash
sudo nano /etc/systemd/system/proxy-inspector.service
```

2. Paste this (adjust paths if your project is elsewhere):

```ini
[Unit]
Description=HTTP/WebSocket Proxy (Proxy Inspector)
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/proxy-inspector
Environment="PATH=/home/ec2-user/proxy-inspector/.venv/bin"
ExecStart=/home/ec2-user/proxy-inspector/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- If your project is in `/home/ec2-user/Proxy incpetor project`, use:
  - `WorkingDirectory=/home/ec2-user/Proxy incpetor project`
  - `Environment="PATH=/home/ec2-user/Proxy incpetor project/.venv/bin"`
  - `ExecStart=/home/ec2-user/Proxy incpetor project/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000`

3. For **Ubuntu**, replace `ec2-user` with `ubuntu` in the paths.

4. Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable proxy-inspector
sudo systemctl start proxy-inspector
sudo systemctl status proxy-inspector
```

5. Check logs:

```bash
sudo journalctl -u proxy-inspector -f
```

---

## Step 8: Open Port 8000 in the Security Group (If Not Done Already)

1. EC2 → **Security Groups** → select the group attached to your instance.
2. **Edit inbound rules** → **Add rule**:
   - Type: **Custom TCP**
   - Port: **8000**
   - Source: **0.0.0.0/0** (or your IP for testing)
3. Save.

Then test again: `http://YOUR_PUBLIC_IP:8000/health` and `http://YOUR_PUBLIC_IP:8000/posts/1`.

---

## Optional: Use Port 80 and Keep It Running

To serve on port 80 (so you can use `http://YOUR_IP` without `:8000`):

1. Open port **80** in the security group (inbound rule).
2. Run uvicorn on 80 (requires sudo for port &lt; 1024):

```ini
ExecStart=/home/ec2-user/proxy-inspector/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 80
```

Or keep uvicorn on 8000 and put **Nginx** in front as a reverse proxy on 80 (better for production).

---

## Optional: Elastic IP (So the Public IP Doesn’t Change)

1. EC2 → **Elastic IPs** → **Allocate**.
2. **Actions** → **Associate** → choose your instance.
3. The public IP now stays the same when you stop/start the instance.  
   **Note:** Elastic IP is free only while the instance is running; if the instance is stopped, you can be charged for an unassociated Elastic IP.

---

## Summary Checklist

| Step | Action |
|------|--------|
| 1 | Launch EC2 t2.micro (Amazon Linux or Ubuntu), create/download .pem key, open SSH (22) and 8000 |
| 2 | SSH: `ssh -i key.pem ec2-user@PUBLIC_IP` |
| 3 | Install Python 3.11 and pip (and git if needed) |
| 4 | Upload project (SCP, git clone, or zip) |
| 5 | `python3.11 -m venv .venv`, `source .venv/bin/activate`, `pip install -r requirements.txt`, `cp .env.example .env` |
| 6 | Test: `uvicorn main:app --host 0.0.0.0 --port 8000` → check `http://PUBLIC_IP:8000/health` |
| 7 | Create `/etc/systemd/system/proxy-inspector.service`, then `systemctl enable --now proxy-inspector` |
| 8 | Ensure security group allows TCP 8000 from 0.0.0.0/0 |

After this, the proxy is hosted on AWS and reachable at `http://YOUR_PUBLIC_IP:8000` (or port 80 if you configured it). Free tier covers one t2.micro 24/7 for 12 months; after that you pay for the instance unless you stop or terminate it.
