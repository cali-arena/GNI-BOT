# WhatsApp Connect — GNI (Streamlit Cloud UI)

Streamlit app that shows **WhatsApp QR code** and **connection status** using the FastAPI QR Bridge. Deploy to Streamlit Community Cloud so operators can scan the QR from anywhere without exposing the internal whatsapp-bot.

## Deploy to Streamlit Community Cloud

1. **Fork or use this repo** so the app lives at `apps/wa-qr-cloud-ui/` (or point Streamlit to this folder as the root).

2. **Go to [share.streamlit.io](https://share.streamlit.io)** and sign in. Click **New app**.

3. **Repository:** your repo (e.g. `your-org/gni-bot-creator`).  
   **Branch:** `main` (or your default).  
   **Main file path:** `apps/wa-qr-cloud-ui/app.py`.  
   **App URL:** choose a subdomain (e.g. `wa-qr-gni`).

4. **Set secrets / environment variables** in Streamlit Cloud (App → Settings → Secrets, or **Settings → General → Environment variables** depending on UI):
   - `GNI_API_BASE_URL` — Full base URL of your API (e.g. `https://your-api.example.com` or `https://your-api.example.com:8000`). No trailing slash.
   - `WA_QR_BRIDGE_TOKEN` — Same long random token configured in the API as `WA_QR_BRIDGE_TOKEN`. The app sends it as `Authorization: Bearer <token>`.
   - `UI_PASSWORD` — (Optional.) If set, users must enter this password before seeing the dashboard.
   - `AUTO_REFRESH_SECONDS` — (Optional.) Seconds between auto-refresh (default: `3`).

5. **CORS:** On the API side, add your Streamlit app origin to CORS (e.g. set `STREAMLIT_ORIGIN=https://wa-qr-gni.streamlit.app` in the API env so the browser allows requests from the Streamlit domain).

6. Deploy. The app will call `GET {GNI_API_BASE_URL}/admin/wa/status` and `GET {GNI_API_BASE_URL}/admin/wa/qr` with the Bearer token.

## Required env vars (summary)

| Variable | Required | Description |
|----------|----------|-------------|
| `GNI_API_BASE_URL` | Yes | API base URL (e.g. `https://api.example.com`). |
| `WA_QR_BRIDGE_TOKEN` | Yes | Bearer token for the QR bridge (same as API `WA_QR_BRIDGE_TOKEN`). |
| `UI_PASSWORD` | No | If set, password gate is shown before the dashboard. |
| `AUTO_REFRESH_SECONDS` | No | Auto-refresh interval in seconds (default: 3). |

## Run locally

```bash
cd apps/wa-qr-cloud-ui
pip install -r requirements.txt

export GNI_API_BASE_URL="https://your-api-host:8000"
export WA_QR_BRIDGE_TOKEN="your_bridge_token"
# optional:
export UI_PASSWORD="optional_password"
export AUTO_REFRESH_SECONDS=5

streamlit run app.py
```

Open the URL shown (e.g. http://localhost:8501). Status and QR (when not connected) appear and refresh automatically.

## Security notes

- **Token:** The app never logs or displays `WA_QR_BRIDGE_TOKEN`. It is only sent in the `Authorization` header to your API. Store it in Streamlit Cloud secrets or env vars, not in code.
- **Password:** If you set `UI_PASSWORD`, it is checked in memory only and stored in `st.session_state` for the session; it is not logged or sent anywhere.
- **API only:** The UI talks only to your FastAPI API (QR bridge). The whatsapp-bot stays internal; never expose it directly to the internet.
- **HTTPS:** Use HTTPS for the API in production so the token is not sent in clear text.

## Behavior

- **Connected ✅** — WhatsApp session is active; QR block is hidden.
- **Waiting for QR** — API returned a QR; scan with WhatsApp on the admin phone.
- **Disconnected** — Not connected and no QR (e.g. bot restarting or error).
- **API unreachable** — Network/configuration issue; check URL and token and retry.
- QR expires quickly; the app auto-refreshes and you can use **Refresh now** to fetch a new one.
