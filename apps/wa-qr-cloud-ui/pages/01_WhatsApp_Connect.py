"""
WhatsApp Connect — Connect/Reconnect to generate QR. Robust polling with caching.

Why caching & polling:
- API calls are cached (status 8s, QR 12s) to reduce request volume and avoid rate limiting.
- After Connect/Reconnect, we poll the QR endpoint with progressive backoff (2,3,5,8,13,15s)
  up to 90s max, with at most 12 poll ticks per run — no aggressive auto-refresh loops.
- Manual "Refresh QR" clears cache and fetches once. "Pause auto refresh" stops polling.
"""
import io
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

from src.api import get_wa_qr, get_wa_status, post_wa_reconnect
from src.ui import inject_app_css, render_sidebar
from src.config import get_config

# --- Cached API wrappers (reduce request volume, avoid rate limiting) ---
@st.cache_data(ttl=8)
def _cached_status():
    return get_wa_status()

@st.cache_data(ttl=12)
def _cached_qr():
    return get_wa_qr()

# Progressive poll intervals (seconds), capped at 15. Max 12 polls ≈ 90s total.
POLL_INTERVALS = [2, 3, 5, 8, 13, 15, 15, 15, 15, 15, 15, 15]
POLL_MAX_WAIT = 90
POLL_MAX_TICKS = 12

st.set_page_config(page_title="GNI — WhatsApp Connect", layout="centered", initial_sidebar_state="expanded")
base = (st.session_state.get("api_base_url") or "").strip().rstrip("/")
if not base and get_config().get("GNI_API_BASE_URL"):
    st.session_state["api_base_url"] = get_config().get("GNI_API_BASE_URL", "").strip().rstrip("/")
    base = st.session_state["api_base_url"]
if not base:
    st.warning("Backend URL not set. Go to Home to set it.")
    st.switch_page("app.py")
inject_app_css()
render_sidebar("client", "whatsapp", api_base_url=base, user_email="")

