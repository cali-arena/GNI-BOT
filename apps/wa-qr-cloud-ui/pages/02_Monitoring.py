"""
Monitoring — scraping/jobs. Login required. Client = own data; admin = all.
"""
import streamlit as st
from src.auth import require_login
from src.config import validate_config
from src.api import get_health, get_monitoring_status, get_monitoring_recent, post_monitoring_run

validate_config()
require_login()
role = (st.session_state.get("auth_role") or "client").strip().lower()
tenant = None if role == "admin" else (st.session_state.get("auth_email") or "").strip() or None

st.title("Monitoring")
st.caption("Scraping and job status." + (" Showing all tenants." if role == "admin" else " Showing your data."))

health_data, health_err = get_health()
if health_err:
    st.warning("API health: " + health_err)
else:
    status = health_data.get("status", "ok") if isinstance(health_data, dict) else "ok"
    st.success("API health: " + str(status))

status_data, status_err = get_monitoring_status(tenant=tenant)
if status_err:
    st.warning("Status: " + status_err)
elif status_data and isinstance(status_data, dict):
    st.subheader("Status")
    for k, v in status_data.items():
        st.text("%s: %s" % (k, v))

st.subheader("Recent jobs")
recent, recent_err = get_monitoring_recent(limit=20, tenant=tenant)
if recent_err:
    st.error(recent_err)
elif recent and len(recent) > 0:
    def _emoji(s):
        s = (s or "").lower()
        if s in ("ok", "success", "completed", "done"):
            return "✅ " + str(s)
        if s in ("pending", "running", "in_progress"):
            return "🟡 " + str(s)
        return "🔴 " + str(s)
    rows = []
    for row in recent:
        if isinstance(row, dict):
            status = row.get("status") or row.get("state") or "—"
            ts = row.get("created_at") or row.get("updated_at") or row.get("timestamp") or "—"
            rows.append({"Status": _emoji(str(status)), "ID": row.get("id", "—"), "Created": ts})
        else:
            rows.append({"Status": "-", "ID": str(row), "Created": "-"})
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.info("No recent jobs.")

st.divider()
st.subheader("Run scraping now")
if "_confirm_run" not in st.session_state:
    st.session_state._confirm_run = False
if st.button("Run now", key="monitoring_run"):
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
