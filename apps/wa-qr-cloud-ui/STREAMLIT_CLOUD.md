# Streamlit Cloud — point app at your VM API

1. Open **https://share.streamlit.io** → your app → **⋮** → **Settings**.
2. Open the **Secrets** tab and add (use your VM IP or HTTPS URL):
   ```toml
   GNI_API_BASE_URL = "http://217.216.84.81:8000"
   ```
3. **Save**. The app will redeploy and use this URL for login and WhatsApp.

**If the app is on HTTPS** (e.g. `*.streamlit.app`), the API URL **must be HTTPS** or the browser will block requests. Use a reverse proxy or tunnel to expose your API over HTTPS.

**Create a user** on the VM first (once the API is up):
```bash
curl -s -X POST http://YOUR_VM_IP:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"YourPassword"}'
```
Then log in on the Streamlit app with that email and password.
