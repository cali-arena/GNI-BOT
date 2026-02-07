"""
WhatsApp Connect — per-user QR and status via JWT (/whatsapp/*).
Connect button -> POST /whatsapp/connect; poll GET /whatsapp/qr and GET /whatsapp/status.
"""
import io
import time
from pathlib import Path

import streamlit as st

from src.api import get_wa_qr, get_wa_status
from src.ui import inject_app_css, render_sidebar

st.set_page_config(page_title="GNI — WhatsApp Connect", layout="centered", initial_sidebar_state="expanded")
base = (st.session_state.get("api_base_url") or "").strip().rstrip("/")
if not base:
    st.warning("Backend URL not set. Go to Home to set it.")
    st.switch_page("app.py")
inject_app_css()
render_sidebar("client", "whatsapp", api_base_url=base, user_email="")

# Centered logo + title + subtitle at top
_logo = Path(__file__).parent.parent / "assets" / "whatsapp-logo.webp"
_col1, _col2, _col3 = st.columns([1, 2, 1])
with _col2:
    if _logo.exists():
        st.image(str(_logo), width=100)
    st.title("WhatsApp Connect")
    st.markdown('<p class="subtitle-muted">Link your WhatsApp account to send and receive messages.</p>', unsafe_allow_html=True)

# Uses /admin/wa/status and /admin/wa/qr with WA_QR_BRIDGE_TOKEN (set in Streamlit secrets)
status_data, status_err = get_wa_status()
qr_data, qr_err = get_wa_qr()

connected = False
qr_string = None
status_label = "Disconnected"
last_reason = None
if status_err and not status_data:
    status_label = "Error" if status_err else "Disconnected"
else:
    if isinstance(status_data, dict):
        connected = status_data.get("connected") or status_data.get("status") == "connected"
        last_reason = status_data.get("lastDisconnectReason")
        status_label = "Connected" if connected else ("Waiting QR" if (qr_data and (qr_data.get("qr") or qr_data.get("status") == "qr_ready")) else "Disconnected")
if isinstance(qr_data, dict) and qr_data.get("qr"):
    qr_string = qr_data.get("qr")

st.subheader("Status: %s" % status_label)
if connected:
    st.success("Connected ✅")
    phone = (status_data or {}).get("phone")
    if phone:
        st.caption("Phone: %s" % phone)
elif qr_err or status_err:
    st.error(status_err or qr_err or "Disconnected")
else:
    st.info("Waiting QR" if qr_string else "Disconnected")
if last_reason:
    st.caption("Last disconnect: %s" % last_reason)

st.divider()
st.subheader("How to connect")
steps = [
    "Open WhatsApp on your phone",
    "Settings → Linked Devices",
    "Link a Device",
    "Scan the QR code below",
]
for i, step in enumerate(steps, 1):
    st.markdown("%d. %s" % (i, step))

if st.button("Connect WhatsApp", key="wa_connect"):
    st.rerun()

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
    st.caption("QR expires quickly. Page refreshes every 2 seconds.")
elif connected:
    st.caption("Session active. QR hidden.")

if st.button("Reconnect", key="wa_reconnect"):
    st.rerun()

with st.expander("FAQ"):
    st.markdown("**Why do I need this?**")
    st.caption("This links your WhatsApp account so the bot can send/receive messages.")
    st.markdown("**How to disconnect?**")
    st.caption("In WhatsApp: Settings → Linked Devices → select this device → Log out.")

if not connected and not (qr_err or status_err):
    time.sleep(2)
    st.rerun()
