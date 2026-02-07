"""
WhatsApp Connect — click Connect/Reconnect to generate QR on demand. QR persists until new click.
"""
import io
import time
from pathlib import Path

import streamlit as st

from src.api import get_wa_qr, get_wa_status, post_wa_reconnect
from src.ui import inject_app_css, render_sidebar

st.set_page_config(page_title="GNI — WhatsApp Connect", layout="centered", initial_sidebar_state="expanded")
base = (st.session_state.get("api_base_url") or "").strip().rstrip("/")
if not base:
    st.warning("Backend URL not set. Go to Home to set it.")
    st.switch_page("app.py")
inject_app_css()
render_sidebar("client", "whatsapp", api_base_url=base, user_email="")

if "wa_qr_string" not in st.session_state:
    st.session_state.wa_qr_string = None
if "wa_polling" not in st.session_state:
    st.session_state.wa_polling = False
if "wa_poll_count" not in st.session_state:
    st.session_state.wa_poll_count = 0
if "wa_poll_failed" not in st.session_state:
    st.session_state.wa_poll_failed = False

# Centered logo + title + subtitle at top
_logo = Path(__file__).parent.parent / "assets" / "whatsapp-logo.webp"
_col1, _col2, _col3 = st.columns([1, 2, 1])
with _col2:
    if _logo.exists():
        st.image(str(_logo), width=100)
    st.title("WhatsApp Connect")
    st.markdown('<p class="subtitle-muted">Link your WhatsApp account to send and receive messages.</p>', unsafe_allow_html=True)

status_data, status_err = get_wa_status()
connected = False
status_label = "Disconnected"
last_reason = None
if status_err and not status_data:
    status_label = "Error" if status_err else "Disconnected"
elif isinstance(status_data, dict):
    connected = status_data.get("connected") or status_data.get("status") == "open"
    last_reason = status_data.get("lastDisconnectReason")
    status_label = "Connected" if connected else "Disconnected"

st.subheader("Status: %s" % status_label)
if connected:
    st.success("Connected ✅")
elif status_err:
    st.error(status_err)
else:
    st.info("Disconnected — click Connect WhatsApp to show QR code")
if last_reason:
    st.caption("Last disconnect: %s" % last_reason)

st.divider()
st.subheader("How to connect")
for i, step in enumerate(["Open WhatsApp on your phone", "Settings → Linked Devices", "Link a Device", "Scan the QR code below"], 1):
    st.markdown("%d. %s" % (i, step))

MAX_POLL = 20  # ~40 seconds max wait for QR

# Connect WhatsApp: trigger reconnect, then poll for QR
if st.button("Connect WhatsApp", key="wa_connect"):
    with st.spinner("Generating QR code…"):
        _, err = post_wa_reconnect()
        if err:
            st.error(err)
        else:
            st.session_state.wa_qr_string = None
            st.session_state.wa_polling = True
            st.session_state.wa_poll_count = 0
            st.session_state.wa_poll_failed = False
    st.rerun()

# Reconnect: same as Connect — new QR on demand
if st.button("Reconnect", key="wa_reconnect"):
    with st.spinner("Generating new QR code…"):
        _, err = post_wa_reconnect()
        if err:
            st.error(err)
        else:
            st.session_state.wa_qr_string = None
            st.session_state.wa_polling = True
            st.session_state.wa_poll_count = 0
            st.session_state.wa_poll_failed = False
    st.rerun()

# Poll for QR when waiting
if st.session_state.wa_polling and not connected:
    st.session_state.wa_poll_count = st.session_state.wa_poll_count + 1
    if st.session_state.wa_poll_count > MAX_POLL:
        st.session_state.wa_polling = False
        st.session_state.wa_poll_failed = True
        st.rerun()
    else:
        st.caption("⏳ Waiting for QR… (%d/%d)" % (st.session_state.wa_poll_count, MAX_POLL))
        qr_data, qr_err = get_wa_qr()
        if isinstance(qr_data, dict) and qr_data.get("qr"):
            st.session_state.wa_qr_string = qr_data.get("qr")
            st.session_state.wa_polling = False
        elif qr_err:
            st.session_state.wa_polling = False
            st.error(qr_err)
        else:
            time.sleep(2)
            st.rerun()

if st.session_state.wa_poll_failed:
    st.warning("QR didn't appear in time. Click **Reconnect** to try again.")

# Also fetch current QR if not polling (e.g. page refresh while bot has QR)
if not connected and not st.session_state.wa_qr_string and not st.session_state.wa_polling and not st.session_state.wa_poll_failed:
    qr_data, _ = get_wa_qr()
    if isinstance(qr_data, dict) and qr_data.get("qr"):
        st.session_state.wa_qr_string = qr_data.get("qr")

# Display persistent QR
qr_string = st.session_state.wa_qr_string
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
    st.caption("QR persists until you click Reconnect for a new one.")
elif connected:
    st.caption("Session active. QR hidden.")

with st.expander("FAQ"):
    st.markdown("**Why do I need this?**")
    st.caption("This links your WhatsApp account so the bot can send/receive messages.")
    st.markdown("**How to disconnect?**")
    st.caption("In WhatsApp: Settings → Linked Devices → select this device → Log out.")
