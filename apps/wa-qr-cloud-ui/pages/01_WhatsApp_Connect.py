"""
WhatsApp Connect — Connect/Reconnect to generate QR. Clean UX: status badges, token input for 401/403, QR card, auto-refresh.

- Token: from env (WA_QR_BRIDGE_TOKEN) or paste in UI (session_state only; never logged).
- 401/403: friendly panel explaining token required + password input.
- Caching & polling: status 8s, QR 12s; progressive poll after Connect.
"""
import io
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import streamlit as st

from src.api import clear_wa_cache, get_wa_netcheck, get_wa_qr, get_wa_status, post_wa_reconnect
from src.ui import inject_app_css, render_sidebar
from src.config import get_config

# --- Cached API wrappers (token is read inside api.py from session_state/config) ---
@st.cache_data(ttl=12)
def _cached_status():
    return get_wa_status()

@st.cache_data(ttl=15)
def _cached_qr():
    return get_wa_qr()

POLL_INTERVALS = [5, 8, 10, 12, 15, 15, 20, 20, 20, 20]
POLL_MAX_WAIT = 120
POLL_MAX_TICKS = len(POLL_INTERVALS)
NOT_READY_WARN_THRESHOLD_SEC = 90  # Show block warning after not_ready for this long
RATE_LIMIT_BACKOFF_SECONDS = 30

st.set_page_config(page_title="GNI — WhatsApp Connect", layout="centered", initial_sidebar_state="expanded")
inject_app_css()

base = (st.session_state.get("api_base_url") or "").strip().rstrip("/")
if not base and get_config().get("GNI_API_BASE_URL"):
    st.session_state["api_base_url"] = get_config().get("GNI_API_BASE_URL", "").strip().rstrip("/")
    base = st.session_state["api_base_url"]
