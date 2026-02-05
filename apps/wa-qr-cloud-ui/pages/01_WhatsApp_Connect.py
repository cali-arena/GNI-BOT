"""
WhatsApp Connection — per-user QR and status via JWT (/whatsapp/*).
Connect button -> POST /whatsapp/connect; poll GET /whatsapp/qr and GET /whatsapp/status every 2s.
"""
import io
import time
import streamlit as st
from src.auth import require_login
from src.config import validate_config
from src.api import post_wa_connect, get_wa_qr_user, get_wa_status_user

validate_config()
require_login()

# Sidebar: logged-in user, logout, home
st.sidebar.caption("Logged in as **%s**" % (st.session_state.get("auth_email") or "—"))
if st.sidebar.button("Log out"):
    from src.auth import logout
    logout()
    st.switch_page("app.py")
st.sidebar.page_link("app.py", label="Home", icon="🏠")

# Use JWT endpoints (per-user)
status_data, status_err = get_wa_status_user()
qr_data, qr_err = get_wa_qr_user()

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
        status_label = "Connected" if connected else ("Waiting QR" if (qr_data and (qr_data.get("qr") or (qr_data.get("status") == "qr_ready")) else "Disconnected")
if isinstance(qr_data, dict) and qr_data.get("qr"):
    qr_string = qr_data.get("qr")

st.title("WhatsApp Connection")
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

# Connect WhatsApp button
if st.button("Connect WhatsApp", key="wa_connect"):
    with st.spinner("Starting session…"):
        _, err = post_wa_connect()
        if err:
            st.error(err)
        else:
            st.success("Session started. Fetching QR…")
            st.rerun()

# Show QR when we have one and not connected
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

# Reconnect button (rate-limited on backend)
if st.button("Reconnect", key="wa_reconnect"):
    with st.spinner("Reconnecting…"):
        _, err = post_wa_connect()
        if err:
            st.error(err)
        else:
            st.success("Reconnect started.")
            st.rerun()

with st.expander("FAQ"):
    st.markdown("**Why do I need this?**")
    st.caption("This links your WhatsApp account so the bot can send/receive messages.")
    st.markdown("**How to disconnect?**")
    st.caption("In WhatsApp: Settings → Linked Devices → select this device → Log out.")

# Poll every 2 seconds when not connected (so QR/status updates)
if not connected and not (qr_err or status_err):
    time.sleep(2)
    st.rerun()
