"""
WhatsApp Connect: QR + status. Talks ONLY to FastAPI (whatsapp/connect, whatsapp/status, whatsapp/qr).
Never talks to whatsapp-bot. JWT from session; 401=logout, 429=rate limit warning.
"""
import io
import sys
import time
from pathlib import Path

# Ensure app root is on path so "src" resolves when this page is run directly
_app_root = Path(__file__).resolve().parent.parent
if str(_app_root) not in sys.path:
    sys.path.insert(0, str(_app_root))

import streamlit as st

from src.api import api_get, api_post

# Require login
jwt = (st.session_state.get("jwt") or "").strip()
if not jwt:
    st.warning("Please log in first.")
    st.switch_page("app.py")

base = (st.session_state.get("api_base_url") or "").strip().rstrip("/")
if not base:
    st.warning("Backend URL not set. Go to Home to set it.")
    st.switch_page("app.py")

def logout():
    st.session_state.jwt = None
    st.session_state.logged_in = False
    st.session_state.email = None
    st.switch_page("app.py")

# Sidebar
st.sidebar.caption("Logged in as **%s**" % (st.session_state.get("email") or ""))
if st.sidebar.button("Log out"):
    logout()
st.sidebar.page_link("app.py", label="Home", icon="🏠")

# Poll backend (FastAPI) - never whatsapp-bot
status_data, status_err, status_code = api_get("/whatsapp/status", jwt=jwt)
qr_data, qr_err, qr_code = api_get("/whatsapp/qr", jwt=jwt)

# 401: force logout
if status_code == 401 or qr_code == 401:
    logout()

# Parse status
connected = False
qr_string = None
last_reason = None
if isinstance(status_data, dict):
    s = (status_data.get("status") or "").strip().lower()
    connected = s == "connected"
    last_reason = status_data.get("lastDisconnectReason")
if isinstance(qr_data, dict) and qr_data.get("qr"):
    qr_string = qr_data.get("qr")

# Title and status badge
st.title("WhatsApp Connect")
if connected:
    st.success("Connected ✅")
elif qr_string:
    st.info("Waiting for QR…")
else:
    st.info("Disconnected")
if last_reason:
    st.caption("Last disconnect: %s" % last_reason)

if status_code == 429 or qr_code == 429:
    st.warning("Too many attempts, wait a bit.")
elif status_err or qr_err:
    st.warning(status_err or qr_err)

# Connect button
if st.button("Connect WhatsApp", key="wa_connect"):
    with st.spinner("Starting…"):
        _, err, code = api_post("/whatsapp/connect", json={}, jwt=jwt)
        if code == 401:
            logout()
        if code == 429:
            st.warning("Too many attempts, wait a bit.")
        elif err:
            st.error(err)
        else:
            st.success("Session started.")
            st.rerun()

# Refresh now
if st.button("Refresh now", key="wa_refresh"):
    st.rerun()

st.divider()

# QR image (never log qr_string)
if connected:
    st.caption("Session active. QR hidden.")
elif qr_string:
    try:
        import qrcode
        img = qrcode.make(qr_string)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        st.image(buf, caption="Scan with WhatsApp", use_container_width=False)
    except Exception:
        st.caption("QR could not be rendered.")
    st.markdown("**Scan this QR with WhatsApp (admin phone).**")
else:
    st.caption("Waiting for QR…")

# Poll every 2–3 seconds when not connected
if not connected and status_code != 401 and qr_code != 401:
    time.sleep(2)
    st.rerun()
