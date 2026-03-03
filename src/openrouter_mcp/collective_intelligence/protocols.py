"""
Protocol-based interfaces for Collective Intelligence components.

This module defines runtime_checkable Protocol interfaces following the
Interface Segregation Principle (ISP), allowing components to depend only
on the interfaces they actually use.

Usage:
    from openrouter_mcp.collective_intelligence.protocols import (
        ConcurrencyAware,
        QuotaAware,
        FailureAware,
        StorageAware,
    )

    class MyComponent:
        def __init__(
            self,
            concurrency: Optional[ConcurrencyAware] = None,
            quota: Optional[QuotaAware] = None,
        ):
            self._concurrency = concurrency
            self._quota = quota
"""

import asyncio
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class ConcurrencyAware(Protocol):
    """
    Protocol for components that manage concurrency limits.

    Components implementing this protocol provide task and model slot management
    with capacity tracking.
    """

    async def acquire_task_slot(self, task_id: str) -> bool:
        """
        Acquire a slot for task execution.

        Args:
            task_id: Unique identifier for the task

        Returns:
            True if slot was acquired, False if timed out or rejected
        """
        ...

    def release_task_slot(self, task_id: str) -> None:
        """
        Release a task execution slot.

        Args:
            task_id: Unique identifier for the task to release
        """
        ...

    async def acquire_model_slot(self) -> bool:
        """
        Acquire a slot for model API call.

        Returns:
            True if slot was acquired, False otherwise
        """
        ...

    def release_model_slot(self) -> None:
        """Release a model API call slot."""
        ...

    def get_active_count(self) -> int:
        """Get number of currently active tasks."""
        ...

    def is_at_capacity(self) -> bool:
        """Check if currently at capacity."""
        ...


@runtime_checkable
class QuotaAware(Protocol):
    """
    Protocol for components that track and enforce quotas.

    Components implementing this protocol manage request-level and
    time-based quota enforcement.
    """

    async def check_and_increment(
        self, request_id: str, tokens: int = 0, cost: float = 0.0
    ) -> Tuple[bool, str]:
        """
        Check if request can proceed and increment counters.

        Args:
            request_id: Unique identifier for the request
            tokens: Number of tokens to add
            cost: Cost in dollars to add

        Returns:
            Tuple of (can_proceed, reason_if_blocked)
        """
        ...

    def reset_request(self, request_id: str) -> None:
        """
        Reset counters for a specific request.

        Args:
            request_id: Unique identifier for the request to reset
        """
        ...

    def get_usage(self, request_id: str) -> Dict[str, Any]:
        """
        Get current usage for a request.

        Args:
            request_id: Unique identifier for the request

        Returns:
            Dictionary containing usage metrics
        """
        ...


@runtime_checkable
class FailureAware(Protocol):
    """
    Protocol for components that handle failure tracking and recovery.

    Components implementing this protocol manage failure recording,
    retry logic, and circuit breaker patterns.
    """

    async def record_failure(
        self, request_id: str, error_msg: str, is_critical: bool = False
    ) -> bool:
        """
        Record a failure and determine if execution should be cancelled.

        Args:
            request_id: Unique identifier for the request
            error_msg: Description of the error
            is_critical: Whether this is a critical failure

        Returns:
            True if execution should be cancelled
        """
        ...

    def should_retry(self, request_id: str, attempt: int) -> bool:
        """
        Determine if a failed task should be retried.

        Args:
            request_id: Unique identifier for the request
            attempt: Current attempt number

        Returns:
            True if should retry
        """
        ...

    def get_backoff_delay(self, attempt: int) -> float:
        """
        Calculate backoff delay for retry.

        Args:
            attempt: Current attempt number

        Returns:
            Delay in seconds before next retry
        """
        ...

    async def check_circuit_breaker(self, component: str) -> bool:
        """
        Check if circuit breaker is open for a component.

        Args:
            component: Name of the component to check

        Returns:
            True if circuit is closed (can proceed), False if open
        """
        ...

    def record_circuit_breaker_failure(self, component: str) -> None:
        """
        Record a failure for circuit breaker tracking.

        Args:
            component: Name of the component that failed
        """
        ...

    def record_circuit_breaker_success(self, component: str) -> None:
        """
        Record a success for circuit breaker tracking.

        Args:
            component: Name of the component that succeeded
        """
        ...


@runtime_checkable
class StorageAware(Protocol):
    """
    Protocol for components that manage storage with TTL and size limits.

    Components implementing this protocol provide storage operations
    with automatic cleanup and capacity management.
    """

    async def add_item(self, item_id: str, item: Any) -> None:
        """
        Add an item to storage.

        Args:
            item_id: Unique identifier for the item
            item: The item to store
        """
        ...

    async def cleanup_expired(self) -> int:
        """
        Remove expired items based on TTL.

        Returns:
            Number of items removed
        """
        ...

    def get_items(self, limit: Optional[int] = None) -> List[Any]:
        """
        Get stored items.

        Args:
            limit: Maximum number of items to return (most recent)

        Returns:
            List of stored items
        """
        ...

    def get_count(self) -> int:
        """Get number of stored items."""
        ...

    async def shutdown(self) -> None:
        """Shutdown storage manager and release resources."""
        ...


@runtime_checkable
class CancellationAware(Protocol):
    """
    Protocol for components that manage task cancellation.

    Components implementing this protocol provide task registration
    and cancellation capabilities.
    """

    async def register_task(self, request_id: str, task: asyncio.Task) -> None:
        """
        Register a task for potential cancellation.

        Args:
            request_id: Unique identifier for the request
            task: The asyncio task to register
        """
        ...

    async def cancel_all_tasks(
        self, request_id: str, reason: str = "Request cancelled"
    ) -> int:
        """
        Cancel all pending tasks for a request.

        Args:
            request_id: Unique identifier for the request
            reason: Reason for cancellation (for logging)

        Returns:
            Number of tasks cancelled
        """
        ...

    async def unregister_task(self, request_id: str, task: asyncio.Task) -> None:
        """
        Unregister a completed task.

        Args:
            request_id: Unique identifier for the request
            task: The asyncio task to unregister
        """
        ...

    def get_pending_count(self, request_id: str) -> int:
        """
        Get number of pending tasks for a request.

        Args:
            request_id: Unique identifier for the request

        Returns:
            Number of pending tasks
        """
        ...


__all__ = [
    "ConcurrencyAware",
    "QuotaAware",
    "FailureAware",
    "StorageAware",
    "CancellationAware",
]
