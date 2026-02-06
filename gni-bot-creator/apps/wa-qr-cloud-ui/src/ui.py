"""
Shared UI: CSS injection and sidebar layout for GNI Streamlit Cloud app.
Use inject_app_css() once per page; use render_sidebar(role, current_page) after auth.
"""
from pathlib import Path
from typing import Literal

import streamlit as st

CurrentPage = Literal["home", "whatsapp", "monitoring", "posts"]

APP_CSS = """
<style>
/* Content max-width and centering for readability */
.main .block-container {
    max-width: 42rem;
    padding-top: 2rem;
    padding-bottom: 2rem;
}
@media (max-width: 640px) {
    .main .block-container { padding-left: 1rem; padding-right: 1rem; }
}

/* Card-style containers: border, shadow, padding, radius */
.stForm {
    border: 1px solid rgba(49, 51, 63, 0.12);
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    padding: 1.5rem 1.25rem;
    margin-bottom: 1rem;
    background: var(--background-color, #fff);
}
/* Status placeholder card (UI-only) */
.status-card {
    border: 1px solid rgba(49, 51, 63, 0.12);
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    padding: 1rem 1.25rem;
    margin: 1rem 0;
    background: var(--secondary-background-color, #f0f2f6);
    color: var(--text-color, #262730);
    font-size: 0.9rem;
}
.status-card .muted { color: rgba(49, 51, 63, 0.6); font-size: 0.85rem; }
/* Content card for page sections (e.g. WhatsApp Connect) */
.content-card {
    border: 1px solid rgba(49, 51, 63, 0.12);
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    padding: 1.25rem 1.5rem;
    margin: 1rem 0;
    background: var(--background-color, #fff);
}
/* Centered logo/title block */
.logo-title-block { text-align: center; margin-bottom: 1.5rem; }
.logo-title-block img { margin-bottom: 0.5rem; }

/* Typography: clear hierarchy */
.main h1 { font-size: 1.75rem; margin-bottom: 0.25rem; }
.main h2 { font-size: 1.25rem; margin-top: 1rem; margin-bottom: 0.5rem; }
.subtitle-muted { color: rgba(49, 51, 63, 0.65); font-size: 0.95rem; margin-bottom: 1rem; }

/* Subtle input/button area (forms already in .stForm) */
.stTextInput input, .stTextInput label { font-size: 0.95rem; }
.stButton > button {
    border-radius: 0.375rem;
    font-weight: 500;
    transition: background 0.15s ease;
}

/* Sidebar: section labels and spacing */
[data-testid="stSidebar"] .stMarkdown { margin-bottom: 0.25rem; }
[data-testid="stSidebar"] section:first-of-type { padding-top: 0.5rem; }
.sidebar-section-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: rgba(49, 51, 63, 0.6);
    margin: 0.75rem 0 0.25rem 0;
}
.sidebar-current-hint {
    font-size: 0.8rem;
    color: rgba(49, 51, 63, 0.55);
    margin-top: 0.25rem;
    padding: 0.25rem 0;
}
</style>
"""


def inject_app_css() -> None:
    """Inject app-wide CSS for cards, max-width, typography. Call once at top of each page."""
    st.markdown(APP_CSS, unsafe_allow_html=True)


def render_sidebar(
    role: str,
    current_page: CurrentPage,
    api_base_url: str = "",
    user_email: str = "",
) -> None:
    """
    Render the left sidebar: GNI branding, logo, user info, nav links with icons.
    Call after login (so role and user_email are set). current_page highlights where the user is.
    """
    # Logo at top (path works from app root or from pages/)
    _base = Path(__file__).resolve().parent.parent
    _logo_path = _base / "assets" / "whatsapp-logo.webp"
    if _logo_path.exists():
        st.sidebar.image(str(_logo_path), use_container_width=True)
    st.sidebar.title("GNI")
    if user_email:
        st.sidebar.caption(f"Logged in as **{user_email}**")
    if api_base_url:
        _short = (api_base_url[:28] + "…") if len(api_base_url) > 30 else api_base_url
        st.sidebar.caption(f"Backend: {_short}")

    if st.sidebar.button("Log out"):
        from src.auth import logout
        logout()
        st.rerun()
    if st.sidebar.button("Change backend URL"):
        st.session_state.api_base_url = None
        st.rerun()

    # Navigation section with current-page hint
    _current_labels = {"home": "Home", "whatsapp": "WhatsApp Connect", "monitoring": "Monitoring", "posts": "Posts"}
    st.sidebar.markdown('<p class="sidebar-section-label">Navigation</p>', unsafe_allow_html=True)
    st.sidebar.page_link("app.py", label="Home", icon="🏠")
    if role == "client":
        st.sidebar.page_link("pages/01_WhatsApp_Connect.py", label="WhatsApp Connect", icon="📱")
    st.sidebar.page_link("pages/02_Monitoring.py", label="Monitoring", icon="📊")
    st.sidebar.page_link("pages/03_Posts.py", label="Posts", icon="📝")
    if role == "admin":
        st.sidebar.page_link("pages/01_WhatsApp_Connect.py", label="WhatsApp Connect", icon="📱")
    st.sidebar.markdown(
        f'<p class="sidebar-current-hint">You\'re on: <strong>{_current_labels.get(current_page, current_page)}</strong></p>',
        unsafe_allow_html=True,
    )
