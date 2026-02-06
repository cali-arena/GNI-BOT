# WhatsApp Connect — Streamlit Cloud UI

Login and WhatsApp Connect (QR + status). Talks to your FastAPI backend. **No secrets required** for deployment.

## Point app at your VM API (Streamlit Cloud)

**Default:** The app uses `http://217.216.84.81:8000` as the API URL. If that’s your VM, deploy with no config.

**To set or change the API URL:**

1. **share.streamlit.io** → your app → **⋮** → **Settings**.
2. Open the **Secrets** tab and add:
   ```toml
   GNI_API_BASE_URL = "http://217.216.84.81:8000"
   ```
   (Use your VM IP or HTTPS URL; if the app is on **HTTPS** you must use an **HTTPS** API URL or the browser will block requests.)
3. **Save** → app will redeploy.

**Or** use **Settings** → **Environment variables**: key `GNI_API_BASE_URL`, value `http://217.216.84.81:8000`.

See **STREAMLIT_CLOUD.md** for full steps and creating a user on the backend.

## Run locally

**From repo root (same as Streamlit Cloud):**

```bash
pip install -r requirements-streamlit.txt
streamlit run streamlit_app.py
```

**From this folder:**

```bash
cd apps/wa-qr-cloud-ui
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud deployment

### Entrypoint and requirements

- **Main file path:** `streamlit_app.py` (repo root)
- **Requirements file:** `requirements-streamlit.txt` (repo root)
- **Root directory:** leave empty (repo root)

### Redeploy after code changes

1. Commit and push to the branch your app uses (e.g. `main`):
   ```bash
   git add .
   git commit -m "Streamlit: your message"
   git push origin main
   ```
2. Streamlit Cloud **auto-deploys on push**. Wait 1–2 minutes.
3. Optional: open the app on share.streamlit.io → **Manage app** → **Reboot app** to force an immediate redeploy.

No need to add or change secrets when redeploying.

## Dependencies (requirements.txt)

- streamlit
- requests
- qrcode[pil]
- pillow

All are listed in `apps/wa-qr-cloud-ui/requirements.txt` and in the root `requirements-streamlit.txt`.