if not base:
    st.warning("Backend URL not set. Go to Home to set it.")
    st.switch_page("app.py")

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
    ("wa_qr_bridge_token", ""),
    ("wa_auto_refresh", False),
    ("wa_auto_refresh_interval", 10),
    ("wa_not_ready_since", None),
    ("wa_rate_limit_until", 0.0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

token_from_env = (get_config().get("WA_QR_BRIDGE_TOKEN") or "").strip()
has_token = bool(token_from_env) or bool((st.session_state.get("wa_qr_bridge_token") or "").strip())

render_sidebar("client", "whatsapp", api_base_url=base, user_email=st.session_state.get("auth_email") or "")

# --- Auth panel: when no token, or when we get 401/403 ---
def _show_token_panel(reason: str = "required"):
    st.markdown(
        '<div class="status-card">'
        "<strong>WhatsApp bridge token (WA_QR_BRIDGE_TOKEN)</strong><br>"
        "<span class=\"muted\">This page needs the same token as on your VM (.env). "
        "Set it in Streamlit Cloud Secrets, or paste it below (stored in this session only, never logged).</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    with st.form("wa_token_form"):
        tok = st.text_input("Token", type="password", placeholder="Paste WA_QR_BRIDGE_TOKEN", key="wa_token_input")
        if st.form_submit_button("Save and continue"):
            v = (tok or "").strip()
            if v:
                st.session_state.wa_qr_bridge_token = v
                clear_wa_cache()
                _cached_status.clear()
                _cached_qr.clear()
                st.rerun()
            else:
                st.warning("Enter a token.")

if not has_token:
    st.title("WhatsApp Connect")
    st.caption("Link your WhatsApp account to send and receive messages.")
    _show_token_panel()
    st.stop()

# --- Fetch status (may return 401/403) ---
status_data, status_err = _cached_status()
is_auth_error = status_err and (
    "Unauthorized" in (status_err or "")
    or "403" in (status_err or "")
    or "401" in (status_err or "")
    or "Missing Authorization" in (status_err or "")
    or "WA_QR_BRIDGE_TOKEN" in (status_err or "")
)

if is_auth_error:
    st.title("WhatsApp Connect")
    st.caption("Link your WhatsApp account to send and receive messages.")
    st.error("Authentication failed: the backend requires a valid **WA_QR_BRIDGE_TOKEN**.")
    _show_token_panel("invalid")
    st.stop()

if status_err and ("429" in status_err or "Rate limit" in status_err):
    st.session_state.wa_rate_limit_until = time.time() + RATE_LIMIT_BACKOFF_SECONDS
    st.session_state.wa_auto_refresh_interval = max(int(st.session_state.wa_auto_refresh_interval or 10), 30)

# --- Normal page content ---
connected = False
status_detail = "disconnected"
last_reason = None
if isinstance(status_data, dict):
    connected = status_data.get("connected") or (status_data.get("status") or "").strip().lower() == "connected"
    status_detail = (status_data.get("status") or "disconnected").strip().lower()
    last_reason = status_data.get("lastDisconnectReason")
    if status_detail == "disconnected":
        st.session_state.wa_auto_refresh_interval = max(int(st.session_state.wa_auto_refresh_interval or 10), 15)

# Track not_ready duration for block warning
if status_detail in ("not_ready", "disconnected") and not connected:
    if st.session_state.wa_not_ready_since is None:
        st.session_state.wa_not_ready_since = time.time()
else:
    st.session_state.wa_not_ready_since = None

# Fetch netcheck (connectivity to WhatsApp from bot container)
netcheck_data, netcheck_err = get_wa_netcheck()
netcheck_ok = isinstance(netcheck_data, dict) and netcheck_data.get("ok") is True
show_block_warning = False
if netcheck_data and isinstance(netcheck_data, dict) and netcheck_data.get("ok") is False:
    show_block_warning = True
elif status_detail in ("not_ready", "disconnected") and st.session_state.wa_not_ready_since:
    elapsed = time.time() - st.session_state.wa_not_ready_since
    if elapsed >= NOT_READY_WARN_THRESHOLD_SEC:
        show_block_warning = True

# --- Header ---
_logo = Path(__file__).parent.parent / "assets" / "whatsapp-logo.webp"
_col1, _col2, _col3 = st.columns([1, 2, 1])
with _col2:
    if _logo.exists():
        st.image(str(_logo), width=100)
    st.title("WhatsApp Connect")
    st.markdown('<p class="subtitle-muted">Link your WhatsApp account to send and receive messages.</p>', unsafe_allow_html=True)

# --- Status badges (clean) ---
if connected:
    st.success("✅ **Connected** — Session active.")
elif status_detail == "qr_ready":
    st.info("🔲 **QR Ready** — Scan the code below with WhatsApp.")
elif status_detail == "not_ready":
    st.info("⏳ **Not Ready** — Click **Connect WhatsApp** to generate a QR code.")
elif status_err:
    st.error("🔴 **Error** — " + (status_err or "Request failed."))
else:
    st.info("⚪ **Disconnected** — Click **Connect WhatsApp** to show a QR code.")
if last_reason:
    st.caption("Last disconnect: " + str(last_reason))

if show_block_warning and not connected:
    st.warning(
        "**Your server IP/network appears blocked by WhatsApp.** "
        "Recommended: use **Telegram** or **Make webhook** for delivery."
    )

if token_from_env:
    st.caption("Using token from environment.")

st.divider()
st.subheader("How to connect")
for i, step in enumerate(["Open WhatsApp on your phone", "Settings → Linked Devices", "Link a Device", "Scan the QR code below"], 1):
    st.markdown("%d. %s" % (i, step))

if not connected and not st.session_state.wa_qr_string and not st.session_state.wa_connect_clicked:
    st.info("👆 Click **Connect WhatsApp** below. The QR can take up to ~2 minutes to appear.")

# --- Primary / Secondary buttons ---
btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])
with btn_col1:
    if st.button("Connect WhatsApp", type="primary", key="wa_connect"):
        clear_wa_cache()
        _cached_status.clear()
        _cached_qr.clear()
        st.session_state.wa_connect_clicked = True
        st.session_state.wa_qr_string = None
        st.session_state.wa_polling = True
        st.session_state.wa_poll_started_at = time.time()
        st.session_state.wa_poll_count = 0
        st.session_state.wa_paused = False
        st.session_state.wa_not_ready_since = None
        _, err = post_wa_reconnect()
        if err:
            st.session_state.wa_polling = False
            st.session_state.wa_refresh_msg = err
            if "429" in err or "Rate limit" in err:
                st.session_state.wa_rate_limit_until = time.time() + RATE_LIMIT_BACKOFF_SECONDS
                st.session_state.wa_auto_refresh_interval = max(int(st.session_state.wa_auto_refresh_interval or 10), 30)
        else:
            st.session_state.wa_refresh_msg = None
        st.rerun()
