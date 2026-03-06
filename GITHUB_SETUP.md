# Put This Project on GitHub

Follow these steps to push the project to your GitHub account.

## 1. Create a new repository on GitHub

1. Go to **https://github.com/new** (or click **+** → **New repository**).
2. **Repository name**: e.g. `proxy-inspector` or `http-websocket-proxy`.
3. **Description** (optional): e.g. `High-performance HTTP & WebSocket proxy with latency simulation and observability`.
4. Choose **Public**.
5. **Do not** check "Add a README" or "Add .gitignore" (this project already has them).
6. Click **Create repository**.

## 2. Initialize Git and push (in your project folder)

Open a terminal in the project root (`Proxy incpetor project`) and run:

```bash
cd "/Users/yashrajkabre/Desktop/Browserstack/Proxy incpetor project"

# Initialize and first commit (if not already done)
git init
git add .
git commit -m "Initial commit: HTTP/WebSocket proxy with latency, flakiness, EC2 deploy"

# Add your GitHub repo as remote (replace YOUR_USERNAME and YOUR_REPO with your values)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# Rename branch to main if needed, then push
git branch -M main
git push -u origin main
```

**Using SSH instead of HTTPS:**

```bash
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

## 3. If you already ran `git init` and committed

Just add the remote and push:

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

## Notes

- **`.env` is in `.gitignore`** — it will not be pushed (keeps secrets off GitHub). Use `.env.example` as a template; on EC2 or elsewhere, copy it to `.env` and fill in values.
- If GitHub asks for login, use a **Personal Access Token** (Settings → Developer settings → Personal access tokens) as the password when using HTTPS, or set up **SSH keys** and use the `git@github.com:...` URL.
