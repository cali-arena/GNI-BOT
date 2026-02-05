# Deploy WhatsApp QR UI to Streamlit Cloud

This app talks **only** to the GNI API over HTTPS. Users log in with email/password (JWT); no WA tokens are stored in Streamlit.

## Required: GNI_API_BASE_URL

- **Repository:** Your GNI-BOT repo (e.g. `https://github.com/your-org/GNI-BOT`)
- **Branch:** `main` (or your default)
- **Root directory:** `apps/wa-qr-cloud-ui`
- **Main file path:** `app.py`

### Streamlit Cloud settings

1. [Streamlit Community Cloud](https://share.streamlit.io/) → your app → **Settings**.
2. **General:** set **Root directory** to `apps/wa-qr-cloud-ui`, **Main file path** to `app.py`.
3. **Secrets** (or Environment variables): set **only**:

```toml
GNI_API_BASE_URL = "https://your-api.example.com"
```

Use your VM's public URL and port (e.g. `https://api.yourdomain.com` or `https://YOUR_IP:8000`). No trailing slash. The API must be reachable from Streamlit Cloud over HTTPS.

4. **Save** and **Reboot** the app.

Users log in with their **API user** email/password (created via `/auth/register` or your seed script). JWT is kept in `session_state`; they see only their own QR and status.

## Optional

- **SEED_CLIENT_EMAIL** / **SEED_CLIENT_PASSWORD**: legacy in-app fallback if API login fails (not required for normal JWT flow).
- **API_KEY** or **ADMIN_API_KEY**: for Monitoring/Posts if your API uses `X-API-Key`.
- **AUTO_REFRESH_SECONDS**: polling interval for QR/status (default 3).

Do **not** set `WA_QR_BRIDGE_TOKEN` for this app; authentication is JWT-only.
