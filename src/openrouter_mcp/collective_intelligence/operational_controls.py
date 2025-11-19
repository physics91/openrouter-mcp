"""
Operational Controls for Collective Intelligence

This module provides configuration and enforcement of operational limits
to prevent resource exhaustion, cost overruns, and cascading failures.

Features:
- Concurrency limits using asyncio.Semaphore
- API call quotas per request
- Automatic cancellation on failure
- TTL and size limits for history storage
- Circuit breaker patterns
- Rate limiting
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConcurrencyConfig:
    """Configuration for concurrency control."""
    max_concurrent_tasks: int = 5
    max_concurrent_models: int = 3
    max_pending_tasks: int = 50
    queue_timeout_seconds: float = 60.0


@dataclass
class QuotaConfig:
    """Configuration for API call quotas."""
    max_api_calls_per_request: int = 20
    max_api_calls_per_minute: int = 100
    max_api_calls_per_hour: int = 1000
    max_tokens_per_request: int = 100000
    max_cost_per_request: float = 1.0  # dollars


@dataclass
class StorageConfig:
    """Configuration for history and cache storage limits."""
    max_history_size: int = 1000
    history_ttl_hours: int = 24
    max_cache_size_mb: int = 100
    enable_auto_cleanup: bool = True
    cleanup_interval_minutes: int = 60


@dataclass
class FailureConfig:
    """Configuration for failure handling."""
    cancel_on_first_failure: bool = False
    cancel_on_critical_failure: bool = True
    max_failures_before_cancel: int = 3
    retry_failed_tasks: bool = True
    max_retry_attempts: int = 2
    exponential_backoff: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: float = 60.0


@dataclass
class OperationalConfig:
    """Master configuration for all operational controls."""
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    quota: QuotaConfig = field(default_factory=QuotaConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    failure: FailureConfig = field(default_factory=FailureConfig)
    enable_monitoring: bool = True
    enable_alerting: bool = True

    @classmethod
    def conservative(cls) -> 'OperationalConfig':
        """Create a conservative configuration for production use."""
        return cls(
            concurrency=ConcurrencyConfig(
                max_concurrent_tasks=3,
                max_concurrent_models=2,
                max_pending_tasks=20
            ),
            quota=QuotaConfig(
                max_api_calls_per_request=10,
                max_api_calls_per_minute=50,
                max_api_calls_per_hour=500,
                max_tokens_per_request=50000,
                max_cost_per_request=0.5
            ),
            failure=FailureConfig(
                cancel_on_critical_failure=True,
                max_failures_before_cancel=2
            )
        )

    @classmethod
    def aggressive(cls) -> 'OperationalConfig':
        """Create an aggressive configuration for high-volume use."""
        return cls(
            concurrency=ConcurrencyConfig(
                max_concurrent_tasks=10,
                max_concurrent_models=5,
                max_pending_tasks=100
            ),
            quota=QuotaConfig(
                max_api_calls_per_request=50,
                max_api_calls_per_minute=200,
                max_api_calls_per_hour=2000,
                max_tokens_per_request=200000,
                max_cost_per_request=5.0
            ),
            failure=FailureConfig(
                cancel_on_first_failure=False,
                max_failures_before_cancel=5
            )
        )


class ConcurrencyLimiter:
    """Manages concurrency limits using semaphores."""

    def __init__(self, config: ConcurrencyConfig):
        self.config = config
        self.task_semaphore = asyncio.Semaphore(config.max_concurrent_tasks)
        self.model_semaphore = asyncio.Semaphore(config.max_concurrent_models)
        self.active_tasks: Set[str] = set()
        self.pending_tasks: deque = deque(maxlen=config.max_pending_tasks)
        self._lock = asyncio.Lock()

    async def acquire_task_slot(self, task_id: str) -> bool:
        """Acquire a slot for task execution."""
        try:
            await asyncio.wait_for(
                self.task_semaphore.acquire(),
                timeout=self.config.queue_timeout_seconds
            )
            async with self._lock:
                self.active_tasks.add(task_id)
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Task {task_id} timed out waiting for execution slot")
            return False

    def release_task_slot(self, task_id: str) -> None:
        """Release a task execution slot."""
        self.task_semaphore.release()
        self.active_tasks.discard(task_id)

    async def acquire_model_slot(self) -> bool:
        """Acquire a slot for model API call."""
        try:
            await self.model_semaphore.acquire()
            return True
        except Exception as e:
            logger.error(f"Failed to acquire model slot: {e}")
            return False

    def release_model_slot(self) -> None:
        """Release a model API call slot."""
        self.model_semaphore.release()

    def get_active_count(self) -> int:
        """Get number of active tasks."""
        return len(self.active_tasks)

    def is_at_capacity(self) -> bool:
        """Check if at capacity."""
        return len(self.active_tasks) >= self.config.max_concurrent_tasks


class QuotaTracker:
    """Tracks and enforces API call quotas."""

    def __init__(self, config: QuotaConfig):
        self.config = config
        self.request_calls: Dict[str, int] = {}
        self.request_tokens: Dict[str, int] = {}
        self.request_costs: Dict[str, float] = {}
        self.minute_calls: deque = deque()
        self.hour_calls: deque = deque()
        self._lock = asyncio.Lock()

    async def check_and_increment(
        self,
        request_id: str,
        tokens: int = 0,
        cost: float = 0.0
    ) -> tuple[bool, str]:
        """
        Check if request can proceed and increment counters.

        Returns:
            (can_proceed, reason_if_blocked)
        """
        async with self._lock:
            # Clean up old time-based entries
            self._cleanup_time_windows()

            # Check per-request limits
            current_calls = self.request_calls.get(request_id, 0)
            if current_calls >= self.config.max_api_calls_per_request:
                return False, f"Request quota exceeded: {current_calls}/{self.config.max_api_calls_per_request} calls"

            current_tokens = self.request_tokens.get(request_id, 0)
            if current_tokens + tokens > self.config.max_tokens_per_request:
                return False, f"Token quota exceeded: {current_tokens + tokens}/{self.config.max_tokens_per_request} tokens"

            current_cost = self.request_costs.get(request_id, 0.0)
            if current_cost + cost > self.config.max_cost_per_request:
                return False, f"Cost quota exceeded: ${current_cost + cost:.4f}/${self.config.max_cost_per_request:.2f}"

            # Check time-based limits
            if len(self.minute_calls) >= self.config.max_api_calls_per_minute:
                return False, f"Minute quota exceeded: {len(self.minute_calls)}/{self.config.max_api_calls_per_minute} calls"

            if len(self.hour_calls) >= self.config.max_api_calls_per_hour:
                return False, f"Hour quota exceeded: {len(self.hour_calls)}/{self.config.max_api_calls_per_hour} calls"

            # Increment counters
            self.request_calls[request_id] = current_calls + 1
            self.request_tokens[request_id] = current_tokens + tokens
            self.request_costs[request_id] = current_cost + cost

            now = datetime.now()
            self.minute_calls.append(now)
            self.hour_calls.append(now)

            return True, ""

    def _cleanup_time_windows(self) -> None:
        """Remove expired time window entries."""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        # Clean minute window
        while self.minute_calls and self.minute_calls[0] < minute_ago:
            self.minute_calls.popleft()

        # Clean hour window
        while self.hour_calls and self.hour_calls[0] < hour_ago:
            self.hour_calls.popleft()

    def reset_request(self, request_id: str) -> None:
        """Reset counters for a specific request."""
        self.request_calls.pop(request_id, None)
        self.request_tokens.pop(request_id, None)
        self.request_costs.pop(request_id, None)

    def get_usage(self, request_id: str) -> Dict[str, Any]:
        """Get current usage for a request."""
        return {
            'calls': self.request_calls.get(request_id, 0),
            'tokens': self.request_tokens.get(request_id, 0),
            'cost': self.request_costs.get(request_id, 0.0),
            'minute_calls': len(self.minute_calls),
            'hour_calls': len(self.hour_calls)
        }


class FailureController:
    """Manages failure handling and cancellation."""

    def __init__(self, config: FailureConfig):
        self.config = config
        self.request_failures: Dict[str, List[str]] = {}
        self.circuit_breaker_failures: Dict[str, int] = {}
        self.circuit_breaker_opened: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def record_failure(
        self,
        request_id: str,
        error_msg: str,
        is_critical: bool = False
    ) -> bool:
        """
        Record a failure and determine if execution should be cancelled.

        Returns:
            True if execution should be cancelled
        """
        async with self._lock:
            if request_id not in self.request_failures:
                self.request_failures[request_id] = []

            self.request_failures[request_id].append(error_msg)
            failure_count = len(self.request_failures[request_id])

            # Check cancellation conditions
            if is_critical and self.config.cancel_on_critical_failure:
                logger.error(f"Critical failure for {request_id}, cancelling: {error_msg}")
                return True

            if self.config.cancel_on_first_failure:
                logger.warning(f"First failure for {request_id}, cancelling: {error_msg}")
                return True

            if failure_count >= self.config.max_failures_before_cancel:
                logger.error(f"Max failures ({failure_count}) reached for {request_id}, cancelling")
                return True

            return False

    def should_retry(self, request_id: str, attempt: int) -> bool:
        """Determine if a failed task should be retried."""
        if not self.config.retry_failed_tasks:
            return False

        return attempt < self.config.max_retry_attempts

    def get_backoff_delay(self, attempt: int) -> float:
        """Calculate backoff delay for retry."""
        if not self.config.exponential_backoff:
            return 1.0

        return min(30.0, 2 ** attempt)  # Max 30 seconds

    async def check_circuit_breaker(self, component: str) -> bool:
        """Check if circuit breaker is open for a component."""
        async with self._lock:
            # Check if circuit breaker is opened
            if component in self.circuit_breaker_opened:
                opened_at = self.circuit_breaker_opened[component]
                timeout = timedelta(seconds=self.config.circuit_breaker_timeout_seconds)

                if datetime.now() - opened_at < timeout:
                    logger.warning(f"Circuit breaker open for {component}")
                    return False  # Circuit is open, reject request
                else:
                    # Timeout passed, close circuit breaker
                    del self.circuit_breaker_opened[component]
                    self.circuit_breaker_failures[component] = 0

            # Check failure threshold
            failures = self.circuit_breaker_failures.get(component, 0)
            if failures >= self.config.circuit_breaker_threshold:
                # Open circuit breaker
                self.circuit_breaker_opened[component] = datetime.now()
                logger.error(f"Circuit breaker opened for {component} after {failures} failures")
                return False

            return True

    def record_circuit_breaker_failure(self, component: str) -> None:
        """Record a failure for circuit breaker tracking."""
        self.circuit_breaker_failures[component] = \
            self.circuit_breaker_failures.get(component, 0) + 1

    def record_circuit_breaker_success(self, component: str) -> None:
        """Record a success for circuit breaker tracking."""
        if component in self.circuit_breaker_failures:
            # Gradually reduce failure count on success
            self.circuit_breaker_failures[component] = max(
                0,
                self.circuit_breaker_failures[component] - 1
            )


class StorageManager:
    """Manages history and cache storage with TTL and size limits."""

    def __init__(self, config: StorageConfig):
        self.config = config
        self.items: deque = deque(maxlen=config.max_history_size)
        self.item_timestamps: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

        if config.enable_auto_cleanup:
            self._start_cleanup_task()

    def _start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        async def cleanup_loop():
            while True:
                await asyncio.sleep(self.config.cleanup_interval_minutes * 60)
                await self.cleanup_expired()

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def add_item(self, item_id: str, item: Any) -> None:
        """Add an item to storage."""
        async with self._lock:
            self.items.append((item_id, item))
            self.item_timestamps[item_id] = datetime.now()

            # Check if we need to cleanup
            if len(self.items) >= self.config.max_history_size * 0.9:
                await self._cleanup_oldest()

    async def cleanup_expired(self) -> int:
        """Remove expired items based on TTL and enforce size limits."""
        async with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=self.config.history_ttl_hours)
            expired_ids = [
                item_id for item_id, timestamp in self.item_timestamps.items()
                if timestamp < cutoff_time
            ]

            # Remove expired items from timestamps
            for item_id in expired_ids:
                del self.item_timestamps[item_id]

            # Rebuild deque with only non-expired items, respecting maxlen
            # This properly enforces the size limit
            new_items = deque(maxlen=self.config.max_history_size)
            for item_id, item in self.items:
                if item_id not in expired_ids:
                    new_items.append((item_id, item))

            self.items = new_items

            # Clean up orphaned timestamps (items that fell off the deque due to maxlen)
            current_item_ids = {item_id for item_id, _ in self.items}
            orphaned_ids = set(self.item_timestamps.keys()) - current_item_ids
            for item_id in orphaned_ids:
                del self.item_timestamps[item_id]

            logger.info(
                f"Cleaned up {len(expired_ids)} expired items and {len(orphaned_ids)} orphaned timestamps"
            )
            return len(expired_ids)

    async def _cleanup_oldest(self) -> None:
        """Remove oldest items to make room."""
        remove_count = len(self.items) // 10  # Remove 10%
        for _ in range(remove_count):
            if self.items:
                item_id, _ = self.items.popleft()
                self.item_timestamps.pop(item_id, None)

    def get_items(self, limit: Optional[int] = None) -> List[Any]:
        """Get stored items."""
        items = [item for _, item in self.items]
        if limit:
            return items[-limit:]
        return items

    def get_count(self) -> int:
        """Get number of stored items."""
        return len(self.items)

    async def shutdown(self) -> None:
        """Shutdown storage manager."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass


