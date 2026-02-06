"""Tests for per-user WhatsApp endpoints: isolation (user A cannot access user B's QR/status), rate limits."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_user_a():
    u = MagicMock()
    u.id = 1
    u.email = "a@test.com"
    return u


@pytest.fixture
def mock_user_b():
    u = MagicMock()
    u.id = 2
    u.email = "b@test.com"
    return u


@pytest.fixture
def mock_db_session():
    return MagicMock()


def test_whatsapp_qr_isolation_user_a_gets_own_qr(mock_user_a, mock_db_session):
    """User A gets QR for user_id=1 only; bot is called with user_id=1."""
    import asyncio
    from apps.api.routes.whatsapp_user import whatsapp_qr

    with patch("apps.api.routes.whatsapp_user.check_wa_qr", return_value=True), \
         patch("apps.api.routes.whatsapp_user._bot_get", new_callable=AsyncMock) as m_bot:
        m_bot.return_value = ({"qr": "data-for-user-1", "status": "qr_ready"}, None)

        async def run():
            return await whatsapp_qr(user=mock_user_a, session=mock_db_session)

        result = asyncio.run(run())

        assert result["qr"] == "data-for-user-1"
        m_bot.assert_called_once()
        # _bot_get(path, params) -> params is 2nd positional
        params = m_bot.call_args[0][1] if len(m_bot.call_args[0]) > 1 else (m_bot.call_args[1] or {}).get("params")
        assert params and params.get("user_id") == 1


def test_whatsapp_qr_isolation_user_b_gets_own_qr_not_a(mock_user_b, mock_db_session):
    """User B gets QR for user_id=2; bot is called with user_id=2, not 1."""
    import asyncio
    from apps.api.routes.whatsapp_user import whatsapp_qr

    with patch("apps.api.routes.whatsapp_user.check_wa_qr", return_value=True), \
         patch("apps.api.routes.whatsapp_user._bot_get", new_callable=AsyncMock) as m_bot:
        m_bot.return_value = ({"qr": "data-for-user-2", "status": "qr_ready"}, None)

        async def run():
            return await whatsapp_qr(user=mock_user_b, session=mock_db_session)

        result = asyncio.run(run())

        assert result["qr"] == "data-for-user-2"
        m_bot.assert_called_once()
        params = m_bot.call_args[0][1] if len(m_bot.call_args[0]) > 1 else (m_bot.call_args[1] or {}).get("params")
        assert params and params.get("user_id") == 2


def test_whatsapp_status_isolation_bot_called_with_user_id(mock_user_a, mock_user_b, mock_db_session):
    """Status endpoint is called with current user's id; user B cannot receive user A's status."""
    import asyncio
    from apps.api.routes.whatsapp_user import whatsapp_status

    with patch("apps.api.routes.whatsapp_user._bot_get", new_callable=AsyncMock) as m_bot:
        m_bot.return_value = ({"connected": True, "status": "connected", "phone": "123"}, None)

        async def run(user):
            return await whatsapp_status(user=user, session=mock_db_session)

        r_a = asyncio.run(run(mock_user_a))
        assert r_a.get("connected") is True
        params = m_bot.call_args[0][1] if len(m_bot.call_args[0]) > 1 else (m_bot.call_args[1] or {}).get("params")
        assert params and params.get("user_id") == 1

        m_bot.return_value = ({"connected": False, "status": "disconnected"}, None)
        asyncio.run(run(mock_user_b))
        params = m_bot.call_args[0][1] if len(m_bot.call_args[0]) > 1 else (m_bot.call_args[1] or {}).get("params")
        assert params and params.get("user_id") == 2


def test_whatsapp_qr_expired_returns_null():
    """When qr_expires_at is in the past, backend returns qr: null."""
    from apps.api.routes.whatsapp_user import _qr_expired
    import time

    assert _qr_expired({}, 60) is True
    assert _qr_expired({"qr": "x"}, 60) is False
    assert _qr_expired({"qr": "x", "qr_expires_at": time.time() - 10}, 60) is True
    assert _qr_expired({"qr": "x", "qr_expires_at": time.time() + 60}, 60) is False


def test_whatsapp_rate_limit_connect_rejects_over_limit():
    """check_wa_connect returns False when over 5/hour (in-memory)."""
    from apps.api import wa_rate_limit

    with patch.object(wa_rate_limit, "_get_redis", return_value=None):
        wa_rate_limit._MEMORY.clear()
        user_id = 99
        for _ in range(5):
            assert wa_rate_limit.check_wa_connect(user_id, limit=5, window_seconds=3600) is True
        assert wa_rate_limit.check_wa_connect(user_id, limit=5, window_seconds=3600) is False


def test_whatsapp_rate_limit_qr_rejects_over_limit():
    """check_wa_qr returns False when over 30/min (in-memory)."""
    from apps.api import wa_rate_limit

    with patch.object(wa_rate_limit, "_get_redis", return_value=None):
        wa_rate_limit._MEMORY.clear()
        user_id = 88
        for _ in range(30):
            assert wa_rate_limit.check_wa_qr(user_id, limit=30, window_seconds=60) is True
        assert wa_rate_limit.check_wa_qr(user_id, limit=30, window_seconds=60) is False
