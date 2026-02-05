"""
Home — GNI Streamlit app. Config from secrets; auth in session only; role-based nav.
"""
import streamlit as st

from src.config import get_config, validate_config
from src.auth import seed_user_if_needed, login, logout, current_user, require_login
from src.api import get_health

st.set_page_config(page_title="GNI — Home", layout="centered", initial_sidebar_state="expanded")

# --- 1) Validate config (required keys); then seed user from secrets ---
validate_config()
seed_user_if_needed()

# --- 2) Session state for auth ---
for key in ("auth_user", "auth_role", "auth_email"):
    if key not in st.session_state:
        st.session_state[key] = None

# --- 3) Login gate ---
if not st.session_state.auth_email:
    st.title("GNI")
    st.subheader("Log in")
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email", autocomplete="email")
        password = st.text_input("Password", type="password", key="login_password", autocomplete="current-password")
        submitted = st.form_submit_button("Log in")
        if submitted:
            if login((email or "").strip(), password or ""):
                st.rerun()
            else:
                st.error("Invalid email or password.")
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
