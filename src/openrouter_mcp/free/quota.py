"""Daily and per-minute quota tracking for free model usage."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from ..config.constants import FreeChatConfig

logger = logging.getLogger(__name__)


class QuotaExceededError(RuntimeError):
    """Raised when a quota limit is exceeded."""

    def __init__(self, message: str, reset_time: datetime):
        super().__init__(message)
        self.reset_time = reset_time


class QuotaTracker:
    """Tracks daily and per-minute request counts with atomic reserve.

    All mutations go through ``reserve_and_record()`` which holds an
    ``asyncio.Lock`` to prevent TOCTOU races under concurrent awaits.
    """

    def __init__(
        self,
        daily_limit: int = FreeChatConfig.FREE_DAILY_LIMIT,
        minute_limit: int = FreeChatConfig.FREE_MINUTE_LIMIT,
    ) -> None:
        self._daily_limit = daily_limit
        self._minute_limit = minute_limit
        self._lock = asyncio.Lock()

        self._daily_count = 0
        self._minute_count = 0
        self._day_start = self._current_day_start()
        self._minute_start = self._current_minute_start()

    # ------------------------------------------------------------------
    # Time helpers (UTC-based)
    # ------------------------------------------------------------------
    @staticmethod
    def _current_day_start() -> datetime:
        now = datetime.now(timezone.utc)
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _current_minute_start() -> datetime:
        now = datetime.now(timezone.utc)
        return now.replace(second=0, microsecond=0)

    def _maybe_reset(self) -> None:
        """Reset counters if their time window has expired (called inside lock)."""
        now_day = self._current_day_start()
        if now_day > self._day_start:
            self._daily_count = 0
            self._day_start = now_day

        now_min = self._current_minute_start()
        if now_min > self._minute_start:
            self._minute_count = 0
            self._minute_start = now_min

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def reserve_and_record(self) -> None:
        """Atomically check limits and increment counters.

        Raises ``QuotaExceededError`` if either limit is reached.
        """
        async with self._lock:
            self._maybe_reset()

            if self._daily_count >= self._daily_limit:
                reset = self._day_start + timedelta(days=1)
                raise QuotaExceededError(
                    f"일일 무료 사용 한도({self._daily_limit}회)를 초과했습니다. "
                    f"UTC {reset.strftime('%H:%M')}에 리셋됩니다.",
                    reset_time=reset,
                )

            if self._minute_count >= self._minute_limit:
                reset = self._minute_start + timedelta(minutes=1)
                raise QuotaExceededError(
                    f"분당 무료 사용 한도({self._minute_limit}회)를 초과했습니다. "
                    f"잠시 후 다시 시도해주세요.",
                    reset_time=reset,
                )

            self._daily_count += 1
            self._minute_count += 1

    def get_quota_status(self) -> dict:
        """Return current quota status (lock-free, approximate)."""
        return {
            "daily_used": self._daily_count,
            "daily_limit": self._daily_limit,
            "daily_remaining": max(0, self._daily_limit - self._daily_count),
            "minute_used": self._minute_count,
            "minute_limit": self._minute_limit,
            "minute_remaining": max(0, self._minute_limit - self._minute_count),
        }