with btn_col2:
    if st.button("Refresh QR", key="wa_refresh_qr"):
        clear_wa_cache()
        qr_data, qr_err = get_wa_qr(force_refresh=True)
        if qr_err:
            st.session_state.wa_refresh_msg = qr_err
            if "429" in qr_err or "Rate limit" in qr_err:
                st.session_state.wa_rate_limit_until = time.time() + RATE_LIMIT_BACKOFF_SECONDS
                st.session_state.wa_auto_refresh_interval = max(int(st.session_state.wa_auto_refresh_interval or 10), 30)
        elif isinstance(qr_data, dict) and qr_data.get("qr"):
            st.session_state.wa_qr_string = qr_data.get("qr")
            st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
            st.session_state.wa_refresh_msg = None
        else:
            st.session_state.wa_refresh_msg = "No QR yet. Click **Connect WhatsApp** first."
        st.rerun()

# --- Auto-refresh toggle + interval ---
st.caption("")
ar_col1, ar_col2 = st.columns(2)
with ar_col1:
    auto_refresh = st.checkbox("Auto-refresh status", value=st.session_state.wa_auto_refresh, key="wa_auto_refresh_cb")
    st.session_state.wa_auto_refresh = auto_refresh
with ar_col2:
    opts = [10, 15, 30]
    cur = st.session_state.wa_auto_refresh_interval
    idx = opts.index(cur) if cur in opts else 1
    interval = st.selectbox("Interval", options=opts, format_func=lambda x: f"{x} s", index=idx, key="wa_interval")
    st.session_state.wa_auto_refresh_interval = interval

st.caption("**Last refresh:** " + str(st.session_state.wa_last_refresh))
if st.session_state.wa_refresh_msg:
    st.warning(st.session_state.wa_refresh_msg)
    st.session_state.wa_refresh_msg = None

rate_limit_wait = int(max(0, st.session_state.wa_rate_limit_until - time.time()))
if rate_limit_wait > 0:
    st.warning(f"Too many requests (429). Slowing refresh for {rate_limit_wait}s.")

def _poll_one_tick() -> tuple[Optional[str], Optional[str], Optional[str]]:
    qr_data, qr_err = get_wa_qr(force_refresh=True)
    if qr_err:
        return None, None, qr_err
    if not isinstance(qr_data, dict):
        return None, "not_ready", None
    status = qr_data.get("status", "not_ready")
    qr = qr_data.get("qr")
    if status == "connected":
        return None, "connected", None
    if status == "qr_ready" and qr:
        return qr, "qr_ready", None
    return None, "not_ready", None

# --- Connect button: start polling ---
if st.session_state.get("wa_connect_clicked") and st.session_state.wa_polling and not st.session_state.wa_paused and st.session_state.wa_poll_count < POLL_MAX_TICKS and not connected:
    elapsed = time.time() - st.session_state.wa_poll_started_at
    if elapsed < POLL_MAX_WAIT:
        idx = min(st.session_state.wa_poll_count, len(POLL_INTERVALS) - 1)
        interval_sec = POLL_INTERVALS[idx]
        st.caption("⏳ Polling for QR… (%ds / %ds)" % (int(elapsed), POLL_MAX_WAIT))
        qr, qr_status, poll_err = _poll_one_tick()
        if poll_err:
            st.session_state.wa_polling = False
            st.session_state.wa_refresh_msg = poll_err
            if "429" in poll_err or "Rate limit" in poll_err:
                st.session_state.wa_rate_limit_until = time.time() + RATE_LIMIT_BACKOFF_SECONDS
                st.session_state.wa_auto_refresh_interval = max(int(st.session_state.wa_auto_refresh_interval or 10), 30)
        elif qr_status == "connected":
            st.session_state.wa_polling = False
            st.session_state.wa_refresh_msg = "✅ Connected!"
        elif qr_status == "qr_ready" and qr:
            st.session_state.wa_qr_string = qr
            st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
            st.session_state.wa_polling = False
        else:
            st.session_state.wa_poll_count += 1
            time.sleep(min(interval_sec, POLL_MAX_WAIT - elapsed))
        st.rerun()
    else:
        st.session_state.wa_polling = False
        st.session_state.wa_refresh_msg = "No QR after 2 minutes. Try **Connect WhatsApp** again or check the VM (whatsapp-bot container)."

