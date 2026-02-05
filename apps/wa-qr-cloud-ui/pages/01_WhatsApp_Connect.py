"""
WhatsApp Connect — QR and status. Client role only. Bearer token; never log QR.
"""
import io
import time
import streamlit as st
from src.auth import require_login, require_role
from src.config import validate_config
from src.api import get_wa_status, get_wa_qr

validate_config()
require_login()
require_role(["client"])

REFRESH_COOLDOWN_SECONDS = 10
if "wa_qr_last_refresh" not in st.session_state:
    st.session_state.wa_qr_last_refresh = 0

def _can_refresh():
    return (time.time() - st.session_state.wa_qr_last_refresh) >= REFRESH_COOLDOWN_SECONDS
def _seconds_until_refresh():
    return max(0, int(REFRESH_COOLDOWN_SECONDS - (time.time() - st.session_state.wa_qr_last_refresh)))

status_data, _ = get_wa_status()
qr_data, _ = get_wa_qr()
connected = status_data.get("connected", False) if status_data else False
qr_string = qr_data.get("qr") if qr_data else None
last_reason = status_data.get("lastDisconnectReason") if status_data else None

st.title("WhatsApp Connect")
st.subheader("How to connect")
steps = [
    "Open WhatsApp on your phone",
    "Settings -> Linked Devices",
    "Link a Device",
    "Scan the QR code below",
]
for i, step in enumerate(steps, 1):
    st.markdown("%d. %s" % (i, step))
st.progress(1.0, text="Step 4 of 4 — Scan the QR code")
st.divider()

if connected:
    st.success("Connected")
elif qr_string:
    st.info("Waiting for scan")
else:
    st.error("Disconnected / expired")
if last_reason:
    st.caption("Last disconnect: " + str(last_reason))

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
    st.caption("QR expires quickly; use Refresh QR if it stops working.")
elif connected:
    st.caption("Session active. QR hidden.")

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    if _can_refresh():
        if st.button("Refresh QR", key="wa_refresh_qr"):
            st.session_state.wa_qr_last_refresh = time.time()
            st.rerun()
    else:
        st.button("Refresh QR", key="wa_refresh_qr", disabled=True, help="Wait %ds" % _seconds_until_refresh())
with col2:
    if not _can_refresh():
        st.caption("Available in %d s" % _seconds_until_refresh())

with st.expander("FAQ"):
    st.markdown("**Why do I need this?**")
    st.caption("This links the GNI bot to WhatsApp.")
    st.markdown("**How to disconnect?**")
    st.caption("In WhatsApp: Settings -> Linked Devices -> select this device -> Log out.")

if status_data is None and not connected:
    st.warning("API unreachable. Check GNI_API_BASE_URL and network.")
