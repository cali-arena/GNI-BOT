"""
API wrapper: api_get / api_post with base URL and auth. Friendly errors; never log secrets.
"""
from typing import Any, Optional

# Timeouts for api_get / api_post helpers: (connect, read) in seconds
_API_CONNECT_TIMEOUT = 5
_API_READ_TIMEOUT = 15


def _get_config():
    from src.config import get_config
    return get_config()


def _headers(use_bearer: bool = True) -> dict:
    cfg = _get_config()
    h = {"Content-Type": "application/json"}
    if use_bearer:
        token = (cfg.get("WA_QR_BRIDGE_TOKEN") or "").strip()
        if token:
            h["Authorization"] = f"Bearer {token}"
    else:
        api_key = (cfg.get("API_KEY") or "").strip()
        if api_key:
            h["X-API-Key"] = api_key
    return h


def _base_url() -> str:
    return (_get_config().get("GNI_API_BASE_URL") or "").strip().rstrip("/")


def api_get(path: str, jwt: Optional[str] = None) -> tuple[Optional[Any], Optional[str], Optional[int]]:
    """
    GET {base}{path}. Optional Authorization: Bearer <jwt>. Timeouts: connect=5s, read=15s.
    Returns (data, error_msg, status_code). status_code is set on HTTP error (e.g. 401, 429); None otherwise.
    On exception: shows st.warning. Never logs secrets.
    """
    import requests
    import streamlit as st
    base = _base_url()
    if not base:
        msg = "API base URL not set"
        try:
            st.warning(msg)
        except Exception:
            pass
        return None, msg, None
    url = f"{base}{path}"
    headers = {"Content-Type": "application/json"}
    if jwt and str(jwt).strip():
        headers["Authorization"] = f"Bearer {jwt.strip()}"
    try:
        r = requests.get(url, headers=headers, timeout=(_API_CONNECT_TIMEOUT, _API_READ_TIMEOUT))
        r.raise_for_status()
        return (r.json() if r.content else None), None, None
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else None
        try:
            detail = e.response.json().get("detail", "Request failed")
        except Exception:
            detail = "Request failed"
        msg = str(detail)[:200] if detail else "Request failed"
        if code == 401:
            msg = "Invalid or expired token. Please log in again."
        elif code == 429:
            msg = "Too many attempts, wait a bit."
        try:
            st.warning(msg)
        except Exception:
            pass
        return None, msg, code
    except requests.exceptions.Timeout:
        msg = "Request timed out."
        try:
            st.warning(msg)
        except Exception:
            pass
        return None, msg, None
    except Exception:
        msg = "Connection error."
        try:
            st.warning(msg)
        except Exception:
            pass
        return None, msg, None


def api_post(path: str, json: Optional[dict] = None, jwt: Optional[str] = None) -> tuple[Optional[Any], Optional[str], Optional[int]]:
    """
    POST {base}{path} with optional json body. Optional Authorization: Bearer <jwt>.
    Returns (data, error_msg, status_code). status_code set on HTTP error; None otherwise.
    Timeouts: connect=5s, read=15s. Never logs secrets.
    """
    import requests
    import streamlit as st
    base = _base_url()
    if not base:
        msg = "API base URL not set"
        try:
            st.warning(msg)
        except Exception:
            pass
        return None, msg, None
    url = f"{base}{path}"
    headers = {"Content-Type": "application/json"}
    if jwt and str(jwt).strip():
        headers["Authorization"] = f"Bearer {jwt.strip()}"
    try:
        r = requests.post(url, headers=headers, json=json or {}, timeout=(_API_CONNECT_TIMEOUT, _API_READ_TIMEOUT))
        r.raise_for_status()
        return (r.json() if r.content else {}), None, None
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else None
        try:
            detail = e.response.json().get("detail", "Request failed")
        except Exception:
            detail = "Request failed"
        msg = str(detail)[:200] if detail else "Request failed"
        if code == 401:
            msg = "Invalid or expired token. Please log in again."
        elif code == 429:
            msg = "Too many attempts, wait a bit."
        try:
            st.warning(msg)
        except Exception:
            pass
        return None, msg, code
    except requests.exceptions.Timeout:
        msg = "Request timed out."
        try:
            st.warning(msg)
        except Exception:
            pass
        return None, msg, None
    except Exception:
        msg = "Connection error."
        try:
            st.warning(msg)
        except Exception:
            pass
        return None, msg, None


