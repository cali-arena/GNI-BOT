# Deploy to Streamlit Cloud (cali-arena/GNI-BOT)

## Streamlit Cloud settings

- **Repository:** `https://github.com/cali-arena/GNI-BOT`
- **Branch:** `main` (or your default)
- **Root directory:** `apps/wa-qr-cloud-ui`
- **Main file path:** `app.py`

## 1. Add secrets (fix "Missing configuration")

1. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in.
2. Open your app (e.g. **automatewa**).
3. Go to **Settings → Secrets**.
4. Paste and replace placeholders:

```toml
GNI_API_BASE_URL = "https://your-api.example.com"
WA_QR_BRIDGE_TOKEN = "your_long_random_bridge_token"
SEED_CLIENT_EMAIL = "admin@yourcompany.com"
SEED_CLIENT_PASSWORD = "your_secure_password"
SEED_CLIENT_ROLE = "client"
```

5. **Save**. Refresh the app; log in with `SEED_CLIENT_EMAIL` / `SEED_CLIENT_PASSWORD`.

## 2. Optional

- **API key:** If your API uses `X-API-Key`, add: `API_KEY = "your-api-key"`
- After changing **Root directory**, click **Reboot app**.
