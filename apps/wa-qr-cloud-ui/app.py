"""
Home — GNI Streamlit app. Login via API (POST /auth/login), then WhatsApp / Monitoring / Posts.
"""
import streamlit as st

from src.config import get_config, validate_config, has_seed_for_legacy
from src.auth import seed_user_if_needed, login as legacy_login, logout, require_login
from src.api import get_health, post_auth_login, get_auth_me

st.set_page_config(page_title="GNI — Home", layout="centered", initial_sidebar_state="expanded")

# --- 1) Validate config (GNI_API_BASE_URL required); optional seed for legacy ---
validate_config()
if has_seed_for_legacy():
    seed_user_if_needed()

# --- 2) Session state for auth ---
for key in ("auth_user", "auth_role", "auth_email", "auth_token"):
    if key not in st.session_state:
        st.session_state[key] = None

# --- 3) Login gate: prefer API login; fallback to legacy in-app login ---
if not st.session_state.get("auth_token") and not st.session_state.get("auth_email"):
    st.title("GNI")
    st.subheader("Log in")
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email", autocomplete="email")
        password = st.text_input("Password", type="password", key="login_password", autocomplete="current-password")
        submitted = st.form_submit_button("Log in")
        if submitted:
            email = (email or "").strip()
            password = password or ""
            if not email or not password:
                st.error("Email and password required.")
            else:
                body, err = post_auth_login(email, password)
                if err:
                    # Fallback: try legacy in-app login (seed user)
                    if legacy_login(email, password):
                        st.switch_page("pages/01_WhatsApp_Connect.py")
                    else:
                        st.error(err or "Invalid email or password.")
                else:
                    token = (body or {}).get("access_token") if isinstance(body, dict) else None
                    if token:
                        st.session_state.auth_token = token
                        me, me_err = get_auth_me()
                        if not me_err and isinstance(me, dict):
                            st.session_state.auth_email = me.get("email") or email
                            st.session_state.auth_role = "client"
                        else:
                            st.session_state.auth_email = email
                        st.switch_page("pages/01_WhatsApp_Connect.py")
                    else:
                        st.error("Login failed.")
    st.stop()

# --- 4) Role-based sidebar (only show allowed pages) ---
role = (st.session_state.get("auth_role") or "client").strip().lower()
st.sidebar.title("GNI")
st.sidebar.caption(f"Logged in as **{st.session_state.auth_email}**")
if st.sidebar.button("Log out"):
    logout()
    st.rerun()

# Nav: client = WhatsApp Connect, Monitoring, Posts; admin = Monitoring, Posts, optionally WhatsApp
if role == "client":
    st.sidebar.page_link("pages/01_WhatsApp_Connect.py", label="WhatsApp Connect", icon="📱")
st.sidebar.page_link("pages/02_Monitoring.py", label="Monitoring", icon="📊")
st.sidebar.page_link("pages/03_Posts.py", label="Posts", icon="📝")
if role == "admin":
    st.sidebar.page_link("pages/01_WhatsApp_Connect.py", label="WhatsApp Connect", icon="📱")

# --- 5) Main: header + Config OK + API health + quick links ---
st.title("Home")
st.success("✅ Config OK — Required secrets are set.")

# API health
health_data, health_err = get_health()
if health_err:
    st.warning(f"⚠️ API health: {health_err}")
else:
    status = health_data.get("status", "ok") if isinstance(health_data, dict) else "ok"
    st.success(f"✅ API health: **{status}**")

# Quick links / status cards
st.subheader("Quick links")
cols = st.columns(3)
with cols[0]:
    st.page_link("pages/01_WhatsApp_Connect.py", label="WhatsApp Connect", icon="📱")
with cols[1]:
    st.page_link("pages/02_Monitoring.py", label="Monitoring", icon="📊")
with cols[2]:
    st.page_link("pages/03_Posts.py", label="Posts", icon="📝")