class TaskCancellationManager:
    """Manages cancellation of pending tasks."""

    def __init__(self):
        self.pending_tasks: Dict[str, Set[asyncio.Task]] = {}
        self._lock = asyncio.Lock()

    async def register_task(self, request_id: str, task: asyncio.Task) -> None:
        """Register a task for potential cancellation."""
        async with self._lock:
            if request_id not in self.pending_tasks:
                self.pending_tasks[request_id] = set()
            self.pending_tasks[request_id].add(task)

    async def cancel_all_tasks(self, request_id: str, reason: str = "Request cancelled") -> int:
        """Cancel all pending tasks for a request."""
        async with self._lock:
            tasks = self.pending_tasks.get(request_id, set())
            cancelled_count = 0

            for task in tasks:
                if not task.done():
                    task.cancel()
                    cancelled_count += 1

            if cancelled_count > 0:
                logger.warning(f"Cancelled {cancelled_count} tasks for {request_id}: {reason}")

            self.pending_tasks.pop(request_id, None)
            return cancelled_count

    async def unregister_task(self, request_id: str, task: asyncio.Task) -> None:
        """Unregister a completed task."""
        async with self._lock:
            if request_id in self.pending_tasks:
                self.pending_tasks[request_id].discard(task)
                if not self.pending_tasks[request_id]:
                    del self.pending_tasks[request_id]

    def get_pending_count(self, request_id: str) -> int:
        """Get number of pending tasks for a request."""
        return len(self.pending_tasks.get(request_id, set()))
