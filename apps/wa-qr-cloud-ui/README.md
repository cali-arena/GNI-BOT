# WhatsApp QR Cloud UI

Lightweight Streamlit app for connecting WhatsApp via QR. Talks only to the GNI API (JWT); no WA tokens stored.

## Deploy structure

```
apps/wa-qr-cloud-ui/
  app.py              # Entrypoint
  requirements.txt
  README.md
  pages/              # Multi-page app
  src/                # config, api, auth
```

## Streamlit Cloud deployment

1. **Connect** your GitHub repo (e.g. `your-org/GNI-BOT`).
2. **App entrypoint**
   - **Root directory:** `apps/wa-qr-cloud-ui`
   - **Main file path:** `app.py`
3. **Environment / Secrets**
   - **Required:** `GNI_API_BASE_URL` — API base URL (e.g. `https://your-api.example.com:8000`), no trailing slash.
   - **Optional:** `APP_NAME` — App title in the browser (defaults to GNI).
4. **Save** and **Reboot** the app.

Users log in with email/password (API `/auth/login`); JWT is stored in session. They see only their own WhatsApp QR and status.

## Run locally

```bash
cd apps/wa-qr-cloud-ui
pip install -r requirements.txt
# Set GNI_API_BASE_URL in .streamlit/secrets.toml or env
streamlit run app.py
```

## Syntax check

From this directory or repo root:

```bash
python -m py_compile app.py
```
