"""
Monitoring — scraping/jobs. Login required. Client = own data; admin = all.
"""
import streamlit as st

from src.auth import require_login
from src.api import get_health, get_api_display_info, get_monitoring_status, get_monitoring_recent, post_monitoring_run
from src.ui import inject_app_css, render_sidebar, render_api_error_hint

try:
    from src.ui import render_api_error_hint
except ImportError:
    render_api_error_hint = lambda display_info=None: None

require_login()
inject_app_css()
role = (st.session_state.get("auth_role") or "client").strip().lower()
base = (st.session_state.get("api_base_url") or "").strip().rstrip("/")
render_sidebar(role, "monitoring", api_base_url=base, user_email=st.session_state.get("auth_email") or "")
# Tenant: admin = all (None); client = email or session fallback or "default"
tenant = None
if role != "admin":
    tenant = (st.session_state.get("auth_email") or "").strip() or st.session_state.get("monitoring_tenant") or "default"
# Ensure tenant is str or None for API (avoids AttributeError in urlencode)
if tenant is not None and not isinstance(tenant, str):
    tenant = str(tenant)

st.title("Monitoring")
st.caption("Scraping and job status." + (" Showing all tenants." if role == "admin" else " Showing your data."))

try:
    health_data, health_err = get_health()
    display_info = get_api_display_info()
    if health_err:
        st.warning(f"⚠️ API health: {health_err}")
        render_api_error_hint(display_info)
    else:
        status = health_data.get("status", "ok") if isinstance(health_data, dict) else "ok"
        st.success(f"✅ API health: **{status}**")
    if display_info.get("base_url"):
        st.caption(f"**API base URL:** `{display_info['base_url']}`")

    status_data, status_err = get_monitoring_status(tenant=tenant)
    if status_err:
        st.error(status_err)
        render_api_error_hint(get_api_display_info())
        st.stop()

    if status_data and isinstance(status_data, dict):
        st.subheader("Status")
        for k, v in status_data.items():
            st.text(f"{k}: {v}")

    st.subheader("Recent jobs")
    recent, recent_err = get_monitoring_recent(limit=20, tenant=tenant)
    if recent_err:
        st.error(recent_err)
        render_api_error_hint(get_api_display_info())
    elif recent and len(recent) > 0:
        def _emoji(s):
            s = (s or "").lower()
            if s in ("ok", "success", "completed", "done"):
                return "✅"
            if s in ("pending", "running", "in_progress"):
                return "🟡"
            return "🔴"
        rows = []
        for row in recent:
            if isinstance(row, dict):
                status = row.get("status") or row.get("state") or "—"
                ts = row.get("created_at") or row.get("updated_at") or row.get("timestamp") or "—"
                rows.append({"Status": _emoji(str(status)) + " " + str(status), "ID": row.get("id", "—"), "Created": ts})
            else:
                rows.append({"Status": "—", "ID": str(row), "Created": "—"})
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No recent jobs.")

    st.divider()
    st.subheader("Run scraping now")
    if "_confirm_run" not in st.session_state:
        st.session_state._confirm_run = False
    if st.button("Run now ▶️", key="monitoring_run"):
        st.session_state._confirm_run = True
    if st.session_state._confirm_run:
        st.caption("Confirm run? This triggers a scraping job.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, run", key="run_yes"):
                _, err = post_monitoring_run(tenant=tenant)
                st.session_state._confirm_run = False
                if err:
                    st.error(err)
                else:
                    st.success("Run triggered.")
                st.rerun()
        with c2:
            if st.button("Cancel", key="run_cancel"):
                st.session_state._confirm_run = False
                st.rerun()
except Exception as e:
    st.error(f"Monitoring error: {e}")
    render_api_error_hint(get_api_display_info())
