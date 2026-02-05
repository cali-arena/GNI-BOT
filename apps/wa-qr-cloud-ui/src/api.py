"""
API wrapper: api_get / api_post with base URL and auth. Friendly errors; never log secrets.
"""
from typing import Any, Optional


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


def _headers_jwt(token: Optional[str] = None) -> dict:
    """Headers with JWT from session (for /auth/me, /whatsapp/*)."""
    h = {"Content-Type": "application/json"}
    t = (token or "").strip()
    if not t:
        try:
            import streamlit as st
            t = (st.session_state.get("auth_token") or "").strip()
        except Exception:
            pass
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h


def _base_url() -> str:
    """Backend base URL: session_state api_base_url first, then config (secrets/env). Never log."""
    out = (_get_config().get("GNI_API_BASE_URL") or "").strip().rstrip("/")
    try:
        import streamlit as st
        session_url = (st.session_state.get("api_base_url") or "").strip().rstrip("/")
        if session_url:
            out = session_url
    except Exception:
        pass
    return out


def api_get(path: str, *, timeout: int = 10, use_bearer: bool = True) -> tuple[Optional[Any], Optional[str]]:
    """GET {base}{path}. Returns (data, error). On non-200 returns friendly error (no secrets)."""
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


def api_post(path: str, json_body: Optional[dict] = None, *, timeout: int = 10, use_bearer: bool = False) -> tuple[Optional[Any], Optional[str]]:
    """POST {base}{path}. Returns (data, error). use_bearer=True for WA bridge; False for API key (monitoring/posts)."""
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


# --- Convenience (used by pages) ---
def get_health() -> tuple[Optional[dict], Optional[str]]:
    return api_get("/health", use_bearer=False)


def get_wa_status() -> tuple[Optional[dict], Optional[str]]:
    return api_get("/admin/wa/status", use_bearer=True)


def get_wa_qr() -> tuple[Optional[dict], Optional[str]]:
    return api_get("/admin/wa/qr", use_bearer=True)


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
    """GET /whatsapp/qr. Requires JWT."""
    return api_get_jwt("/whatsapp/qr")


def get_wa_status_user() -> tuple[Optional[dict], Optional[str]]:
    """GET /whatsapp/status. Requires JWT."""
    return api_get_jwt("/whatsapp/status")


def get_wa_status() -> tuple[Optional[dict], Optional[str]]:
    """Legacy: GET /admin/wa/status with WA_QR_BRIDGE_TOKEN."""
    return api_get("/admin/wa/status", use_bearer=True)


def get_wa_qr() -> tuple[Optional[dict], Optional[str]]:
    """Legacy: GET /admin/wa/qr with WA_QR_BRIDGE_TOKEN."""
    return api_get("/admin/wa/qr", use_bearer=True)


def get_monitoring_status(tenant: Optional[str] = None) -> tuple[Optional[dict], Optional[str]]:
    path = "/monitoring/status"
    if tenant:
        path += "?" + __import__("urllib.parse").urlencode({"tenant": tenant})
    return api_get(path, use_bearer=False)


def get_monitoring_recent(limit: int = 20, tenant: Optional[str] = None) -> tuple[Optional[list], Optional[str]]:
    params = {"limit": limit}
    if tenant:
        params["tenant"] = tenant
    path = "/monitoring/recent?" + __import__("urllib.parse").urlencode(params)
    data, err = api_get(path, use_bearer=False)
    if err:
        return None, err
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict) and "items" in data:
        return data["items"], None
    return data or [], None


def post_monitoring_run(tenant: Optional[str] = None) -> tuple[Optional[dict], Optional[str]]:
    return api_post("/monitoring/run", json_body={"tenant": tenant} if tenant else None, use_bearer=False)


def get_posts(status: str = "pending", limit: int = 20, tenant: Optional[str] = None) -> tuple[Optional[list], Optional[str]]:
    if status == "pending":
        data, err = api_get("/review/pending", use_bearer=False)
    else:
        params = {"status": status, "limit": limit}
        if tenant:
            params["tenant"] = tenant
        path = "/posts?" + __import__("urllib.parse").urlencode(params)
        data, err = api_get(path, use_bearer=False)
    if err:
        return None, err
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict) and "items" in data:
        return data["items"], None
    return data or [], None


def post_approve(post_id: int) -> tuple[Optional[dict], Optional[str]]:
    return api_post(f"/review/{post_id}/approve", use_bearer=False)


def post_reject(post_id: int) -> tuple[Optional[dict], Optional[str]]:
    return api_post(f"/review/{post_id}/reject", use_bearer=False)