# --- Initial fetch: one cached QR if not connected ---
if not connected and not st.session_state.wa_qr_string and not st.session_state.wa_polling and not st.session_state.wa_connect_clicked:
    qr_data, _ = _cached_qr()
    if isinstance(qr_data, dict) and qr_data.get("qr"):
        st.session_state.wa_qr_string = qr_data.get("qr")
        st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")

# --- QR in centered card ---
qr_string = st.session_state.wa_qr_string
if not connected and qr_string:
    try:
        import base64
        import qrcode
        img = qrcode.make(qr_string)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        b64 = base64.b64encode(buf.getvalue()).decode()
        _c1, _c2, _c3 = st.columns([1, 2, 1])
        with _c2:
            st.markdown(
                '<div class="content-card" style="text-align:center;">'
                '<img src="data:image/png;base64,' + b64 + '" alt="QR" style="max-width:100%;"/>'
                '<p style="margin-top:0.5rem;color:rgba(49,51,63,0.6);font-size:0.85rem;">Scan with WhatsApp</p>'
                '</div>',
                unsafe_allow_html=True,
            )
        st.caption("QR stays until you click **Connect WhatsApp** again for a new one.")
    except Exception:
        st.caption("QR could not be rendered.")
elif not connected and st.session_state.wa_polling:
    st.caption("Waiting for QR…")
elif connected:
    st.caption("Session active. QR hidden.")

# --- Auto-refresh: rerun page on interval when enabled (Streamlit 1.33+ run_every) ---
if st.session_state.wa_auto_refresh and st.session_state.wa_auto_refresh_interval:
    sec = int(st.session_state.wa_auto_refresh_interval)
    if rate_limit_wait > 0:
        sec = max(sec, rate_limit_wait)
    try:
        @st.fragment(run_every=timedelta(seconds=sec))
        def _auto_refresh_tick():
            clear_wa_cache()
            _cached_status.clear()
            get_wa_status()
            st.session_state.wa_last_refresh = datetime.now().strftime("%H:%M:%S")
            st.rerun()
    except Exception:
        pass  # run_every not available in older Streamlit

with st.expander("FAQ"):
    st.markdown("**Why do I need this?**")
    st.caption("This links your WhatsApp account so the bot can send/receive messages.")
    st.markdown("**How to disconnect?**")
    st.caption("In WhatsApp: Settings → Linked Devices → select this device → Log out.")

with st.expander("📡 Connectivity (netcheck + bot status)"):
    nc = netcheck_data if isinstance(netcheck_data, dict) else {}
    nc_ok = nc.get("ok")
    nc_sc = nc.get("status_code")
    nc_err = nc.get("error")
    st.caption("**Netcheck:** ok=%s | status_code=%s | error=%s" % (
        nc_ok if nc_ok is not None else "N/A",
        nc_sc if nc_sc is not None else "N/A",
        repr(nc_err)[:80] if nc_err else "—",
    ))
    st.caption("**Bot status:**")
    if status_data and isinstance(status_data, dict):
        safe = {k: v for k, v in status_data.items() if "token" not in (str(k)).lower() and "secret" not in (str(k)).lower()}
        st.json(safe)
    elif status_err:
        st.caption("Error: " + str(status_err))
    if netcheck_err:
        st.caption("Netcheck request: " + str(netcheck_err))

with st.expander("🔍 Debug (no secrets)"):
    st.caption("Status and polling state (token never shown):")
    st.code("Connect clicked: %s\nPolling: %s\nPoll count: %s\nLast refresh: %s" % (
        st.session_state.wa_connect_clicked,
        st.session_state.wa_polling,
        st.session_state.wa_poll_count,
        st.session_state.wa_last_refresh,
    ))
    if status_err:
        st.error("Status error: " + str(status_err))
    if status_data and isinstance(status_data, dict):
        # Safe display: no token fields
        safe = {k: v for k, v in status_data.items() if "token" not in k.lower() and "secret" not in k.lower()}
        st.json(safe)
