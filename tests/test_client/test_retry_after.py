"""Tests for Retry-After header parsing."""

import pytest

from src.openrouter_mcp.client.openrouter import _parse_retry_after

pytestmark = pytest.mark.unit


class TestParseRetryAfter:
    def test_none_returns_none(self):
        assert _parse_retry_after(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_retry_after("") is None

    def test_integer_seconds(self):
        assert _parse_retry_after("120") == 120.0

    def test_float_seconds(self):
        assert _parse_retry_after("1.5") == 1.5

    def test_zero_returns_zero(self):
        """Retry-After: 0 should return 0.0, not None (falsy but valid)."""
        assert _parse_retry_after("0") == 0.0

    def test_negative_clamped_to_zero(self):
        assert _parse_retry_after("-5") == 0.0

    def test_large_value_clamped_to_3600(self):
        assert _parse_retry_after("7200") == 3600.0

    def test_garbage_returns_none(self):
        assert _parse_retry_after("not-a-number") is None

    def test_http_date_format(self):
        """HTTP-date should parse to a delta in seconds."""
        from datetime import datetime, timedelta, timezone
        from email.utils import format_datetime

        future = datetime.now(timezone.utc) + timedelta(seconds=60)
        header = format_datetime(future, usegmt=True)
        result = _parse_retry_after(header)
        assert result is not None
        assert 50 <= result <= 70  # ~60 seconds, allow clock skew

    def test_nan_returns_none(self):
        assert _parse_retry_after("nan") is None

    def test_inf_clamped_to_3600(self):
        assert _parse_retry_after("inf") == 3600.0

    def test_negative_inf_clamped_to_zero(self):
        assert _parse_retry_after("-inf") == 0.0
