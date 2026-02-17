"""
WhatsApp Connect — QR shown ONLY when NOT connected.
On load: GET /admin/wa/status. If connected → hide QR, show "Connected ✅".
If not connected → GET /admin/wa/qr, render QR or "Waiting for QR...".
No automatic QR polling when connected.
"""
import io
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

from src.api import clear_wa_cache, get_wa_qr, get_wa_status, post_wa_reconnect
from src.ui import inject_app_css, render_sidebar
from src.config import get_config

# No QR caching across sessions
POLL_INTERVALS = [3, 5, 5, 8, 10, 12, 15, 15]
POLL_MAX_WAIT = 120

st.set_page_config(page_title="GNI — WhatsApp Connect", layout="centered", initial_sidebar_state="expanded")

# API base URL from env (default http://api:8000)
base = (st.session_state.get("api_base_url") or "").strip().rstrip("/")
if not base:
    base = (get_config().get("API_BASE_URL") or get_config().get("GNI_API_BASE_URL") or "http://api:8000").strip().rstrip("/")
    st.session_state["api_base_url"] = base
if not base:
    st.warning("API base URL not set. Set API_BASE_URL or GNI_API_BASE_URL in env/secrets (default: http://api:8000).")
    st.switch_page("app.py")

wa_token = (get_config().get("WA_QR_BRIDGE_TOKEN") or "").strip()
if not wa_token:
    st.error("Missing WA_QR_BRIDGE_TOKEN")
    st.caption("Configure WA_QR_BRIDGE_TOKEN in Streamlit Cloud Secrets.")
    st.stop()

inject_app_css()
render_sidebar("client", "whatsapp", api_base_url=base, user_email="")