# --- Session state ---
for key, default in [
    ("wa_qr_string", None),
    ("wa_last_refresh", "Never"),
    ("wa_polling", False),
    ("wa_poll_started_at", 0.0),
    ("wa_poll_count", 0),
    ("wa_paused", False),
    ("wa_refresh_msg", None),
    ("wa_connect_clicked", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# --- Status (cached) ---
status_data, status_err = _cached_status()
connected = False
status_label = "Disconnected"
last_reason = None
if status_err and not status_data:
    status_label = "Error" if status_err else "Disconnected"
elif isinstance(status_data, dict):
    connected = status_data.get("connected") or status_data.get("status") == "open"
    last_reason = status_data.get("lastDisconnectReason")
    status_label = "Connected" if connected else "Disconnected"

# --- Header ---
_logo = Path(__file__).parent.parent / "assets" / "whatsapp-logo.webp"
_col1, _col2, _col3 = st.columns([1, 2, 1])
with _col2:
    if _logo.exists():
        st.image(str(_logo), width=100)
    st.title("WhatsApp Connect")
    st.markdown('<p class="subtitle-muted">Link your WhatsApp account to send and receive messages.</p>', unsafe_allow_html=True)

st.subheader("Status: %s" % status_label)
if connected:
    st.success("Connected ✅")
elif status_err:
    if status_err and "rate limit" in status_err.lower():
        st.error("Rate limited. Wait 30 seconds, then click Refresh.")
    else:
        st.error(status_err)
else:
    st.info("Disconnected — click Connect WhatsApp to show QR code")
if last_reason:
    st.caption("Last disconnect: %s" % last_reason)

st.divider()
st.subheader("How to connect")
for i, step in enumerate(["Open WhatsApp on your phone", "Settings → Linked Devices", "Link a Device", "Scan the QR code below"], 1):
    st.markdown("%d. %s" % (i, step))

if not connected and not st.session_state.wa_qr_string and not st.session_state.wa_connect_clicked:
    st.info("👆 **Click Connect WhatsApp below** to start. QR appears within ~90 seconds.")


def _poll_one_tick() -> Optional[str]:
    """Fetch QR once (bypass throttle for fresh result). Return qr string or None."""
    qr_data, qr_err = get_wa_qr(force_refresh=True)
    if qr_err:
        return None
    if isinstance(qr_data, dict) and qr_data.get("qr"):
        return qr_data.get("qr")
    if isinstance(qr_data, dict) and qr_data.get("status") == "qr_ready" and qr_data.get("qr"):
        return qr_data.get("qr")
    return None


# --- Connect: trigger reconnect once, start polling ---
if st.button("Connect WhatsApp", key="wa_connect"):
    _cached_qr.clear()
    _cached_status.clear()
    st.session_state.wa_connect_clicked = True
    st.session_state.wa_qr_string = None
    st.session_state.wa_polling = True
    st.session_state.wa_poll_started_at = time.time()
    st.session_state.wa_poll_count = 0
    st.session_state.wa_paused = False
    _, err = post_wa_reconnect()
    if err:
        st.session_state.wa_polling = False
        st.session_state.wa_refresh_msg = err
    st.rerun()

# --- Reconnect: same as Connect ---
if st.button("Reconnect", key="wa_reconnect"):
    _cached_qr.clear()
    _cached_status.clear()
    st.session_state.wa_connect_clicked = True
    st.session_state.wa_qr_string = None
    st.session_state.wa_polling = True
    st.session_state.wa_poll_started_at = time.time()
    st.session_state.wa_poll_count = 0
    st.session_state.wa_paused = False
    _, err = post_wa_reconnect()
    if err:
        st.session_state.wa_polling = False
        st.session_state.wa_refresh_msg = err
    st.rerun()

# --- Polling: one tick per rerun, capped ---
if (
    not connected
    and st.session_state.wa_polling
    and not st.session_state.wa_paused
    and st.session_state.wa_poll_count < POLL_MAX_TICKS
):
    elapsed = time.time() - st.session_state.wa_poll_started_at
    if elapsed < POLL_MAX_WAIT:
        idx = min(st.session_state.wa_poll_count, len(POLL_INTERVALS) - 1)
        interval = POLL_INTERVALS[idx]
        st.caption("⏳ Polling for QR… (%ds / %ds)" % (int(elapsed), POLL_MAX_WAIT))
        qr = _poll_one_tick()
        if qr:
            st.session_state.wa_qr_string = qr
            st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
            st.session_state.wa_polling = False
            st.session_state.wa_refresh_msg = None
        else:
            st.session_state.wa_poll_count += 1
            time.sleep(min(interval, POLL_MAX_WAIT - elapsed))
        st.rerun()
    else:
        st.session_state.wa_polling = False
        st.session_state.wa_refresh_msg = "Timeout. Click **Refresh QR** or **Reconnect** to try again."

# --- Manual controls ---
if not connected:
    st.caption("Last refresh: %s" % st.session_state.wa_last_refresh)
    if st.session_state.wa_refresh_msg:
        st.warning(st.session_state.wa_refresh_msg)
        st.session_state.wa_refresh_msg = None

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔄 Refresh QR", key="manual_refresh"):
            _cached_qr.clear()
            qr_data, qr_err = get_wa_qr(force_refresh=True)
            if qr_err:
                st.session_state.wa_refresh_msg = "⚠️ " + (
                    qr_err if "rate limit" not in (qr_err or "").lower() else "Rate limited. Try again in 30 seconds."
                )
            elif isinstance(qr_data, dict) and qr_data.get("qr"):
                st.session_state.wa_qr_string = qr_data.get("qr")
                st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
                st.session_state.wa_refresh_msg = None
            else:
                st.session_state.wa_refresh_msg = "Waiting for QR. Click **Connect WhatsApp** first, then Refresh."
            st.rerun()

    with col2:
        if st.session_state.wa_paused:
            if st.button("▶ Resume polling", key="wa_resume"):
                st.session_state.wa_paused = False
                st.session_state.wa_polling = True
                st.session_state.wa_poll_count = 0
                st.session_state.wa_poll_started_at = time.time()
                st.rerun()
        else:
            if st.button("⏸ Pause auto refresh", key="wa_pause"):
                st.session_state.wa_paused = True
                st.session_state.wa_polling = False
                st.rerun()

# --- Initial fetch: if no QR, not polling, try once (cached) ---
if (
    not connected
    and not st.session_state.wa_qr_string
    and not st.session_state.wa_polling
    and not st.session_state.wa_connect_clicked
):
    qr_data, _ = _cached_qr()
    if isinstance(qr_data, dict) and qr_data.get("qr"):
        st.session_state.wa_qr_string = qr_data.get("qr")
        st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")

# --- Display QR ---
qr_string = st.session_state.wa_qr_string
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
    st.caption("QR persists until you click Reconnect for a new one.")
elif not connected and st.session_state.wa_polling:
    st.caption("Waiting for QR…")
elif connected:
    st.caption("Session active. QR hidden.")

with st.expander("FAQ"):
    st.markdown("**Why do I need this?**")
    st.caption("This links your WhatsApp account so the bot can send/receive messages.")
    st.markdown("**How to disconnect?**")
    st.caption("In WhatsApp: Settings → Linked Devices → select this device → Log out.")
