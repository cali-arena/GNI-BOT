# Streamlit Cloud configuration

## Entrypoint and requirements

- **Main file path:** `streamlit_app.py` (repo root). This runs the app from `apps/wa-qr-cloud-ui/app.py`.
- **Requirements file:** `requirements-streamlit.txt` (repo root). Set this in the app settings.
- **Root directory:** leave empty (repo root).

## Point the app at your VM API

The app calls your backend for login and WhatsApp. Set the API URL in Streamlit Cloud so the app knows where to send requests.

### Option A: Use the default (no config)

The app has a **default API URL** in code (`http://217.216.84.81:8000`). If that is your VM, you don’t need to set anything. Deploy and use the app as-is.

### Option B: Set the API URL in Streamlit Cloud (recommended)

1. Open **https://share.streamlit.io** and go to your app.
2. Click the **⋮** (three dots) next to your app → **Settings** (or **Manage app** → **Settings**).
3. Open the **Secrets** tab.
4. In the text box, add one line (replace with your API URL if different):

   ```toml
   GNI_API_BASE_URL = "http://217.216.84.81:8000"
   ```

   - Use **HTTP** if your Streamlit app URL is `http://...` (e.g. local).
   - Use **HTTPS** if your app is on **https://...** (e.g. `*.streamlit.app`). Browsers block HTTP calls from HTTPS pages, so the API must be served over HTTPS (e.g. reverse proxy + Let’s Encrypt, or a tunnel).

5. Click **Save**. The app will redeploy and use this URL for `/auth/login`, `/whatsapp/status`, etc.

### Option C: Environment variable instead of Secrets

In **Settings** → **General** (or **Environment variables**), add:

- **Key:** `GNI_API_BASE_URL`
- **Value:** `http://217.216.84.81:8000` (or your HTTPS API URL)

Same rules as above: use HTTPS if the Streamlit app is on HTTPS.

## After changing the API URL

- **Reboot app:** **Manage app** → **Reboot app** (or wait for auto-redeploy after saving).
- **Create a user** on the backend if you haven’t:
  ```bash
  curl -s -X POST http://YOUR_VM_IP:8000/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"your@email.com","password":"YourPassword"}'
  ```
- Log in on the Streamlit app with that email and password.

## Redeploy after code changes

1. Push to the branch your app uses (e.g. `main`).
2. Streamlit Cloud auto-deploys in 1–2 minutes.
3. Optional: **Manage app** → **Reboot app** to force an immediate redeploy.
