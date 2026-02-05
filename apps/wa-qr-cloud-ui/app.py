"""
Streamlit Cloud UI: Login → WhatsApp Connect. No required secrets.
Page 1: Login (email + password). Page 2: WhatsApp Connect (QR + status, auto-refresh 3s).
"""
import io
import os
import time
import streamlit as st
import requests

# --- Config: API_BASE_URL from query param > env > placeholder ---
_PLACEHOLDER_BASE = "http://<VM_PUBLIC_IP>:8000"

def _get_query_api_base_url():
    try:
        if hasattr(st, "query_params"):
            v = st.query_params.get("api_base_url")
        else:
            v = None
        if v is None:
            return ""
        if isinstance(v, list):
            v = v[0] if v else ""
        return (v or "").strip().rstrip("/")
    except Exception:
        return ""

def _get_env_api_base_url():
    return (os.getenv("API_BASE_URL") or os.getenv("GNI_API_BASE_URL") or "").strip().rstrip("/")

def get_api_base_url():
    session_url = (st.session_state.get("api_base_url") or "").strip().rstrip("/")
    if session_url:
        return session_url
    query_url = _get_query_api_base_url()
    if query_url:
        return query_url
    env_url = _get_env_api_base_url()
    if env_url:
        return env_url
    return _PLACEHOLDER_BASE

st.set_page_config(page_title="WhatsApp Connect", layout="centered", initial_sidebar_state="expanded")

# Session state: logged_in, token, email (token never shown on screen)
for key in ("api_base_url", "token", "logged_in", "email"):
    if key not in st.session_state:
        st.session_state[key] = None

_query_url = _get_query_api_base_url()
if _query_url and not (st.session_state.get("api_base_url") or "").strip():
    st.session_state.api_base_url = _query_url

base = get_api_base_url()

# --- API helpers (errors → warning/error, never crash) ---
def _api_get(path: str, token: str):
    """GET {base}{path}. Returns (data, err, status_code)."""
    if not base or base == _PLACEHOLDER_BASE:
        return None, "Set Backend URL (query ?api_base_url=... or env API_BASE_URL)", None
    url = f"{base.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(url, headers=headers, timeout=(5, 15))
        data = r.json() if r.content else None
        if r.ok:
            return data, None, None
        detail = (data or {}).get("detail", "Request failed") if isinstance(data, dict) else "Request failed"
        return None, str(detail)[:200], r.status_code
    except requests.exceptions.Timeout:
        return None, "Request timed out.", None
    except requests.exceptions.RequestException:
        return None, "Cannot reach backend. Check URL and network.", None
    except Exception:
        return None, "Request failed.", None

def _api_post(path: str, json_body: dict, token: str):
    """POST {base}{path}. Returns (data, err, status_code)."""
    if not base or base == _PLACEHOLDER_BASE:
        return None, "Set Backend URL first.", None
    url = f"{base.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(url, json=json_body or {}, headers=headers, timeout=(5, 15))
        data = r.json() if r.content else None
        if r.ok:
            return data, None, None
        detail = (data or {}).get("detail", "Request failed") if isinstance(data, dict) else "Request failed"
        return None, str(detail)[:200], r.status_code
    except requests.exceptions.Timeout:
        return None, "Request timed out.", None
    except requests.exceptions.RequestException:
        return None, "Cannot reach backend. Check URL and network.", None
    except Exception:
        return None, "Request failed.", None

def logout():
    st.session_state.token = None
    st.session_state.logged_in = False
    st.session_state.email = None
    st.rerun()

# --- Page 1: Login ---
if not st.session_state.get("logged_in") or not st.session_state.get("token"):
    st.title("WhatsApp Connect")
    st.subheader("Log in")
    st.caption("Backend: %s" % base)
    if base == _PLACEHOLDER_BASE:
        with st.expander("Set Backend URL", expanded=True):
            url_input = st.text_input("API base URL", value=base, key="url_input")
            if st.button("Save URL"):
                u = (url_input or "").strip().rstrip("/")
                if u:
                    st.session_state.api_base_url = u
                    st.rerun()
    else:
        if st.button("Change backend URL"):
            st.session_state.api_base_url = None
            st.rerun()
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email", autocomplete="email")
        password = st.text_input("Password", type="password", key="login_password", autocomplete="current-password")
        if st.form_submit_button("Login"):
            e = (email or "").strip()
            p = (password or "")
            if not e or not p:
                st.error("Email and password required.")
            else:
                data, err, code = _api_post("/auth/login", {"email": e, "password": p}, token="")
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
                    st.error("Login failed.")
    st.stop()

# --- Page 2: WhatsApp Connect ---
token = (st.session_state.get("token") or "").strip()

st.sidebar.title("WhatsApp Connect")
st.sidebar.caption("Logged in as **%s**" % (st.session_state.get("email") or ""))
if st.sidebar.button("Log out"):
    logout()
st.sidebar.caption("Backend: %s" % base)
if st.sidebar.button("Change backend URL"):
    st.session_state.api_base_url = None
    st.rerun()

# Fetch status and QR
status_data, status_err, status_code = _api_get("/whatsapp/status", token=token)
qr_data, qr_err, qr_code = _api_get("/whatsapp/qr", token=token)

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
    last_reason = status_data.get("lastDisconnectReason")
if isinstance(qr_data, dict) and qr_data.get("qr"):
    qr_string = qr_data.get("qr")

st.title("WhatsApp Connect")

# Status
if connected:
    st.success("Connected ✅")
    phone = (status_data or {}).get("phone")
    if phone:
        st.caption("Phone: %s" % phone)
elif qr_string:
    st.info("Waiting for QR")
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
        _, err, code = _api_post("/whatsapp/connect", {}, token=token)
        if code == 401:
            logout()
        if code == 429:
            st.warning("Too many attempts, wait a bit.")
        elif err:
            st.error(err)
        else:
            st.success("Session started.")
            st.rerun()

if st.button("Refresh now", key="wa_refresh"):
    st.rerun()

st.divider()

# Instructions
st.markdown("**How to connect:** Open WhatsApp → Linked Devices → Link a device → scan QR")

# QR image (raw string → qrcode + PIL)
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

# Auto-refresh every 3 seconds when not connected (no extra deps)
if not connected and status_code != 401 and qr_code != 401:
    time.sleep(3)
    st.rerun()
