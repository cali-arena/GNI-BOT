# GNI — Streamlit Cloud UI

Multi-page Streamlit app: **Home**, **WhatsApp Connect**, **Monitoring**, **Posts**. Config and login via Streamlit Secrets; no local `.env` or file persistence (Cloud-safe).

## Streamlit Cloud Setup (cali-arena/GNI-BOT)

1. In Streamlit Cloud, point the app to repo **cali-arena/GNI-BOT**.
2. Set **Root directory** to: `apps/wa-qr-cloud-ui`
3. Set **Main file path** to: `app.py`
4. In **Settings → Secrets**, paste (replace placeholders):

```toml
GNI_API_BASE_URL = "https://your-api.example.com"
WA_QR_BRIDGE_TOKEN = "your_long_random_bridge_token"
SEED_CLIENT_EMAIL = "admin@yourcompany.com"
SEED_CLIENT_PASSWORD = "your_secure_password"
SEED_CLIENT_ROLE = "client"
```

5. **Exact secrets keys** (optional: `API_KEY` for Monitoring/Posts):

| Key | Required | Description |
|-----|----------|-------------|
| `GNI_API_BASE_URL` | ✅ | API base URL (no trailing slash). |
| `WA_QR_BRIDGE_TOKEN` | ✅ | Bearer token for QR bridge. |
| `SEED_CLIENT_EMAIL` | ✅ | Login email. |
| `SEED_CLIENT_PASSWORD` | ✅ | Login password (hashed; never plaintext in logs). |
| `SEED_CLIENT_ROLE` | No | `client` or `admin`. |
| `API_KEY` | No | X-API-Key for /monitoring and /review. |

6. After saving secrets, refresh the app. Log in with `SEED_CLIENT_EMAIL` / `SEED_CLIENT_PASSWORD`.

## Troubleshooting

- **"Missing configuration"** — Add all required keys in **Settings → Secrets**. Save and refresh.
- **Health check failure** — Check `GNI_API_BASE_URL` is correct and `/health` returns 200.
- **401 on Monitoring/Posts** — Set `API_KEY` in Secrets if your API requires it.

## Run locally

```bash
cd apps/wa-qr-cloud-ui
pip install -r requirements.txt
# .streamlit/secrets.toml or env vars
streamlit run app.py
```
