"""Tests for env parsing: env_int, env_float; missing/empty -> default, invalid -> ValueError."""
import os

import pytest

from apps.shared.env_helpers import env_float, env_int


class TestEnvInt:
    """env_int: missing/empty/whitespace -> default; invalid -> ValueError with variable name; min/max enforced."""

    def test_missing_uses_default(self):
        key = "TEST_ENV_INT_MISSING_XYZ"
        os.environ.pop(key, None)
        assert env_int(key, 86400) == 86400

    def test_empty_string_uses_default(self):
        key = "TEST_ENV_INT_EMPTY_XYZ"
        os.environ[key] = ""
        try:
            assert env_int(key, 86400) == 86400
        finally:
            os.environ.pop(key, None)

    def test_whitespace_uses_default(self):
        key = "TEST_ENV_INT_WHITESPACE_XYZ"
        os.environ[key] = "   "
        try:
            assert env_int(key, 86400) == 86400
        finally:
            os.environ.pop(key, None)

    def test_invalid_raises_value_error_mentioning_variable(self):
        key = "TEST_ENV_INT_INVALID_XYZ"
        os.environ[key] = "abc"
        try:
            with pytest.raises(ValueError) as exc_info:
                env_int(key, 86400)
            assert key in str(exc_info.value)
            assert "abc" in str(exc_info.value) or "Invalid integer" in str(exc_info.value)
        finally:
            os.environ.pop(key, None)

    def test_min_value_enforced_env_zero_raises(self):
        key = "TEST_ENV_INT_MIN_ZERO_XYZ"
        os.environ[key] = "0"
        try:
            with pytest.raises(ValueError) as exc_info:
                env_int(key, 86400, min_value=1)
            assert key in str(exc_info.value)
            assert "1" in str(exc_info.value) or ">=" in str(exc_info.value)
        finally:
            os.environ.pop(key, None)

    def test_valid_parsed(self):
        key = "TEST_ENV_INT_VALID_XYZ"
        os.environ[key] = "3600"
        try:
            assert env_int(key, 86400) == 3600
        finally:
            os.environ.pop(key, None)


class TestEnvFloat:
    """env_float: missing/empty/whitespace -> default; invalid -> ValueError with variable name."""

    def test_missing_uses_default(self):
        key = "TEST_ENV_FLOAT_MISSING_XYZ"
        os.environ.pop(key, None)
        assert env_float(key, 1.0) == 1.0

    def test_empty_string_uses_default(self):
        key = "TEST_ENV_FLOAT_EMPTY_XYZ"
        os.environ[key] = ""
        try:
            assert env_float(key, 60.0) == 60.0
        finally:
            os.environ.pop(key, None)

    def test_whitespace_uses_default(self):
        key = "TEST_ENV_FLOAT_WHITESPACE_XYZ"
        os.environ[key] = "   "
        try:
            assert env_float(key, 60.0) == 60.0
        finally:
            os.environ.pop(key, None)

    def test_invalid_raises_value_error_mentioning_variable(self):
        key = "TEST_ENV_FLOAT_INVALID_XYZ"
        os.environ[key] = "abc"
        try:
            with pytest.raises(ValueError) as exc_info:
                env_float(key, 1.0)
            assert key in str(exc_info.value)
        finally:
            os.environ.pop(key, None)


class TestCacheTtlSecondsBehavior:
    """CACHE_TTL_SECONDS behavior: same defaults and constraints as apps.worker.cache."""

    def test_missing_uses_default_86400(self):
        key = "CACHE_TTL_SECONDS"
        old = os.environ.pop(key, None)
        try:
            assert env_int(key, 86400, min_value=1) == 86400
        finally:
            if old is not None:
                os.environ[key] = old

    def test_empty_uses_default_86400(self):
        key = "CACHE_TTL_SECONDS"
        old = os.environ.get(key)
        os.environ[key] = ""
        try:
            assert env_int(key, 86400, min_value=1) == 86400
        finally:
            if old is not None:
                os.environ[key] = old
            else:
                os.environ.pop(key, None)

    def test_whitespace_uses_default_86400(self):
        key = "CACHE_TTL_SECONDS"
        old = os.environ.get(key)
        os.environ[key] = "   "
        try:
            assert env_int(key, 86400, min_value=1) == 86400
        finally:
            if old is not None:
                os.environ[key] = old
            else:
                os.environ.pop(key, None)

    def test_invalid_raises_value_error_mentioning_variable(self):
        key = "CACHE_TTL_SECONDS"
        old = os.environ.get(key)
        os.environ[key] = "abc"
        try:
            with pytest.raises(ValueError) as exc_info:
                env_int(key, 86400, min_value=1)
            assert "CACHE_TTL_SECONDS" in str(exc_info.value)
        finally:
            if old is not None:
                os.environ[key] = old
            else:
                os.environ.pop(key, None)

    def test_zero_raises_because_min_value_one(self):
        key = "CACHE_TTL_SECONDS"
        old = os.environ.get(key)
        os.environ[key] = "0"
        try:
            with pytest.raises(ValueError) as exc_info:
                env_int(key, 86400, min_value=1)
            assert "CACHE_TTL_SECONDS" in str(exc_info.value)
        finally:
            if old is not None:
                os.environ[key] = old
            else:
                os.environ.pop(key, None)

    def test_valid_value_parsed(self):
        key = "CACHE_TTL_SECONDS"
        old = os.environ.get(key)
        os.environ[key] = "3600"
        try:
            assert env_int(key, 86400, min_value=1) == 3600
        finally:
            if old is not None:
                os.environ[key] = old
            else:
                os.environ.pop(key, None)
