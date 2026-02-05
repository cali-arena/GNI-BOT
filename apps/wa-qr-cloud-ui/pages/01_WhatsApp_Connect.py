"""
WhatsApp Connection — JWT-protected: POST /whatsapp/connect, GET /whatsapp/qr, GET /whatsapp/status.
Status card, QR rendering (qrcode+PIL), polling when not connected; 401=logout, 429=rate limit warning.
Never log QR or token.
"""
import io
import time
import streamlit as st

from src.auth import require_login, logout
from src.config import validate_config
from src.api import api_get, api_post

validate_config()
require_login()

# JWT from session (never logged)
_jwt = (st.session_state.get("jwt") or st.session_state.get("auth_token") or "").strip()
if not _jwt:
    st.warning("Please log in to continue.")
    st.stop()

# Sidebar
st.sidebar.caption("Logged in as **%s**" % (st.session_state.get("email") or st.session_state.get("auth_email") or "—"))
if st.sidebar.button("Log out"):
    logout()
    st.rerun()
st.sidebar.page_link("app.py", label="Home", icon="🏠")

# --- Poll both endpoints ---
status_data, status_err, status_code = api_get("/whatsapp/status", jwt=_jwt)
qr_data, qr_err, qr_code = api_get("/whatsapp/qr", jwt=_jwt)

# 401: force logout (clear session)
if status_code == 401 or qr_code == 401:
    logout()
    st.rerun()

# Parse status
connected = False
status_label = "Disconnected"
phone = None
connected_at = None
last_reason = None
if isinstance(status_data, dict):
    s = (status_data.get("status") or "").strip().lower()
    connected = s == "connected"
    status_label = "Connected" if connected else ("Waiting for QR" if s == "qr_ready" else "Disconnected")
    phone = status_data.get("phone")
    connected_at = status_data.get("connected_at")
    last_reason = status_data.get("lastDisconnectReason")
if status_err and not status_data:
    status_label = "Error"

# QR string (never log)
qr_string = None
if isinstance(qr_data, dict) and qr_data.get("qr"):
    qr_string = qr_data.get("qr")

# --- Status card ---
st.title("WhatsApp Connection")
if connected:
    st.success("Connected ✅")
    if phone:
        st.caption("Phone: **%s**" % phone)
    if connected_at:
        st.caption("Connected at: %s" % connected_at)
elif status_label == "Waiting for QR":
    st.info("Waiting for QR")
else:
    st.info("Disconnected")
if last_reason:
    st.caption("Last disconnect: %s" % last_reason)

# API unreachable or rate limited
if status_err or qr_err:
    err_msg = status_err or qr_err
    if status_code == 429 or qr_code == 429:
        st.warning("Too many attempts, wait a bit.")
    else:
        st.error(err_msg or "API unreachable. Check connection and retry.")

st.divider()
st.subheader("How to connect")
for i, step in enumerate([
    "Open WhatsApp on your phone",
    "Settings → Linked Devices",
    "Link a Device",
    "Scan the QR code below",
], 1):
    st.markdown("%d. %s" % (i, step))

# Connect WhatsApp
if st.button("Connect WhatsApp", key="wa_connect"):
    with st.spinner("Starting session…"):
        _, err, code = api_post("/whatsapp/connect", json={}, jwt=_jwt)
        if code == 401:
            logout()
            st.rerun()
        if code == 429:
            st.warning("Too many attempts, wait a bit.")
        elif err:
            st.error(err)
        else:
            st.success("Session started. Fetching QR…")
            st.rerun()

# Reconnect (same call; warn if rate limited)
if st.button("Reconnect", key="wa_reconnect"):
    with st.spinner("Reconnecting…"):
        _, err, code = api_post("/whatsapp/connect", json={}, jwt=_jwt)
        if code == 401:
            logout()
            st.rerun()
        if code == 429:
            st.warning("Too many attempts, wait a bit.")
        elif err:
            st.error(err)
        else:
            st.success("Reconnect started.")
            st.rerun()

# --- QR rendering (never log qr_string) ---
if not connected and qr_string:
    try:
        import qrcode
        img = qrcode.make(qr_string)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        st.image(buf, caption="Scan with WhatsApp", use_container_width=False)
    except Exception:
        st.caption("QR could not be rendered.")
    st.caption("QR expires quickly; refresh if needed.")
elif connected:
    st.caption("Session active. QR hidden.")

# FAQ
with st.expander("FAQ"):
    st.markdown("**Why do I need this?**")
    st.caption("This links your WhatsApp account so the bot can send/receive messages.")
    st.markdown("**How to disconnect?**")
    st.caption("In WhatsApp: Settings → Linked Devices → select this device → Log out.")

# --- Polling: every 2 s when not connected or QR present; stop when connected ---
if not connected and status_code != 401 and qr_code != 401:
    time.sleep(2)
    st.rerun()