# Session state
for key, default in [
    ("wa_qr_string", None),
    ("wa_last_refresh", "Never"),
    ("wa_polling", False),
    ("wa_poll_started_at", 0.0),
    ("wa_poll_count", 0),
    ("wa_refresh_msg", None),
    ("wa_connect_clicked", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# --- 1) On page load: GET /admin/wa/status ---
status_data, status_err = get_wa_status()
connected = False
last_reason = None
server_time = None
if isinstance(status_data, dict):
    connected = bool(status_data.get("connected")) or (status_data.get("status") or "").strip().lower() == "connected"
    last_reason = status_data.get("lastDisconnectReason")
    server_time = status_data.get("server_time")

# --- 2) Status indicator: green badge connected, red badge disconnected ---
_col1, _col2 = st.columns([1, 3])
with _col1:
    if connected:
        st.markdown('<span style="background:#22c55e;color:white;padding:4px 12px;border-radius:6px;">✅ Connected</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="background:#ef4444;color:white;padding:4px 12px;border-radius:6px;">❌ Disconnected</span>', unsafe_allow_html=True)

# --- Header ---
_logo = Path(__file__).parent.parent / "assets" / "whatsapp-logo.webp"
with _col2:
    if _logo.exists():
        st.image(str(_logo), width=80)
st.title("WhatsApp Connect")
st.markdown('<p class="subtitle-muted">Link your WhatsApp account.</p>', unsafe_allow_html=True)

# --- 3) If connected: show success, DO NOT call /wa/qr ---
if connected:
    st.success("WhatsApp Connected ✅")
    st.write("Session active. QR hidden.")
    if server_time:
        st.caption("Server time: %s" % server_time)
    st.divider()
    for i, step in enumerate(["Open WhatsApp", "Settings → Linked Devices", "Link a Device"], 1):
        st.markdown("%d. %s" % (i, step))
    st.caption("To disconnect: WhatsApp → Linked Devices → Log out.")
    st.stop()

# --- 4) If NOT connected: GET /admin/wa/qr on load (no caching) ---
# On first load when not connected: fetch QR once. If qr exists, render; else "Waiting for QR..."
if not st.session_state.wa_qr_string and not st.session_state.wa_polling:
    qr_data, _ = get_wa_qr(force_refresh=True)
    if isinstance(qr_data, dict) and qr_data.get("qr"):
        st.session_state.wa_qr_string = qr_data.get("qr")
        st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
        st.rerun()


def _fetch_qr() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """GET /wa/qr. Returns (qr_string, status, error). No caching."""
    qr_data, qr_err = get_wa_qr(force_refresh=True)
    if qr_err:
        return None, None, qr_err
    if not isinstance(qr_data, dict):
        return None, "not_ready", None
    s = qr_data.get("status", "not_ready")
    qr = qr_data.get("qr")
    if s == "connected":
        return None, "connected", None
    if s == "qr_ready" and qr:
        return qr, "qr_ready", None
    return None, "not_ready", None

# Connect / Reconnect buttons
if st.button("Connect WhatsApp", key="wa_connect"):
    clear_wa_cache()
    st.session_state.wa_connect_clicked = True
    st.session_state.wa_qr_string = None
    st.session_state.wa_polling = True
    st.session_state.wa_poll_started_at = time.time()
    st.session_state.wa_poll_count = 0
    _, err = post_wa_reconnect()
    if err:
        st.session_state.wa_refresh_msg = "⚠️ " + (err[:120] if err else "Request failed")
    else:
        st.session_state.wa_refresh_msg = None
    st.rerun()

if st.button("Reconnect", key="wa_reconnect"):
    clear_wa_cache()
    st.session_state.wa_connect_clicked = True
    st.session_state.wa_qr_string = None
    st.session_state.wa_polling = True
    st.session_state.wa_poll_started_at = time.time()
    st.session_state.wa_poll_count = 0
    _, err = post_wa_reconnect()
    if err:
        st.session_state.wa_refresh_msg = "⚠️ " + (err[:120] if err else "Request failed")
    else:
        st.session_state.wa_refresh_msg = None
    st.rerun()

# Polling: ONLY when NOT connected
if st.session_state.wa_polling and st.session_state.wa_poll_count < len(POLL_INTERVALS):
    elapsed = time.time() - st.session_state.wa_poll_started_at
    if elapsed < POLL_MAX_WAIT:
        idx = min(st.session_state.wa_poll_count, len(POLL_INTERVALS) - 1)
        interval = POLL_INTERVALS[idx]
        st.caption("⏳ Polling for QR… (%ds / %ds)" % (int(elapsed), POLL_MAX_WAIT))
        qr, qr_status, poll_err = _fetch_qr()
        if poll_err:
            st.session_state.wa_polling = False
            st.session_state.wa_refresh_msg = "⚠️ " + (poll_err[:120] if poll_err else "Request failed")
        elif qr_status == "connected":
            st.session_state.wa_polling = False
            st.session_state.wa_qr_string = None
            st.session_state.wa_refresh_msg = None
            st.rerun()  # Will show connected on next run
        elif qr_status == "qr_ready" and qr:
            st.session_state.wa_qr_string = qr
            st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
            st.session_state.wa_polling = False
            st.session_state.wa_refresh_msg = None
        else:
            st.session_state.wa_refresh_msg = "Waiting for QR…"
            st.session_state.wa_poll_count += 1
            time.sleep(min(interval, POLL_MAX_WAIT - elapsed))
        st.rerun()
    else:
        st.session_state.wa_polling = False
        st.session_state.wa_refresh_msg = "No QR after 2 minutes. Click **Reconnect**."

# Manual Refresh QR
if st.button("🔄 Refresh QR", key="manual_refresh"):
    clear_wa_cache()
    qr_data, qr_err = get_wa_qr(force_refresh=True)
    if qr_err:
        st.session_state.wa_refresh_msg = "⚠️ " + (qr_err[:120] if qr_err else "Request failed")
    elif isinstance(qr_data, dict) and qr_data.get("qr"):
        st.session_state.wa_qr_string = qr_data.get("qr")
        st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
        st.session_state.wa_refresh_msg = None
    else:
        st.session_state.wa_refresh_msg = "Waiting for QR… Click **Connect WhatsApp** first."
    st.rerun()

if st.session_state.wa_refresh_msg:
    st.warning(st.session_state.wa_refresh_msg)
    st.session_state.wa_refresh_msg = None

st.divider()
st.subheader("How to connect")
for i, step in enumerate(["Open WhatsApp on your phone", "Settings → Linked Devices", "Link a Device", "Scan the QR code below"], 1):
    st.markdown("%d. %s" % (i, step))

# --- Display QR: ONLY when NOT connected ---
qr_string = st.session_state.wa_qr_string
if qr_string:
    try:
        import qrcode
        img = qrcode.make(qr_string)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        st.image(buf, caption="Scan with WhatsApp", use_container_width=False)
        st.caption("Last refresh: %s" % st.session_state.wa_last_refresh)
    except Exception:
        st.caption("QR could not be rendered.")
elif st.session_state.wa_polling:
    st.info("Waiting for QR…")
elif st.session_state.wa_connect_clicked:
    st.info("Waiting for QR… Click **Refresh QR** or wait for auto-poll.")
else:
    st.info("👆 **Click Connect WhatsApp** to start.")

if last_reason:
    st.caption("Last disconnect: %s" % last_reason)
if server_time:
    st.caption("Server time: %s" % server_time)

with st.expander("FAQ"):
    st.markdown("**Why?** Links your WhatsApp so the bot can send/receive messages.")
    st.markdown("**Disconnect?** WhatsApp → Linked Devices → Log out.")

with st.expander("🔍 Debug"):
    st.code("Connect clicked: %s\nPolling: %s" % (st.session_state.wa_connect_clicked, st.session_state.wa_polling))
    if status_err:
        st.caption("Status error: %s" % (status_err[:100] if status_err else "—"))
    if status_data and isinstance(status_data, dict):
        safe = {k: v for k, v in status_data.items() if k not in ("token", "session", "auth", "key", "secret")}
        st.json(safe)
