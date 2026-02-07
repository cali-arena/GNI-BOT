"""
WhatsApp Connect — Connect/Reconnect to generate QR. Manual Refresh to avoid rate limiting.
"""
import io
import time
from datetime import datetime
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
if "wa_last_refresh" not in st.session_state:
    st.session_state.wa_last_refresh = "Never"
if "wa_refresh_count" not in st.session_state:
    st.session_state.wa_refresh_count = 0
if "wa_pause_auto" not in st.session_state:
    st.session_state.wa_pause_auto = False
if "wa_refresh_msg" not in st.session_state:
    st.session_state.wa_refresh_msg = None
if "wa_connect_clicked" not in st.session_state:
    st.session_state.wa_connect_clicked = False

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
    if status_err and "rate limit" in status_err.lower():
        st.error("Rate limited. Wait 30 seconds, then click Refresh.")
    else:
        st.error(status_err)
else:
    st.info("Disconnected — click Connect WhatsApp to show QR code")
if last_reason:
    st.caption("Last disconnect: %s" % last_reason)

st.divider()
st.subheader("How to connect")
for i, step in enumerate(["Open WhatsApp on your phone", "Settings → Linked Devices", "Link a Device", "Scan the QR code below"], 1):
    st.markdown("%d. %s" % (i, step))

# Prominent CTA when no QR yet and user never started
if not connected and not st.session_state.wa_qr_string and not st.session_state.wa_connect_clicked:
    st.info("👆 **Click Connect WhatsApp below** to start. Wait ~30 seconds for the QR to appear.")

INITIAL_WAIT = 30
RETRY_WAIT = 10
MAX_RETRIES_AFTER_CONNECT = 2
MAX_AUTO_REFRESH = 3
REFRESH_INTERVAL = 15


def _do_connect_flow():
    """Shared flow: reconnect, wait, fetch QR (with retries)."""
    st.session_state.wa_connect_clicked = True
    st.session_state.wa_qr_string = None
    st.session_state.wa_refresh_count = 0
    st.session_state.wa_pause_auto = False
    _, err = post_wa_reconnect()
    if err:
        return err, None
    time.sleep(INITIAL_WAIT)
    for attempt in range(MAX_RETRIES_AFTER_CONNECT + 1):
        qr_data, qr_err = get_wa_qr()
        if qr_err:
            return qr_err, None
        if isinstance(qr_data, dict) and qr_data.get("qr"):
            return None, qr_data.get("qr")
        if attempt < MAX_RETRIES_AFTER_CONNECT:
            time.sleep(RETRY_WAIT)
    return None, None  # No error, just no QR yet


# Connect WhatsApp: trigger reconnect, wait, fetch QR (with retries)
if st.button("Connect WhatsApp", key="wa_connect"):
    with st.spinner("Starting… waiting ~30–50 seconds for QR…"):
        err, qr = _do_connect_flow()
        if err:
            if "rate limit" in (err or "").lower():
                st.warning("Rate limited. Click Refresh in 30 seconds.")
            else:
                st.error(err)
        elif qr:
            st.session_state.wa_qr_string = qr
            st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
        else:
            st.warning("QR not ready yet. Click **Refresh QR** in 15 seconds.")
    st.rerun()

# Reconnect: same as Connect
if st.button("Reconnect", key="wa_reconnect"):
    with st.spinner("Starting… waiting ~30–50 seconds for QR…"):
        err, qr = _do_connect_flow()
        if err:
            if "rate limit" in (err or "").lower():
                st.warning("Rate limited. Click Refresh in 30 seconds.")
            else:
                st.error(err)
        elif qr:
            st.session_state.wa_qr_string = qr
            st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
        else:
            st.warning("QR not ready yet. Click **Refresh QR** in 15 seconds.")
    st.rerun()

# Manual Refresh button — avoids rate limiting
if not connected:
    st.caption("Last refresh: %s" % st.session_state.wa_last_refresh)
    if st.session_state.wa_refresh_msg:
        st.warning(st.session_state.wa_refresh_msg)
        st.session_state.wa_refresh_msg = None
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔄 Refresh QR", key="manual_refresh"):
            qr_data, qr_err = get_wa_qr()
            if qr_err:
                st.session_state.wa_refresh_msg = "⚠️ " + (qr_err if "rate limit" not in (qr_err or "").lower() else "Rate limited. Try again in 30 seconds.")
            elif isinstance(qr_data, dict) and qr_data.get("qr"):
                st.session_state.wa_qr_string = qr_data.get("qr")
                st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
                st.session_state.wa_refresh_msg = None
            else:
                st.session_state.wa_refresh_msg = "No QR yet. Click Connect WhatsApp first, then wait ~30 sec."
            st.rerun()

# Initial fetch: if no QR in session, try once (e.g. page refresh while bot has QR)
if not connected and not st.session_state.wa_qr_string and st.session_state.wa_refresh_count == 0 and not st.session_state.wa_pause_auto:
    qr_data, _ = get_wa_qr()
    if isinstance(qr_data, dict) and qr_data.get("qr"):
        st.session_state.wa_qr_string = qr_data.get("qr")
        st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")

# Limited auto-refresh (only when no QR yet, max 3 times, 15s interval)
if not connected and not st.session_state.wa_qr_string and not st.session_state.wa_pause_auto:
    if st.session_state.wa_refresh_count < MAX_AUTO_REFRESH:
        st.caption("⏳ Auto-refreshing… (%d/%d)" % (st.session_state.wa_refresh_count + 1, MAX_AUTO_REFRESH))
        time.sleep(REFRESH_INTERVAL)
        st.session_state.wa_refresh_count += 1
        qr_data, qr_err = get_wa_qr()
        if isinstance(qr_data, dict) and qr_data.get("qr"):
            st.session_state.wa_qr_string = qr_data.get("qr")
            st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
        st.rerun()
    else:
        st.session_state.wa_pause_auto = True
        if st.session_state.wa_connect_clicked:
            st.warning("QR didn't appear in time. Click **Refresh QR** or **Reconnect** to try again.")
        else:
            st.warning("👆 Click **Connect WhatsApp** above to start. Wait ~30 seconds for the QR to appear.")

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
