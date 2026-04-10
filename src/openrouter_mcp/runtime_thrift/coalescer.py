"""In-flight request coalescing for identical work."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Dict, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class _RecentResult(Generic[T]):
    value: T
    expires_at: float


class RequestCoalescer(Generic[T]):
    """Share in-flight work and optionally reuse fresh successful results briefly."""

    def __init__(self, time_fn: Optional[Callable[[], float]] = None) -> None:
        self._lock = asyncio.Lock()
        self._inflight: Dict[str, asyncio.Task[T]] = {}
        self._recent: Dict[str, _RecentResult[T]] = {}
        self._time_fn = time_fn or time.monotonic

    async def run(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl_seconds: int = 0,
        on_follower_join: Optional[Callable[[], None]] = None,
        on_recent_result_reuse: Optional[Callable[[], None]] = None,
    ) -> T:
        """Run the factory once per key while work is in flight or freshly cached."""
        ttl_seconds = max(0, int(ttl_seconds))
        created_task = False

        async with self._lock:
            now = self._time_fn()
            self._drop_expired_entries(now)

            if ttl_seconds <= 0:
                self._recent.pop(key, None)
            else:
                recent = self._recent.get(key)
                if recent is not None:
                    if on_recent_result_reuse is not None:
                        on_recent_result_reuse()
                    return recent.value

            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(factory())
                self._inflight[key] = task
                created_task = True
            elif on_follower_join is not None:
                on_follower_join()

        try:
            result = await task
        except BaseException:
            if created_task:
                async with self._lock:
                    if self._inflight.get(key) is task:
                        self._inflight.pop(key, None)
            raise

        if created_task:
            async with self._lock:
                if self._inflight.get(key) is task:
                    self._inflight.pop(key, None)
                if ttl_seconds > 0:
                    self._recent[key] = _RecentResult(
                        value=result,
                        expires_at=self._time_fn() + ttl_seconds,
                    )

        return result

    def _drop_expired_entries(self, now: float) -> None:
        expired_keys = [key for key, recent in self._recent.items() if recent.expires_at <= now]
        for key in expired_keys:
            self._recent.pop(key, None)
