"""
Home - GNI Streamlit app. Login via API (POST /auth/login), then WhatsApp / Monitoring / Posts.
Syntax check: python -m py_compile app.py
"""
import streamlit as st

from src.config import validate_config, has_seed_for_legacy
from src.auth import seed_user_if_needed, logout, require_login
from src.api import api_post, get_health

st.set_page_config(page_title="GNI — Home", layout="centered", initial_sidebar_state="expanded")

# --- 1) Validate config (GNI_API_BASE_URL required); optional seed for legacy ---
validate_config()
if has_seed_for_legacy():
    seed_user_if_needed()

# --- 2) Session state: jwt + logged_in (primary); email from login input; keep auth_token/auth_email for pages ---
for key in ("jwt", "logged_in", "email", "auth_user", "auth_role", "auth_email", "auth_token"):
    if key not in st.session_state:
        st.session_state[key] = None
if st.session_state.get("jwt") and st.session_state.get("logged_in"):
    # Keep auth_token/auth_email in sync for pages that use require_login / api_get_jwt
    st.session_state.auth_token = st.session_state.jwt
    if st.session_state.get("email"):
        st.session_state.auth_email = st.session_state.email


def show_login() -> None:
    """Email + password form; on submit POST /auth/login. On success: set session_state jwt, logged_in, email and rerun. On fail: st.error."""
    st.title("GNI")
    st.subheader("Log in")
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email", autocomplete="email")
        password = st.text_input("Password", type="password", key="login_password", autocomplete="current-password")
        submitted = st.form_submit_button("Login")
        if submitted:
            email = (email or "").strip()
            password = (password or "").strip()
            if not email or not password:
                st.error("Email and password required.")
            else:
                data, err, _ = api_post("/auth/login", json={"email": email, "password": password})
                if err:
                    st.error(err)
                elif data and isinstance(data, dict) and data.get("access_token"):
                    st.session_state["jwt"] = data["access_token"]
                    st.session_state["logged_in"] = True
                    st.session_state["email"] = email
                    st.session_state["auth_token"] = data["access_token"]
                    st.session_state["auth_email"] = email
                    st.session_state["auth_role"] = "client"
                    st.rerun()
                else:
                    st.error("Login failed.")


# --- 3) Login gate: show login if not logged in ---
if not st.session_state.get("logged_in") and not st.session_state.get("jwt"):
    show_login()
    st.stop()

# --- 4) Sidebar: logged in as <email>, logout button, nav ---
role = (st.session_state.get("auth_role") or "client").strip().lower()
st.sidebar.title("GNI")
st.sidebar.caption("Logged in as **%s**" % (st.session_state.get("email") or st.session_state.get("auth_email") or "—"))
if st.sidebar.button("Log out"):
    logout()
    st.rerun()

if role == "client":
    st.sidebar.page_link("pages/01_WhatsApp_Connect.py", label="WhatsApp Connect", icon="📱")
st.sidebar.page_link("pages/02_Monitoring.py", label="Monitoring", icon="📊")
st.sidebar.page_link("pages/03_Posts.py", label="Posts", icon="📝")
if role == "admin":
    st.sidebar.page_link("pages/01_WhatsApp_Connect.py", label="WhatsApp Connect", icon="📱")

# --- 5) Main: header + API health + quick links ---
st.title("Home")
st.success("✅ Config OK — Required secrets are set.")

health_data, health_err = get_health()
if health_err:
    st.warning("⚠️ API health: %s" % health_err)
else:
    status = health_data.get("status", "ok") if isinstance(health_data, dict) else "ok"
    st.success("✅ API health: **%s**" % status)

st.subheader("Quick links")
cols = st.columns(3)
with cols[0]:
    st.page_link("pages/01_WhatsApp_Connect.py", label="WhatsApp Connect", icon="📱")
with cols[1]:
    st.page_link("pages/02_Monitoring.py", label="Monitoring", icon="📊")
with cols[2]:
    st.page_link("pages/03_Posts.py", label="Posts", icon="📝")
