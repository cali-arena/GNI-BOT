"""
WhatsApp Connect — GNI. Streamlit UI for QR + connection status via FastAPI QR Bridge.
Never logs or displays the bridge token. Optional UI_PASSWORD gate.
"""
import io
import os
from datetime import timedelta

import requests
import streamlit as st

# Page config must be first Streamlit command
st.set_page_config(page_title="WhatsApp Connect — GNI", layout="centered")

# --- Config from env (never log token) ---
GNI_API_BASE_URL = (os.environ.get("GNI_API_BASE_URL") or "").strip().rstrip("/")
WA_QR_BRIDGE_TOKEN = (os.environ.get("WA_QR_BRIDGE_TOKEN") or "").strip()
UI_PASSWORD = (os.environ.get("UI_PASSWORD") or "").strip()
try:
    AUTO_REFRESH_SECONDS = int(os.environ.get("AUTO_REFRESH_SECONDS", "3"))
except ValueError:
    AUTO_REFRESH_SECONDS = 3

REQUEST_TIMEOUT = 10


def _headers():
    return {"Authorization": f"Bearer {WA_QR_BRIDGE_TOKEN}"} if WA_QR_BRIDGE_TOKEN else {}


def fetch_status():
    """GET /admin/wa/status. Returns dict or None on error."""
    if not GNI_API_BASE_URL or not WA_QR_BRIDGE_TOKEN:
        return None
    try:
        r = requests.get(
            f"{GNI_API_BASE_URL}/admin/wa/status",
            headers=_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def fetch_qr():
    """GET /admin/wa/qr. Returns dict with qr (str or None), expires_in, server_time; or None on error."""
    if not GNI_API_BASE_URL or not WA_QR_BRIDGE_TOKEN:
        return None
    try:
        r = requests.get(
            f"{GNI_API_BASE_URL}/admin/wa/qr",
            headers=_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# --- Session state: password gate ---
if "wa_ui_authenticated" not in st.session_state:
    st.session_state.wa_ui_authenticated = False

if UI_PASSWORD and not st.session_state.wa_ui_authenticated:
    st.title("WhatsApp Connect — GNI")
    pwd = st.text_input("Password", type="password", key="wa_ui_pwd")
    if st.button("Unlock"):
        if pwd == UI_PASSWORD:
            st.session_state.wa_ui_authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

# --- Require config when showing dashboard ---
if not GNI_API_BASE_URL or not WA_QR_BRIDGE_TOKEN:
    st.title("WhatsApp Connect — GNI")
    st.error("Missing configuration. Set **GNI_API_BASE_URL** and **WA_QR_BRIDGE_TOKEN** in the environment.")
    st.stop()

st.title("WhatsApp Connect — GNI")

# Manual refresh trigger
if st.button("Refresh now"):
    st.rerun()


@st.fragment(run_every=timedelta(seconds=AUTO_REFRESH_SECONDS))
def dashboard():
    status_data = fetch_status()
    qr_data = fetch_qr()

    if status_data is None:
        st.warning("API unreachable. Check **GNI_API_BASE_URL** and network. Retry in a moment.")
        return

    connected = status_data.get("connected", False)
    last_reason = status_data.get("lastDisconnectReason")

    # Status pill
    if connected:
        st.success("Connected ✅")
    elif qr_data and qr_data.get("qr"):
        st.info("Waiting for QR")
    else:
        st.error("Disconnected")

    if last_reason:
        st.caption(f"Last disconnect: {last_reason}")

    # QR block: only when not connected and API returned a QR
    qr_string = qr_data.get("qr") if qr_data else None
    if not connected and qr_string:
        try:
            import qrcode
            img = qrcode.make(qr_string)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            st.image(buf, caption="Scan with WhatsApp on the admin phone")
        except Exception:
            st.caption("QR could not be rendered.")
        st.caption("QR expires quickly; refresh if needed.")
    elif connected:
        st.caption("Session active. QR hidden.")


dashboard()

if UI_PASSWORD:
    st.divider()
    if st.button("Lock"):
        st.session_state.wa_ui_authenticated = False
        st.rerun()
