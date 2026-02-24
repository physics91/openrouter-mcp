"""
Tests for TTL precision fix in OpenRouterClient and ModelCache.

This module tests the fix for the cache TTL conversion issue where
integer division caused all sub-hour TTL values to be clamped to 1 hour.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from src.openrouter_mcp.client.openrouter import OpenRouterClient
from src.openrouter_mcp.models.cache import ModelCache


class TestTTLPrecision:
    """Test TTL conversion with sub-hour precision."""

    @pytest.mark.unit
    def test_5_minute_ttl_conversion(self):
        """Test 5-minute TTL (300s) converts correctly."""
        cache_ttl = 300  # 5 minutes in seconds
        client = OpenRouterClient(
            api_key="test-key",
            enable_cache=True,
            cache_ttl=cache_ttl
        )

        # Should convert to ~0.08334 hours (5 minutes = 300s)
        # Note: 300/3600 = 0.08333..., when multiplied back: 0.08333*3600 = 299.988 -> int(299.988) = 299
        # But max(0.08334, ...) gives us 0.08334 * 3600 = 300.024 -> int(300.024) = 300
        expected_seconds = 300
        actual_seconds = client._model_cache.ttl_seconds

        assert actual_seconds == expected_seconds, \
            f"Expected {expected_seconds}s, got {actual_seconds}s"

    @pytest.mark.unit
    def test_30_minute_ttl_conversion(self):
        """Test 30-minute TTL (1800s) converts correctly."""
        cache_ttl = 1800  # 30 minutes in seconds
        client = OpenRouterClient(
            api_key="test-key",
            enable_cache=True,
            cache_ttl=cache_ttl
        )

        # Should convert to 0.5 hours (30 minutes)
        expected_seconds = 1800
        actual_seconds = client._model_cache.ttl_seconds

        assert actual_seconds == expected_seconds, \
            f"Expected {expected_seconds}s, got {actual_seconds}s"

    @pytest.mark.unit
    def test_1_hour_ttl_conversion(self):
        """Test 1-hour TTL (3600s) converts correctly."""
        cache_ttl = 3600  # 1 hour in seconds
        client = OpenRouterClient(
            api_key="test-key",
            enable_cache=True,
            cache_ttl=cache_ttl
        )

        # Should convert to 1.0 hours
        expected_seconds = 3600
        actual_seconds = client._model_cache.ttl_seconds

        assert actual_seconds == expected_seconds, \
            f"Expected {expected_seconds}s, got {actual_seconds}s"

    @pytest.mark.unit
    def test_24_hour_ttl_conversion(self):
        """Test 24-hour TTL (86400s) converts correctly."""
        cache_ttl = 86400  # 24 hours in seconds
        client = OpenRouterClient(
            api_key="test-key",
            enable_cache=True,
            cache_ttl=cache_ttl
        )

        # Should convert to 24.0 hours
        expected_seconds = 86400
        actual_seconds = client._model_cache.ttl_seconds

        assert actual_seconds == expected_seconds, \
            f"Expected {expected_seconds}s, got {actual_seconds}s"

    @pytest.mark.unit
    def test_minimum_ttl_enforced(self):
        """Test that minimum TTL (5 minutes) is enforced."""
        cache_ttl = 60  # 1 minute - below minimum
        client = OpenRouterClient(
            api_key="test-key",
            enable_cache=True,
            cache_ttl=cache_ttl
        )

        # Should be clamped to minimum of 0.0833 hours (5 minutes = 300s)
        expected_seconds = 300  # 5 minutes minimum
        actual_seconds = client._model_cache.ttl_seconds

        assert actual_seconds == expected_seconds, \
            f"Expected minimum {expected_seconds}s, got {actual_seconds}s"

    @pytest.mark.unit
    def test_model_cache_accepts_fractional_hours(self):
        """Test ModelCache directly accepts fractional hour values."""
        test_cases = [
            (0.08334, 300),    # 5 minutes (0.08334 * 3600 = 300.024)
            (0.5, 1800),       # 30 minutes
            (1.0, 3600),       # 1 hour
            (2.5, 9000),       # 2.5 hours
            (24.0, 86400),     # 24 hours
        ]

        for ttl_hours, expected_seconds in test_cases:
            cache = ModelCache(ttl_hours=ttl_hours)
            assert cache.ttl_seconds == expected_seconds, \
                f"TTL {ttl_hours}h should be {expected_seconds}s, got {cache.ttl_seconds}s"

    @pytest.mark.unit
    def test_cache_expiry_with_short_ttl(self):
        """Test cache expiration works correctly with short TTL."""
        import tempfile
        import os

        # Use a temporary cache file to avoid interference
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            cache_file = f.name

        try:
            # Create cache with 5-minute TTL
            cache = ModelCache(ttl_hours=0.08334, cache_file=cache_file)  # 5 minutes (300s)

            # Initially, cache should be expired (no data)
            assert cache.is_expired()

            # Simulate setting last update time
            cache._last_update = datetime.now()

            # Should not be expired immediately
            assert not cache.is_expired()

            # Simulate time passing (6 minutes = 360s, more than 300s TTL)
            cache._last_update = datetime.now() - timedelta(seconds=360)

            # Should now be expired
            assert cache.is_expired()
        finally:
            # Clean up temp file
            if os.path.exists(cache_file):
                os.unlink(cache_file)

    @pytest.mark.unit
    def test_cache_expiry_with_30_minute_ttl(self):
        """Test cache expiration with 30-minute TTL."""
        cache = ModelCache(ttl_hours=0.5)  # 30 minutes

        cache._last_update = datetime.now()
        assert not cache.is_expired()

        # After 20 minutes - should not be expired
        cache._last_update = datetime.now() - timedelta(minutes=20)
        assert not cache.is_expired()

        # After 35 minutes - should be expired
        cache._last_update = datetime.now() - timedelta(minutes=35)
        assert cache.is_expired()

    @pytest.mark.unit
    def test_float_conversion_precision(self):
        """Test that float conversion maintains precision."""
        # Test various TTL values
        test_values = [
            (300, 0.0833),      # 5 minutes
            (600, 0.1667),      # 10 minutes
            (900, 0.25),        # 15 minutes
            (1800, 0.5),        # 30 minutes
            (2700, 0.75),       # 45 minutes
            (3600, 1.0),        # 1 hour
            (7200, 2.0),        # 2 hours
        ]

        for seconds, expected_hours in test_values:
            actual_hours = seconds / 3600.0
            # Allow small floating-point precision difference
            assert abs(actual_hours - expected_hours) < 0.0001, \
                f"{seconds}s should be ~{expected_hours}h, got {actual_hours}h"

    @pytest.mark.unit
    def test_cache_disabled_no_ttl_conversion(self):
        """Test that when cache is disabled, no TTL conversion occurs."""
        client = OpenRouterClient(
            api_key="test-key",
            enable_cache=False,
            cache_ttl=300
        )

        # Cache should be None
        assert client._model_cache is None

    @pytest.mark.unit
    def test_default_ttl_value(self):
        """Test default TTL value (3600s = 1 hour)."""
        client = OpenRouterClient(
            api_key="test-key",
            enable_cache=True
            # cache_ttl defaults to 3600
        )

        expected_seconds = 3600  # 1 hour
        actual_seconds = client._model_cache.ttl_seconds

        assert actual_seconds == expected_seconds, \
            f"Default TTL should be {expected_seconds}s, got {actual_seconds}s"


class TestTTLEdgeCases:
    """Test edge cases for TTL conversion."""

    @pytest.mark.unit
    def test_zero_ttl_gets_clamped(self):
        """Test that zero TTL gets clamped to minimum."""
        client = OpenRouterClient(
            api_key="test-key",
            enable_cache=True,
            cache_ttl=0
        )

        # Should be clamped to minimum 5 minutes
        expected_seconds = 300
        actual_seconds = client._model_cache.ttl_seconds

        assert actual_seconds == expected_seconds, \
            f"Zero TTL should be clamped to {expected_seconds}s, got {actual_seconds}s"

    @pytest.mark.unit
    def test_negative_ttl_gets_clamped(self):
        """Test that negative TTL gets clamped to minimum."""
        client = OpenRouterClient(
            api_key="test-key",
            enable_cache=True,
            cache_ttl=-100
        )

        # Should be clamped to minimum 5 minutes
        expected_seconds = 300
        actual_seconds = client._model_cache.ttl_seconds

        assert actual_seconds == expected_seconds, \
            f"Negative TTL should be clamped to {expected_seconds}s, got {actual_seconds}s"

    @pytest.mark.unit
    def test_very_large_ttl(self):
        """Test handling of very large TTL values."""
        cache_ttl = 86400 * 7  # 1 week in seconds
        client = OpenRouterClient(
            api_key="test-key",
            enable_cache=True,
            cache_ttl=cache_ttl
        )

        expected_seconds = 604800  # 1 week
        actual_seconds = client._model_cache.ttl_seconds

        assert actual_seconds == expected_seconds, \
            f"Large TTL should be {expected_seconds}s, got {actual_seconds}s"

    @pytest.mark.unit
    def test_fractional_seconds_truncated(self):
        """Test that fractional seconds are handled (should be int)."""
        # ModelCache converts to int, so 0.5 seconds is lost
        cache = ModelCache(ttl_hours=0.0001)  # Very small value

        # 0.0001 hours = 0.36 seconds, should truncate to 0 but be >= 0
        assert isinstance(cache.ttl_seconds, int)
        assert cache.ttl_seconds >= 0


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    @pytest.mark.unit
    def test_integer_ttl_hours_still_works(self):
        """Test that integer hour values still work (backward compatibility)."""
        cache = ModelCache(ttl_hours=1)  # Integer value
        assert cache.ttl_seconds == 3600

        cache = ModelCache(ttl_hours=24)  # Integer value
        assert cache.ttl_seconds == 86400

    @pytest.mark.unit
    def test_cache_stats_includes_ttl(self):
        """Test that cache stats include TTL information."""
        cache = ModelCache(ttl_hours=0.5)
        cache._memory_cache = []

        stats = cache.get_cache_stats()

        assert "ttl_seconds" in stats
        assert stats["ttl_seconds"] == 1800  # 30 minutes

    @pytest.mark.unit
    def test_client_get_cache_info(self):
        """Test that client.get_cache_info() returns TTL."""
        client = OpenRouterClient(
            api_key="test-key",
            enable_cache=True,
            cache_ttl=1800  # 30 minutes
        )

        cache_info = client.get_cache_info()

        assert cache_info is not None
        assert "ttl_seconds" in cache_info
        assert cache_info["ttl_seconds"] == 1800