def _headers_jwt(token: Optional[str] = None) -> dict:
    """Headers with JWT from session (for /auth/me, /whatsapp/*). Uses session_state jwt or auth_token."""
    h = {"Content-Type": "application/json"}
    t = (token or "").strip()
    if not t:
        try:
            import streamlit as st
            t = (st.session_state.get("jwt") or st.session_state.get("auth_token") or "").strip()
        except Exception:
            pass
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h


def api_get_jwt(path: str, *, timeout: int = 10, token: Optional[str] = None) -> tuple[Optional[Any], Optional[str]]:
    """GET with JWT from session (or passed token). For /auth/me, /whatsapp/*."""
    import requests
    base = _base_url()
    if not base:
        return None, "API base URL not set"
    url = f"{base}{path}"
    try:
        r = requests.get(url, headers=_headers_jwt(token=token), timeout=timeout)
        r.raise_for_status()
        return r.json() if r.content else None, None
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", "Request failed")
        except Exception:
            detail = "Request failed"
        if e.response.status_code == 401:
            return None, "Invalid or expired token. Please log in again."
        if e.response.status_code == 404:
            return None, "Endpoint not found."
        return None, str(detail)[:200]
    except requests.exceptions.Timeout:
        return None, "Request timed out."
    except Exception:
        return None, "Connection error."


def api_post_jwt(path: str, json_body: Optional[dict] = None, *, timeout: int = 10, token: Optional[str] = None) -> tuple[Optional[Any], Optional[str]]:
    """POST with JWT from session. For /auth/login, /whatsapp/connect."""
    import requests
    base = _base_url()
    if not base:
        return None, "API base URL not set"
    url = f"{base}{path}"
    try:
        r = requests.post(url, headers=_headers_jwt(token=token), json=json_body or {}, timeout=timeout)
        r.raise_for_status()
        return r.json() if r.content else {}, None
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", "Request failed")
        except Exception:
            detail = "Request failed"
        if e.response.status_code == 401:
            return None, "Invalid or expired token. Please log in again."
        if e.response.status_code == 429:
            return None, "Rate limit exceeded. Try again later."
        return None, str(detail)[:200]
    except requests.exceptions.Timeout:
        return None, "Request timed out."
    except Exception:
        return None, "Connection error."


def _api_get_legacy(path: str, *, timeout: int = 10, use_bearer: bool = True) -> tuple[Optional[Any], Optional[str]]:
    """GET with config-based bearer or API key. Used by get_wa_status, get_wa_qr, monitoring, posts."""
    import requests
    base = _base_url()
    if not base:
        return None, "API base URL not set"
    url = f"{base}{path}"
    try:
        r = requests.get(url, headers=_headers(use_bearer=use_bearer), timeout=timeout)
        r.raise_for_status()
        return r.json() if r.content else None, None
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", "Request failed")
        except Exception:
            detail = "Request failed"
        if e.response.status_code == 401:
            return None, "Authentication failed. Check your secrets."
        if e.response.status_code == 404:
            return None, "Endpoint not found."
        return None, str(detail)[:200]
    except requests.exceptions.Timeout:
        return None, "Request timed out."
    except Exception as e:
        return None, "Connection error."


def _api_post_legacy(path: str, json_body: Optional[dict] = None, *, timeout: int = 10, use_bearer: bool = False) -> tuple[Optional[Any], Optional[str]]:
    """POST with config-based auth. Used by monitoring run, approve, reject."""
    import requests
    base = _base_url()
    if not base:
        return None, "API base URL not set"
    url = f"{base}{path}"
    try:
        r = requests.post(url, headers=_headers(use_bearer=use_bearer), json=json_body or {}, timeout=timeout)
        r.raise_for_status()
        return r.json() if r.content else {}, None
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", "Request failed")
        except Exception:
            detail = "Request failed"
        if e.response.status_code == 401:
            return None, "Authentication failed. Check your secrets."
        if e.response.status_code == 404:
            return None, "Endpoint not found."
        return None, str(detail)[:200]
    except requests.exceptions.Timeout:
        return None, "Request timed out."
    except Exception as e:
        return None, "Connection error."


