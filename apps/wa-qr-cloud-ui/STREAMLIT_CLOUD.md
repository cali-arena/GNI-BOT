# Streamlit Cloud configuration

- **Root directory:** `apps/wa-qr-cloud-ui`
- **Main file path:** `app.py`
- **Secrets:** Do **not** require any secrets. App must run without them.
- **Optional env:** `GNI_API_BASE_URL` — backend API base URL. If unset, the app shows a "Backend URL" input so the user can paste it once per session (stored in `st.session_state`).

After pushing changes, open the app on share.streamlit.io → **Manage app** → **Reboot app** (or wait for auto-redeploy).
