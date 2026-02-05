# Streamlit Cloud configuration

- **Main file path:** `streamlit_app.py` (repo root). This entrypoint imports and runs the app from `apps/wa-qr-cloud-ui/app.py`.
- **Requirements file:** `requirements-streamlit.txt` (set in app settings so Cloud installs only Streamlit deps).
- **Secrets:** None required. Do not use `.streamlit/secrets.toml` for this app.
- **Optional env:** `API_BASE_URL` — backend API base URL. If unset, users can pass `?api_base_url=http://VM_IP:8000` in the URL.

After pushing changes, open the app on share.streamlit.io → **Manage app** → **Reboot app** (or wait for auto-redeploy).