# --- Convenience (used by pages) ---
def get_health() -> tuple[Optional[dict], Optional[str]]:
    data, err, _ = api_get("/health")
    return data, err


def get_wa_status() -> tuple[Optional[dict], Optional[str]]:
    return _api_get_legacy("/admin/wa/status", use_bearer=True)


def get_wa_qr() -> tuple[Optional[dict], Optional[str]]:
    return _api_get_legacy("/admin/wa/qr", use_bearer=True)


# --- JWT / per-user WhatsApp (use these when auth_token is in session) ---
def post_auth_login(email: str, password: str) -> tuple[Optional[dict], Optional[str]]:
    """POST /auth/login. Returns (body with access_token, error). No auth header."""
    import requests
    base = _base_url()
    if not base:
        return None, "API base URL not set"
    url = f"{base}/auth/login"
    try:
        r = requests.post(url, headers={"Content-Type": "application/json"}, json={"email": email, "password": password}, timeout=10)
        r.raise_for_status()
        return r.json() if r.content else None, None
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", "Request failed")
        except Exception:
            detail = "Request failed"
        return None, str(detail)[:200]
    except Exception:
        return None, "Connection error."


def get_auth_me() -> tuple[Optional[dict], Optional[str]]:
    """GET /auth/me. Requires auth_token in session."""
    return api_get_jwt("/auth/me")


def post_wa_connect() -> tuple[Optional[dict], Optional[str]]:
    """POST /whatsapp/connect. Requires JWT."""
    return api_post_jwt("/whatsapp/connect", json_body={})


def get_wa_qr_user() -> tuple[Optional[dict], Optional[str]]:
    """GET /whatsapp/qr. Requires JWT. Never log qr content."""
    return api_get_jwt("/whatsapp/qr")


def get_wa_status_user() -> tuple[Optional[dict], Optional[str]]:
    """GET /whatsapp/status. Requires JWT."""
    return api_get_jwt("/whatsapp/status")


def get_monitoring_status(tenant: Optional[str] = None) -> tuple[Optional[dict], Optional[str]]:
    path = "/monitoring/status"
    if tenant:
        path += "?" + __import__("urllib.parse").urlencode({"tenant": tenant})
    return _api_get_legacy(path, use_bearer=False)


def get_monitoring_recent(limit: int = 20, tenant: Optional[str] = None) -> tuple[Optional[list], Optional[str]]:
    params = {"limit": limit}
    if tenant:
        params["tenant"] = tenant
    path = "/monitoring/recent?" + __import__("urllib.parse").urlencode(params)
    data, err = _api_get_legacy(path, use_bearer=False)
    if err:
        return None, err
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict) and "items" in data:
        return data["items"], None
    return data or [], None


def post_monitoring_run(tenant: Optional[str] = None) -> tuple[Optional[dict], Optional[str]]:
    return _api_post_legacy("/monitoring/run", json_body={"tenant": tenant} if tenant else None, use_bearer=False)


def get_posts(status: str = "pending", limit: int = 20, tenant: Optional[str] = None) -> tuple[Optional[list], Optional[str]]:
    if status == "pending":
        data, err = _api_get_legacy("/review/pending", use_bearer=False)
    else:
        params = {"status": status, "limit": limit}
        if tenant:
            params["tenant"] = tenant
        path = "/posts?" + __import__("urllib.parse").urlencode(params)
        data, err = _api_get_legacy(path, use_bearer=False)
    if err:
        return None, err
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict) and "items" in data:
        return data["items"], None
    return data or [], None


def post_approve(post_id: int) -> tuple[Optional[dict], Optional[str]]:
    return _api_post_legacy(f"/review/{post_id}/approve", use_bearer=False)


def post_reject(post_id: int) -> tuple[Optional[dict], Optional[str]]:
    return _api_post_legacy(f"/review/{post_id}/reject", use_bearer=False)
