# Deploying IG Pulse

CI (GitHub Actions, `.github/workflows/deploy.yml`) builds the `linux/amd64`
image on every push to `main`, pushes it to `ghcr.io/shariski/ig-pulse`, then
SSHes to the VPS and runs `docker compose pull && up -d`. The VPS only pulls —
it never builds (a torch image won't fit its disk).

Reverse proxy + TLS are handled by the existing nginx-proxy stack on the host;
the app joins the external `deploy_web` network and is fronted by Cloudflare.

## One-time setup

### 1. Cloudflare (you)
- **DNS:** add an A record `pulse.shariski.com → <VPS IP>`, proxied (orange cloud).
- **Origin cert:** Cloudflare dashboard → SSL/TLS → Origin Server → *Create
  Certificate* (cover `*.shariski.com` or `pulse.shariski.com`). Save the
  certificate and private key. Ensure the zone's SSL/TLS mode is **Full** (or
  Full (strict), which requires this origin cert).

### 2. VPS `/opt/ig-pulse/`
```bash
sudo mkdir -p /opt/ig-pulse && sudo chown $USER /opt/ig-pulse
# place docker-compose.prod.yml as docker-compose.yml (or use -f)
cp deploy/.env.example /opt/ig-pulse/.env   # then fill FB_APP_ID/SECRET + SESSION_SECRET
```
Install the Cloudflare origin cert into nginx-proxy's certs volume by filename
match (so nginx-proxy serves it for the vhost):
```bash
# inside the nginx-proxy certs volume / mount:
#   pulse.shariski.com.crt   <- origin certificate (PEM)
#   pulse.shariski.com.key   <- origin private key (PEM)
```

### 3. GitHub repo secrets (Settings → Secrets and variables → Actions)
- `VPS_HOST` — VPS IP / hostname
- `VPS_USER` — deploy user (e.g. `deploy`)
- `VPS_SSH_KEY` — private key whose public half is in that user's
  `~/.ssh/authorized_keys`

### 4. GHCR package visibility
After the first CI publish, make the `ig-pulse` package **public** (GitHub →
your packages → ig-pulse → Package settings) so the VPS can pull without auth.

## Deploy
Push to `main` (or run the workflow manually). To roll back, redeploy a previous
SHA on the VPS: `IMAGE_TAG=<sha> docker compose up -d`.

## Data
All persistent state — `registry.db`, per-account `acct_<id>.db`, and the
HuggingFace model cache — lives in the `ig-pulse-data` Docker volume.
