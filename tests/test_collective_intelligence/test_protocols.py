"""
Tests for Protocol interfaces in collective intelligence module.

Verifies that operational control classes properly implement the
ISP-compliant Protocol interfaces.
"""

import pytest
import asyncio
from typing import get_type_hints

from openrouter_mcp.collective_intelligence.protocols import (
    ConcurrencyAware,
    QuotaAware,
    FailureAware,
    StorageAware,
    CancellationAware,
)
from openrouter_mcp.collective_intelligence.operational_controls import (
    ConcurrencyLimiter,
    ConcurrencyConfig,
    QuotaTracker,
    QuotaConfig,
    FailureController,
    FailureConfig,
    StorageManager,
    StorageConfig,
    TaskCancellationManager,
)


class TestConcurrencyAwareProtocol:
    """Tests for ConcurrencyAware protocol implementation."""

    def test_concurrency_limiter_implements_protocol(self):
        """ConcurrencyLimiter should implement ConcurrencyAware protocol."""
        config = ConcurrencyConfig()
        limiter = ConcurrencyLimiter(config)

        # isinstance check with runtime_checkable Protocol
        assert isinstance(limiter, ConcurrencyAware)

    def test_concurrency_aware_has_required_methods(self):
        """ConcurrencyAware protocol should define all required methods."""
        required_methods = [
            'acquire_task_slot',
            'release_task_slot',
            'acquire_model_slot',
            'release_model_slot',
            'get_active_count',
            'is_at_capacity',
        ]

        for method in required_methods:
            assert hasattr(ConcurrencyAware, method)

    @pytest.mark.asyncio
    async def test_concurrency_limiter_methods_work(self):
        """ConcurrencyLimiter methods should work as expected."""
        config = ConcurrencyConfig(max_concurrent_tasks=2)
        limiter = ConcurrencyLimiter(config)

        # Test acquire and release task slot
        assert await limiter.acquire_task_slot("test-1")
        assert limiter.get_active_count() == 1
        assert not limiter.is_at_capacity()

        assert await limiter.acquire_task_slot("test-2")
        assert limiter.get_active_count() == 2
        assert limiter.is_at_capacity()

        limiter.release_task_slot("test-1")
        assert limiter.get_active_count() == 1
        assert not limiter.is_at_capacity()


class TestQuotaAwareProtocol:
    """Tests for QuotaAware protocol implementation."""

    def test_quota_tracker_implements_protocol(self):
        """QuotaTracker should implement QuotaAware protocol."""
        config = QuotaConfig()
        tracker = QuotaTracker(config)

        assert isinstance(tracker, QuotaAware)

    def test_quota_aware_has_required_methods(self):
        """QuotaAware protocol should define all required methods."""
        required_methods = [
            'check_and_increment',
            'reset_request',
            'get_usage',
        ]

        for method in required_methods:
            assert hasattr(QuotaAware, method)

    @pytest.mark.asyncio
    async def test_quota_tracker_methods_work(self):
        """QuotaTracker methods should work as expected."""
        config = QuotaConfig(
            max_api_calls_per_request=5,
            max_tokens_per_request=1000,
            max_cost_per_request=1.0
        )
        tracker = QuotaTracker(config)

        # Test check_and_increment
        can_proceed, reason = await tracker.check_and_increment(
            "req-1", tokens=100, cost=0.1
        )
        assert can_proceed
        assert reason == ""

        # Test get_usage
        usage = tracker.get_usage("req-1")
        assert usage['calls'] == 1
        assert usage['tokens'] == 100
        assert usage['cost'] == 0.1

        # Test reset_request
        tracker.reset_request("req-1")
        usage = tracker.get_usage("req-1")
        assert usage['calls'] == 0


class TestFailureAwareProtocol:
    """Tests for FailureAware protocol implementation."""

    def test_failure_controller_implements_protocol(self):
        """FailureController should implement FailureAware protocol."""
        config = FailureConfig()
        controller = FailureController(config)

        assert isinstance(controller, FailureAware)

    def test_failure_aware_has_required_methods(self):
        """FailureAware protocol should define all required methods."""
        required_methods = [
            'record_failure',
            'should_retry',
            'get_backoff_delay',
            'check_circuit_breaker',
            'record_circuit_breaker_failure',
            'record_circuit_breaker_success',
        ]

        for method in required_methods:
            assert hasattr(FailureAware, method)

    @pytest.mark.asyncio
    async def test_failure_controller_methods_work(self):
        """FailureController methods should work as expected."""
        config = FailureConfig(
            max_failures_before_cancel=3,
            retry_failed_tasks=True,
            max_retry_attempts=2
        )
        controller = FailureController(config)

        # Test record_failure
        should_cancel = await controller.record_failure("req-1", "error 1")
        assert not should_cancel

        # Test should_retry
        assert controller.should_retry("req-1", attempt=0)
        assert controller.should_retry("req-1", attempt=1)
        assert not controller.should_retry("req-1", attempt=2)

        # Test get_backoff_delay
        delay = controller.get_backoff_delay(attempt=2)
        assert delay > 0

        # Test circuit breaker
        can_proceed = await controller.check_circuit_breaker("test-component")
        assert can_proceed


