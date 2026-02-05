"""Minimal tests for env parsing: empty -> default, invalid -> handled, valid -> parsed."""
import os

import pytest

from apps.shared.secrets import EnvSecretsProvider
from apps.shared.env_helpers import parse_int_default

try:
    from apps.api.core.settings import ApiSettings
    HAS_PYDANTIC_SETTINGS = True
except ImportError:
    HAS_PYDANTIC_SETTINGS = False


class TestEnvSecretsProvider:
    """get_secret / EnvSecretsProvider: empty string treated as missing -> default."""

    def test_missing_key_returns_default(self):
        provider = EnvSecretsProvider()
        assert provider.get("NONEXISTENT_KEY", "default") == "default"

    def test_empty_string_returns_default(self):
        provider = EnvSecretsProvider()
        os.environ["TEST_EMPTY_VAR"] = ""
        try:
            assert provider.get("TEST_EMPTY_VAR", "86400") == "86400"
        finally:
            os.environ.pop("TEST_EMPTY_VAR", None)

    def test_blank_string_returns_default(self):
        provider = EnvSecretsProvider()
        os.environ["TEST_BLANK_VAR"] = "   "
        try:
            assert provider.get("TEST_BLANK_VAR", "86400") == "86400"
        finally:
            os.environ.pop("TEST_BLANK_VAR", None)

    def test_valid_value_returned(self):
        provider = EnvSecretsProvider()
        os.environ["TEST_VALID_VAR"] = " 12345 "
        try:
            assert provider.get("TEST_VALID_VAR", "0") == "12345"
        finally:
            os.environ.pop("TEST_VALID_VAR", None)


class TestParseIntDefault:
    """parse_int_default: invalid -> default, valid -> parsed and clamped."""

    def test_empty_returns_default(self):
        assert parse_int_default("", 86400, 1, 604800) == 86400
        assert parse_int_default("  ", 86400, 1, 604800) == 86400

    def test_invalid_returns_default(self):
        assert parse_int_default("abc", 86400, 1, 604800) == 86400
        assert parse_int_default("12.3", 86400, 1, 604800) == 86400

    def test_valid_parsed(self):
        assert parse_int_default("3600", 86400, 1, 604800) == 3600
        assert parse_int_default("86400", 86400, 1, 604800) == 86400

    def test_clamped_to_range(self):
        assert parse_int_default("0", 86400, 1, 604800) == 86400  # 0 -> default
        assert parse_int_default("1", 86400, 1, 604800) == 1
        assert parse_int_default("999999", 86400, 1, 604800) == 604800


@pytest.mark.skipif(not HAS_PYDANTIC_SETTINGS, reason="pydantic-settings not installed")
class TestApiSettingsJwtExpiry:
    """ApiSettings.JWT_EXPIRY_SECONDS: empty -> 86400, invalid -> raise, valid -> int."""

    def test_empty_string_becomes_default(self):
        s = ApiSettings(
            DATABASE_URL="postgresql://u:p@h/d",
            REDIS_URL="redis://localhost/0",
            JWT_SECRET="",
            JWT_EXPIRY_SECONDS="",  # validator: empty -> 86400
            API_KEY="",
        )
        assert s.JWT_EXPIRY_SECONDS == 86400

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match="JWT_EXPIRY_SECONDS must be an integer"):
            ApiSettings(
                DATABASE_URL="postgresql://u:p@h/d",
                REDIS_URL="redis://localhost/0",
                JWT_SECRET="",
                JWT_EXPIRY_SECONDS="notanint",
                API_KEY="",
            )

    def test_valid_int_parsed(self):
        s = ApiSettings(
            DATABASE_URL="postgresql://u:p@h/d",
            REDIS_URL="redis://localhost/0",
            JWT_SECRET="",
            JWT_EXPIRY_SECONDS=3600,
            API_KEY="",
        )
        assert s.JWT_EXPIRY_SECONDS == 3600
