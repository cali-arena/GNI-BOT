# GNI Bot — Deployment (VM + Streamlit Cloud)

- **VM:** runs Postgres, Redis, Ollama, API, worker, whatsapp-bot (internal). Only API (port 8000) is exposed.
- **Streamlit Cloud:** lightweight QR UI; talks only to API over HTTPS (JWT). Never talks to whatsapp-bot.

---

## 1. VM deployment

### 1.1 One-time setup on the VM

SSH into the VM and clone the repo (use `/opt/gni` or `/opt/gni-bot-creator`). If you use a monorepo, ensure the **whatsapp-bot** lives at `../apps/whatsapp-bot` relative to the clone (e.g. clone the parent repo so that `apps/whatsapp-bot` and the GNI-BOT compose root are siblings).

```bash
ssh root@<YOUR_VM_IP>

# Clone to /opt/gni (or /opt/gni-bot-creator)
git clone https://github.com/your-org/GNI-BOT.git /opt/gni
# If whatsapp-bot is in a sibling repo:
# git clone https://github.com/your-org/your-monorepo.git /opt/repo
# and use /opt/repo/GNI-BOT as compose root, with /opt/repo/apps/whatsapp-bot present

cd /opt/gni
```

If whatsapp-bot is in a **sibling** directory (e.g. monorepo layout):

- Clone so that GNI-BOT compose root is e.g. `/opt/gni` and whatsapp-bot is at `/opt/apps/whatsapp-bot`.
- In `docker-compose.yml`, `whatsapp-bot` build context is `../apps/whatsapp-bot`. So either:
  - Clone monorepo to `/opt/repo` and run compose from `/opt/repo/GNI-BOT` with `../apps/whatsapp-bot` = `/opt/repo/apps/whatsapp-bot`, or
  - Sync/copy `apps/whatsapp-bot` to `/opt/gni/../apps/whatsapp-bot` (i.e. parent of `/opt/gni` has `apps/whatsapp-bot`).

Example (monorepo at `/opt/repo`, GNI-BOT inside it):

```bash
git clone https://github.com/your-org/your-monorepo.git /opt/repo
cd /opt/repo/GNI-BOT
```

Create env and run:

```bash
cp .env.example .env
# Edit .env: POSTGRES_*, API_PORT, etc.

docker compose up -d --build
```

Only **API** (e.g. port 8000) is bound to the host. whatsapp-bot has no `ports:` and is internal.

### 1.2 Systemd (24/7 auto-start)

From the **VM**, from the same directory you use for `docker compose` (e.g. `/opt/gni` or `/opt/repo/GNI-BOT`):

```bash
sudo APP_DIR=/opt/gni bash scripts/install_systemd.sh
```

Default `APP_DIR` is `/opt/gni-bot-creator`; override with `APP_DIR` if you used `/opt/gni`.

- Start on boot: `systemctl enable gni-bot`
- Status: `sudo systemctl status gni-bot`
- Logs: `sudo journalctl -u gni-bot -f`

### 1.3 Deploy from your machine (optional)

Using the project’s deploy script (syncs repo + optional whatsapp-bot, then runs compose on VM):

```bash
VM_USER=root VM_HOST=<YOUR_VM_IP> VM_PATH=/opt/gni bash scripts/deploy_vm.sh
```

Then on the VM, enable systemd as above with `APP_DIR=/opt/gni`.

### 1.4 Acceptance (VM)

- `curl http://<VM_IP>:8000/health` returns OK.
- Port 3100 (whatsapp-bot) is **not** exposed on the host; only 8000 is public.

---

## 2. Streamlit Cloud deployment

- **Connect** the GitHub repo that contains `apps/wa-qr-cloud-ui` (e.g. GNI-BOT or your monorepo).
- **Branch:** e.g. `main`.
- **Root directory:** `apps/wa-qr-cloud-ui`
- **Main file path:** `app.py`
- **Secrets / Environment:** set **GNI_API_BASE_URL** to your API URL, e.g. `https://<your-domain-or-ip>:8000` (no trailing slash). Use HTTPS in production.

No WA tokens in Streamlit; only user JWT in `session_state`. Clients log in → “Connect WhatsApp” → see **their** QR and status only.

See [apps/wa-qr-cloud-ui/DEPLOY.md](apps/wa-qr-cloud-ui/DEPLOY.md) for Streamlit-specific steps.

---

## 3. Summary

| Component      | Where        | Exposed              | Notes                                  |
|----------------|-------------|----------------------|----------------------------------------|
| Postgres       | VM (internal) | No                   | Used by API/worker                     |
| Redis          | VM (internal) | No                   | Used by API/worker/whatsapp-bot        |
| Ollama         | VM (internal) | No                   | Used by worker                         |
| API            | VM          | **8000** (public)    | Only public service                    |
| Worker         | VM (internal) | No                   | RQ jobs                                |
| whatsapp-bot   | VM (internal) | **Never**            | API calls it internally                |
| Streamlit QR UI| Streamlit Cloud | N/A               | Calls API over HTTPS (JWT)             |

Acceptance:

- Client logs into Streamlit UI, connects WhatsApp, sees **their** QR and status only.
- VM stays 24/7 with systemd.
- whatsapp-bot is never exposed publicly.
