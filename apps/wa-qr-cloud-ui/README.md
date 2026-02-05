# WhatsApp Connect — Streamlit Cloud UI

Login and WhatsApp Connect (QR + status). Talks to your FastAPI backend. **No secrets required** for deployment.

## No secrets required

The app uses a **default API URL** in code. You can run it on Streamlit Cloud with **zero secrets** configured. No `GNI_API_BASE_URL` or `.streamlit/secrets.toml` needed.

**Optional override (for a different backend):**

- **Streamlit Cloud:** Settings → Environment variables → `GNI_API_BASE_URL` = `http://your-host:8000`
- **Or** Settings → Secrets → `GNI_API_BASE_URL` = `http://your-host:8000`

If the backend is temporarily down, the app still loads and shows a generic message (“Something went wrong. Please try again later.”). No stack traces or hostnames are shown to users.

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
