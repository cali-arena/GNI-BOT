"""
Streamlit UI: 1) Login (email + password, JWT in session). 2) WhatsApp Connect (status, QR, auto-refresh).
No backend config in UI. No debug or tracebacks. All errors → short user-friendly message.
"""
import io
import time
from pathlib import Path
import streamlit as st

from src.api_base import get_api_base_url
from src.http import get as http_get, post as http_post

st.set_page_config(page_title="WhatsApp Connect", layout="centered", initial_sidebar_state="expanded")

for key in ("token", "logged_in", "email"):
    if key not in st.session_state:
        st.session_state[key] = None

base = get_api_base_url().rstrip("/")


def _headers(token: str):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _sanitize_disconnect_reason(reason: str) -> str:
    """Generic text only; no URLs or technical details."""
    if not reason or not isinstance(reason, str):
        return "Connection was closed."
    s = reason.strip()
    if "http" in s.lower() or "://" in s or "localhost" in s.lower():
        return "Connection was closed."
    return s[:200] if len(s) > 200 else s


def logout():
    st.session_state.token = None
    st.session_state.logged_in = False
    st.session_state.email = None
    st.rerun()


# --- Page 1: Login ---
if not st.session_state.get("logged_in") or not st.session_state.get("token"):
    _logo_path = Path(__file__).resolve().parent / "logo.jpg"
    if _logo_path.exists():
        st.image(str(_logo_path), use_column_width=True)
    st.title("WhatsApp Connect")
    st.subheader("Log in")
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email", autocomplete="email")
        password = st.text_input("Password", type="password", key="login_password", autocomplete="current-password")
        if st.form_submit_button("Login"):
            e = (email or "").strip()
            p = (password or "")
            if not e or not p:
                st.error("Email and password required.")
            else:
                data, err, code = http_post(f"{base}/auth/login", {"email": e, "password": p}, headers=_headers(""))
                if code == 401:
                    st.error("Invalid email or password.")
                elif err:
                    st.error(err)
                elif data and isinstance(data, dict) and data.get("access_token"):
                    st.session_state.token = data["access_token"]
                    st.session_state.logged_in = True
                    st.session_state.email = e
                    st.rerun()
                else:
                    st.error("Something went wrong. Please try again later.")
    st.stop()

# --- Page 2: WhatsApp Connect ---
token = (st.session_state.get("token") or "").strip()

# Sidebar: logo, no backend config, logout
_logo_path = Path(__file__).resolve().parent / "logo.jpg"
if _logo_path.exists():
    st.sidebar.image(str(_logo_path), use_column_width=True)
st.sidebar.title("WhatsApp Connect")
st.sidebar.caption("Logged in as **%s**" % (st.session_state.get("email") or ""))
if st.sidebar.button("Log out"):
    logout()

status_data, status_err, status_code = http_get(f"{base}/whatsapp/status", headers=_headers(token))
qr_data, qr_err, qr_code = http_get(f"{base}/whatsapp/qr", headers=_headers(token))

if status_code == 401 or qr_code == 401:
    logout()

connected = False
qr_string = None
last_reason = None
if isinstance(status_data, dict):
    connected = status_data.get("connected") is True
    s = (status_data.get("status") or "").strip().lower()
    if not connected and s == "connected":
        connected = True
    raw_reason = status_data.get("lastDisconnectReason")
    if raw_reason:
        last_reason = _sanitize_disconnect_reason(str(raw_reason))
if isinstance(qr_data, dict) and qr_data.get("qr"):
    qr_string = qr_data.get("qr")

st.title("WhatsApp Connect")

# Status badge
if connected:
    st.success("Connected")
elif qr_string:
    st.info("Waiting for QR")
else:
    st.info("Disconnected")

if last_reason:
    st.caption(last_reason)

# WhatsApp log (same locally and on Cloud)
with st.expander("WhatsApp log", expanded=False):
    status_label = "Connected" if connected else ("Waiting for QR" if qr_string else "Disconnected")
    st.text("Status: %s" % status_label)
    if connected and isinstance(status_data, dict) and (status_data.get("phone") or status_data.get("phone_e164")):
        st.text("Phone: %s" % (status_data.get("phone") or status_data.get("phone_e164") or ""))
    if last_reason:
        st.text("Last disconnect: %s" % last_reason)
    if status_err or qr_err:
        st.text("Note: %s" % (status_err or qr_err))

if status_code == 429 or qr_code == 429:
    st.warning("Too many attempts. Please try again later.")
elif status_err or qr_err:
    st.warning(status_err or qr_err)

if st.button("Connect WhatsApp", key="wa_connect"):
    with st.spinner("Starting…"):
        _, err, code = http_post(f"{base}/whatsapp/connect", {}, headers=_headers(token))
        if code == 401:
            logout()
        if code == 429:
            st.warning("Too many attempts. Please try again later.")
        elif err:
            st.error(err)
        else:
            st.success("Session started.")
            st.rerun()

if st.button("Refresh now", key="wa_refresh"):
    st.rerun()

st.divider()
st.markdown("**How to connect:** Open WhatsApp → Linked Devices → Link a device → scan QR")

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
else:
    st.caption("Waiting for QR…")

# Auto-refresh every 3 seconds when not connected
if not connected and status_code != 401 and qr_code != 401:
    time.sleep(3)
    st.rerun()
