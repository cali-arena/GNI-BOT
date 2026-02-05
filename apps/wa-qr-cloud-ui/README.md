# WhatsApp Connect — Login + QR

Streamlit app: **Login** and **WhatsApp Connect** (QR + status). Talks only to your FastAPI backend.

- **No secrets required.** App boots immediately. Use query param `?api_base_url=...` or env `API_BASE_URL` (optional).
- Login: email/password → `POST {backend}/auth/login` → token in session (never shown on screen).
- WhatsApp Connect: connect, poll status/QR via backend; QR rendered with qrcode+PIL.

## Run locally

**From repo root (recommended for Streamlit Cloud parity):**

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

**Point to VM backend:** Use `?api_base_url=http://VM_IP:8000` in the URL, or set env `API_BASE_URL`. No `.streamlit/secrets.toml` or other secrets needed.

## Streamlit Cloud

- **Main file:** `streamlit_app.py` (at repo root).
- **Requirements file:** `requirements-streamlit.txt`.
- **Secrets:** None required. Optional env `API_BASE_URL`.
