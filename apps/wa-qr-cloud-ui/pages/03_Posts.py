"""
Posts — generated posts queue. Login required. Client = own; admin = all. Approve / Reject.
"""
import streamlit as st

from src.auth import require_login
from src.config import validate_config
from src.api import get_posts, post_approve, post_reject

validate_config()
require_login()
role = (st.session_state.get("auth_role") or "client").strip().lower()
tenant = None if role == "admin" else (st.session_state.get("auth_email") or "").strip() or None

def _emoji(s):
    s = (s or "").lower()
    if s in ("published", "approved", "sent"):
        return "✅"
    if s in ("pending", "drafted", "draft"):
        return "🟡"
    return "🔴"

st.title("Posts")
st.caption("Generated posts queue." + (" All tenants." if role == "admin" else " Your data."))

tab_pending, tab_published = st.tabs(["Pending", "Published"])

with tab_pending:
    st.subheader("Pending")
    pending, err = get_posts(status="pending", limit=20, tenant=tenant)
    if err:
        st.error(err)
    elif pending and len(pending) > 0:
        for item in pending:
            id_ = item.get("id") if isinstance(item, dict) else None
            title = (item.get("title") or item.get("source_name") or f"#{id_}") if isinstance(item, dict) else str(item)
            status = item.get("status", "pending") if isinstance(item, dict) else "pending"
            created = (item.get("created_at") or "—") if isinstance(item, dict) else "—"
            with st.container():
                st.markdown(f"**{_emoji(str(status))} {title}**")
                st.caption(f"ID {id_} · {created}")
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    if st.button("Approve ✅", key=f"approve_{id_}"):
                        _, action_err = post_approve(id_)
                        if action_err:
                            st.error(action_err)
                        else:
                            st.success("Approved.")
                            st.rerun()
                with col2:
                    if st.button("Reject ❌", key=f"reject_{id_}"):
                        _, action_err = post_reject(id_)
                        if action_err:
                            st.error(action_err)
                        else:
                            st.success("Rejected.")
                            st.rerun()
                st.divider()
    else:
        st.info("No pending posts.")

with tab_published:
    st.subheader("Published")
    published, err2 = get_posts(status="published", limit=20, tenant=tenant)
    if err2:
        st.warning(err2)
    elif published and len(published) > 0:
        rows = []
        for item in published:
            if isinstance(item, dict):
                status = item.get("status", "—")
                rows.append({
                    "Status": _emoji(str(status)) + " " + str(status),
                    "ID": item.get("id", "—"),
                    "Title": (item.get("title") or item.get("source_name") or "—")[:50],
                    "Created": item.get("created_at") or "—",
                })
            else:
                rows.append({"Status": "—", "ID": str(item), "Title": "—", "Created": "—"})
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No published posts.")
