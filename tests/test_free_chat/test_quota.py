"""Tests for daily and per-minute quota tracking."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.openrouter_mcp.config.constants import FreeChatConfig
from src.openrouter_mcp.free.quota import QuotaExceededError, QuotaTracker

pytestmark = pytest.mark.unit


class TestQuotaTrackerBasic:
    @pytest.mark.asyncio
    async def test_allows_requests_within_daily_limit(self):
        tracker = QuotaTracker(daily_limit=3, minute_limit=100)
        for _ in range(3):
            await tracker.reserve_and_record()
        status = tracker.get_quota_status()
        assert status["daily_used"] == 3
        assert status["daily_remaining"] == 0

    @pytest.mark.asyncio
    async def test_exceeds_daily_limit(self):
        tracker = QuotaTracker(daily_limit=2, minute_limit=100)
        await tracker.reserve_and_record()
        await tracker.reserve_and_record()
        with pytest.raises(QuotaExceededError, match="일일 무료 사용 한도"):
            await tracker.reserve_and_record()

    @pytest.mark.asyncio
    async def test_exceeds_minute_limit(self):
        tracker = QuotaTracker(daily_limit=100, minute_limit=2)
        await tracker.reserve_and_record()
        await tracker.reserve_and_record()
        with pytest.raises(QuotaExceededError, match="분당 무료 사용 한도"):
            await tracker.reserve_and_record()

    @pytest.mark.asyncio
    async def test_quota_exceeded_has_reset_time(self):
        tracker = QuotaTracker(daily_limit=1, minute_limit=100)
        await tracker.reserve_and_record()
        with pytest.raises(QuotaExceededError) as exc_info:
            await tracker.reserve_and_record()
        assert isinstance(exc_info.value.reset_time, datetime)
        assert exc_info.value.reset_time.tzinfo == timezone.utc


class TestQuotaTrackerReset:
    @pytest.mark.asyncio
    async def test_daily_reset_on_new_day(self):
        tracker = QuotaTracker(daily_limit=1, minute_limit=100)
        await tracker.reserve_and_record()

        # Simulate day change
        yesterday = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=1)
        tracker._day_start = yesterday

        # Should succeed after day reset
        await tracker.reserve_and_record()
        assert tracker.get_quota_status()["daily_used"] == 1

    @pytest.mark.asyncio
    async def test_minute_reset_on_new_minute(self):
        tracker = QuotaTracker(daily_limit=100, minute_limit=1)
        await tracker.reserve_and_record()

        # Simulate minute change
        last_minute = datetime.now(timezone.utc).replace(
            second=0, microsecond=0
        ) - timedelta(minutes=1)
        tracker._minute_start = last_minute

        # Should succeed after minute reset
        await tracker.reserve_and_record()
        assert tracker.get_quota_status()["minute_used"] == 1


class TestQuotaTrackerStatus:
    @pytest.mark.asyncio
    async def test_status_structure(self):
        tracker = QuotaTracker(daily_limit=50, minute_limit=20)
        status = tracker.get_quota_status()
        assert set(status.keys()) == {
            "daily_used",
            "daily_limit",
            "daily_remaining",
            "minute_used",
            "minute_limit",
            "minute_remaining",
        }

    @pytest.mark.asyncio
    async def test_status_reflects_usage(self):
        tracker = QuotaTracker(daily_limit=10, minute_limit=5)
        await tracker.reserve_and_record()
        await tracker.reserve_and_record()
        status = tracker.get_quota_status()
        assert status["daily_used"] == 2
        assert status["daily_remaining"] == 8
        assert status["minute_used"] == 2
        assert status["minute_remaining"] == 3


class TestQuotaTrackerDefaults:
    def test_uses_config_defaults(self):
        tracker = QuotaTracker()
        status = tracker.get_quota_status()
        assert status["daily_limit"] == FreeChatConfig.FREE_DAILY_LIMIT
        assert status["minute_limit"] == FreeChatConfig.FREE_MINUTE_LIMIT


class TestQuotaTrackerConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_reserves_respect_limit(self):
        limit = 10
        tracker = QuotaTracker(daily_limit=limit, minute_limit=100)

        results = await asyncio.gather(
            *[tracker.reserve_and_record() for _ in range(limit + 5)],
            return_exceptions=True,
        )

        successes = [r for r in results if r is None]
        failures = [r for r in results if isinstance(r, QuotaExceededError)]

        assert len(successes) == limit
        assert len(failures) == 5