class TestStorageAwareProtocol:
    """Tests for StorageAware protocol implementation."""

    def test_storage_manager_implements_protocol(self):
        """StorageManager should implement StorageAware protocol."""
        config = StorageConfig(enable_auto_cleanup=False)
        manager = StorageManager(config)

        assert isinstance(manager, StorageAware)

    def test_storage_aware_has_required_methods(self):
        """StorageAware protocol should define all required methods."""
        required_methods = [
            'add_item',
            'cleanup_expired',
            'get_items',
            'get_count',
            'shutdown',
        ]

        for method in required_methods:
            assert hasattr(StorageAware, method)

    @pytest.mark.asyncio
    async def test_storage_manager_methods_work(self):
        """StorageManager methods should work as expected."""
        config = StorageConfig(
            max_history_size=10,
            enable_auto_cleanup=False
        )
        manager = StorageManager(config)

        try:
            # Test add_item
            await manager.add_item("item-1", {"data": "test1"})
            await manager.add_item("item-2", {"data": "test2"})

            # Test get_count
            assert manager.get_count() == 2

            # Test get_items
            items = manager.get_items()
            assert len(items) == 2

            items_limited = manager.get_items(limit=1)
            assert len(items_limited) == 1

            # Test cleanup_expired
            cleaned = await manager.cleanup_expired()
            assert cleaned >= 0
        finally:
            await manager.shutdown()


class TestCancellationAwareProtocol:
    """Tests for CancellationAware protocol implementation."""

    def test_cancellation_manager_implements_protocol(self):
        """TaskCancellationManager should implement CancellationAware protocol."""
        manager = TaskCancellationManager()

        assert isinstance(manager, CancellationAware)

    def test_cancellation_aware_has_required_methods(self):
        """CancellationAware protocol should define all required methods."""
        required_methods = [
            'register_task',
            'cancel_all_tasks',
            'unregister_task',
            'get_pending_count',
        ]

        for method in required_methods:
            assert hasattr(CancellationAware, method)

    @pytest.mark.asyncio
    async def test_cancellation_manager_methods_work(self):
        """TaskCancellationManager methods should work as expected."""
        manager = TaskCancellationManager()

        # Create a dummy task
        async def dummy_coro():
            await asyncio.sleep(100)

        task = asyncio.create_task(dummy_coro())

        try:
            # Test register_task
            await manager.register_task("req-1", task)
            assert manager.get_pending_count("req-1") == 1

            # Test cancel_all_tasks
            cancelled = await manager.cancel_all_tasks("req-1", "test cancellation")
            assert cancelled == 1
            assert manager.get_pending_count("req-1") == 0
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


class TestProtocolTypeChecking:
    """Tests for Protocol type checking behavior."""

    def test_non_implementing_class_fails_isinstance(self):
        """Classes not implementing protocol should fail isinstance check."""

        class NotConcurrencyAware:
            pass

        obj = NotConcurrencyAware()
        assert not isinstance(obj, ConcurrencyAware)

    def test_partial_implementation_fails_isinstance(self):
        """Classes with partial implementation should fail isinstance check."""

        class PartialConcurrencyAware:
            async def acquire_task_slot(self, task_id: str) -> bool:
                return True
            # Missing other required methods

        obj = PartialConcurrencyAware()
        # Note: runtime_checkable only checks method existence, not signatures
        # This test documents that partial implementations are rejected
        assert not isinstance(obj, ConcurrencyAware)

    def test_duck_typed_class_passes_isinstance(self):
        """Duck-typed classes with all methods should pass isinstance check."""

        class DuckTypedConcurrencyAware:
            async def acquire_task_slot(self, task_id: str) -> bool:
                return True

            def release_task_slot(self, task_id: str) -> None:
                pass

            async def acquire_model_slot(self) -> bool:
                return True

            def release_model_slot(self) -> None:
                pass

            def get_active_count(self) -> int:
                return 0

            def is_at_capacity(self) -> bool:
                return False

        obj = DuckTypedConcurrencyAware()
        assert isinstance(obj, ConcurrencyAware)
