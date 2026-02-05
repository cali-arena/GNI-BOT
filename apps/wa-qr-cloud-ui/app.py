"""
Streamlit app: Login + WhatsApp Connect only. Talks ONLY to FastAPI backend.
No mandatory secrets; never block startup. Optional API URL from env or paste in UI.
"""
import streamlit as st

from src.config import API_BASE_URL
from src.api import api_post

st.set_page_config(page_title="WhatsApp Connect", layout="centered", initial_sidebar_state="expanded")

# Session state: backend URL (env or user-pasted), auth
for key in ("api_base_url", "jwt", "logged_in", "email"):
    if key not in st.session_state:
        st.session_state[key] = None
if not st.session_state.api_base_url and API_BASE_URL:
    st.session_state.api_base_url = API_BASE_URL

def logout():
    st.session_state.jwt = None
    st.session_state.logged_in = False
    st.session_state.email = None
    st.rerun()

# --- 1) Backend URL not set: show paste input (never block) ---
base = (st.session_state.get("api_base_url") or "").strip().rstrip("/")
if not base:
    st.title("WhatsApp Connect")
    st.caption("Backend URL not set. Please paste it here:")
    with st.form("backend_url_form"):
        url_input = st.text_input("Backend URL", placeholder="https://your-api.example.com:8000", key="url_input")
        if st.form_submit_button("Save"):
            u = (url_input or "").strip().rstrip("/")
            if u:
                st.session_state.api_base_url = u
                st.rerun()
            else:
                st.warning("Enter a URL.")
    st.stop()

# --- 2) Not logged in: show login ---
if not st.session_state.get("logged_in") or not st.session_state.get("jwt"):
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
                data, err, code = api_post("/auth/login", json={"email": e, "password": p})
                if code == 401:
                    st.error("Invalid email or password.")
                elif err:
                    st.error(err)
                elif data and isinstance(data, dict) and data.get("access_token"):
                    st.session_state.jwt = data["access_token"]
                    st.session_state.logged_in = True
                    st.session_state.email = e
                    st.rerun()
                else:
                    st.error("Login failed.")
    st.caption("Backend: %s" % base)
    st.stop()

# --- 3) Logged in: sidebar + link to WhatsApp Connect ---
st.sidebar.title("WhatsApp Connect")
st.sidebar.caption("Logged in as **%s**" % (st.session_state.get("email") or ""))
if st.sidebar.button("Log out"):
    logout()
st.sidebar.caption("Backend: %s" % base)
if st.sidebar.button("Change backend URL"):
    st.session_state.api_base_url = None
    st.rerun()
st.sidebar.page_link("pages/01_WhatsApp_Connect.py", label="WhatsApp Connect", icon="📱")

st.title("Home")
st.success("Logged in.")
st.page_link("pages/01_WhatsApp_Connect.py", label="Open WhatsApp Connect", icon="📱")
