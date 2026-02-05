# WhatsApp Connect — Login + QR

Streamlit app: **Login** and **WhatsApp Connect** (QR + status). Talks only to your FastAPI backend.

- **No mandatory secrets.** App boots immediately. Optional env `GNI_API_BASE_URL` or paste backend URL in the UI.
- Login: email/password → `POST {backend}/auth/login` → JWT in session.
- WhatsApp Connect: connect, poll status/QR via backend; QR rendered with qrcode+PIL.

## Streamlit Cloud

- **App path (entrypoint):** `apps/wa-qr-cloud-ui/app.py` (from repo root).
- **In Streamlit Cloud:** set **Root directory** to `apps/wa-qr-cloud-ui`, **Main file** to `app.py`.
- **Secrets:** None required. Optional env `GNI_API_BASE_URL`. If empty, user pastes backend URL on first load.

## Run locally

```bash
cd apps/wa-qr-cloud-ui
pip install -r requirements.txt
streamlit run app.py
```

Set `GNI_API_BASE_URL` or paste the backend URL in the app when prompted.
