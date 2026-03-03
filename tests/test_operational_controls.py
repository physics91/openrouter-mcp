"""
Tests for Operational Controls

This module tests the operational controls including concurrency limits,
quotas, failure handling, and storage management.
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from openrouter_mcp.collective_intelligence.operational_controls import (
    ConcurrencyConfig,
    ConcurrencyLimiter,
    FailureConfig,
    FailureController,
    OperationalConfig,
    QuotaConfig,
    QuotaTracker,
    StorageConfig,
    StorageManager,
    TaskCancellationManager,
)


class TestConcurrencyLimiter:
    """Tests for ConcurrencyLimiter."""

    @pytest.mark.asyncio
    async def test_task_slot_acquisition(self):
        """Test task slot acquisition and release."""
        config = ConcurrencyConfig(max_concurrent_tasks=2)
        limiter = ConcurrencyLimiter(config)

        # Acquire two slots
        assert await limiter.acquire_task_slot("task1")
        assert await limiter.acquire_task_slot("task2")
        assert limiter.get_active_count() == 2
        assert limiter.is_at_capacity()

        # Try to acquire third slot - should return False after timeout
        config_short_timeout = ConcurrencyConfig(
            max_concurrent_tasks=2, queue_timeout_seconds=0.1
        )
        limiter_short = ConcurrencyLimiter(config_short_timeout)
        await limiter_short.acquire_task_slot("task1")
        await limiter_short.acquire_task_slot("task2")
        result = await limiter_short.acquire_task_slot("task3")
        assert result is False

    @pytest.mark.asyncio
    async def test_task_slot_release(self):
        """Test task slot release."""
        config = ConcurrencyConfig(max_concurrent_tasks=2)
        limiter = ConcurrencyLimiter(config)

        await limiter.acquire_task_slot("task1")
        await limiter.acquire_task_slot("task2")
        assert limiter.get_active_count() == 2

        # Release one slot
        limiter.release_task_slot("task1")
        assert limiter.get_active_count() == 1
        assert not limiter.is_at_capacity()

    @pytest.mark.asyncio
    async def test_model_slot_acquisition(self):
        """Test model API slot acquisition and release."""
        config = ConcurrencyConfig(max_concurrent_models=2)
        limiter = ConcurrencyLimiter(config)

        assert await limiter.acquire_model_slot()
        assert await limiter.acquire_model_slot()

        limiter.release_model_slot()
        assert await limiter.acquire_model_slot()


class TestQuotaTracker:
    """Tests for QuotaTracker."""

    @pytest.mark.asyncio
    async def test_per_request_call_quota(self):
        """Test per-request API call quota enforcement."""
        config = QuotaConfig(max_api_calls_per_request=3)
        tracker = QuotaTracker(config)

        # First 3 calls should succeed
        can_proceed, _ = await tracker.check_and_increment("req1")
        assert can_proceed
        can_proceed, _ = await tracker.check_and_increment("req1")
        assert can_proceed
        can_proceed, _ = await tracker.check_and_increment("req1")
        assert can_proceed

        # 4th call should fail
        can_proceed, reason = await tracker.check_and_increment("req1")
        assert not can_proceed
        assert "Request quota exceeded" in reason

    @pytest.mark.asyncio
    async def test_token_quota(self):
        """Test token quota enforcement."""
        config = QuotaConfig(max_tokens_per_request=100)
        tracker = QuotaTracker(config)

        # Should succeed with 90 tokens
        can_proceed, _ = await tracker.check_and_increment("req1", tokens=90)
        assert can_proceed

        # Should fail with additional 20 tokens
        can_proceed, reason = await tracker.check_and_increment("req1", tokens=20)
        assert not can_proceed
        assert "Token quota exceeded" in reason

    @pytest.mark.asyncio
    async def test_cost_quota(self):
        """Test cost quota enforcement."""
        config = QuotaConfig(max_cost_per_request=1.0)
        tracker = QuotaTracker(config)

        # Should succeed with $0.50
        can_proceed, _ = await tracker.check_and_increment("req1", cost=0.5)
        assert can_proceed

        # Should fail with additional $0.60
        can_proceed, reason = await tracker.check_and_increment("req1", cost=0.6)
        assert not can_proceed
        assert "Cost quota exceeded" in reason

    @pytest.mark.asyncio
    async def test_quota_reset(self):
        """Test quota reset for a request."""
        config = QuotaConfig(max_api_calls_per_request=2)
        tracker = QuotaTracker(config)

        # Use up quota
        await tracker.check_and_increment("req1")
        await tracker.check_and_increment("req1")
        can_proceed, _ = await tracker.check_and_increment("req1")
        assert not can_proceed

        # Reset and try again
        tracker.reset_request("req1")
        can_proceed, _ = await tracker.check_and_increment("req1")
        assert can_proceed

    @pytest.mark.asyncio
    async def test_usage_tracking(self):
        """Test usage tracking."""
        config = QuotaConfig()
        tracker = QuotaTracker(config)

        await tracker.check_and_increment("req1", tokens=100, cost=0.5)
        await tracker.check_and_increment("req1", tokens=50, cost=0.3)

        usage = tracker.get_usage("req1")
        assert usage["calls"] == 2
        assert usage["tokens"] == 150
        assert usage["cost"] == 0.8


class TestFailureController:
    """Tests for FailureController."""

    @pytest.mark.asyncio
    async def test_critical_failure_cancellation(self):
        """Test cancellation on critical failure."""
        config = FailureConfig(cancel_on_critical_failure=True)
        controller = FailureController(config)

        should_cancel = await controller.record_failure(
            "req1", "Critical error", is_critical=True
        )
        assert should_cancel

    @pytest.mark.asyncio
    async def test_max_failures_cancellation(self):
        """Test cancellation after max failures."""
        config = FailureConfig(max_failures_before_cancel=3)
        controller = FailureController(config)

        # First two failures should not cancel
        assert not await controller.record_failure("req1", "Error 1")
        assert not await controller.record_failure("req1", "Error 2")

        # Third failure should cancel
        should_cancel = await controller.record_failure("req1", "Error 3")
        assert should_cancel

    @pytest.mark.asyncio
    async def test_retry_logic(self):
        """Test retry decision logic."""
        config = FailureConfig(retry_failed_tasks=True, max_retry_attempts=2)
        controller = FailureController(config)

        assert controller.should_retry("req1", attempt=0)
        assert controller.should_retry("req1", attempt=1)
        assert not controller.should_retry("req1", attempt=2)

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        config = FailureConfig(exponential_backoff=True)
        controller = FailureController(config)

        delay1 = controller.get_backoff_delay(0)
        delay2 = controller.get_backoff_delay(1)
        delay3 = controller.get_backoff_delay(2)

        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 4.0

    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
        config = FailureConfig(
            circuit_breaker_threshold=3, circuit_breaker_timeout_seconds=1.0
        )
        controller = FailureController(config)

        # Circuit should be closed initially
        assert await controller.check_circuit_breaker("component1")

        # Record failures to open circuit
        for _ in range(3):
            controller.record_circuit_breaker_failure("component1")

        # Circuit should be open
        assert not await controller.check_circuit_breaker("component1")

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Circuit should close after timeout
        assert await controller.check_circuit_breaker("component1")

    @pytest.mark.asyncio
    async def test_circuit_breaker_success_recovery(self):
        """Test circuit breaker recovery on success."""
        config = FailureConfig(circuit_breaker_threshold=3)
        controller = FailureController(config)

        # Record failures
        controller.record_circuit_breaker_failure("component1")
        controller.record_circuit_breaker_failure("component1")

        # Record success - should reduce failure count
        controller.record_circuit_breaker_success("component1")

        # Should still be under threshold
        assert await controller.check_circuit_breaker("component1")


class TestStorageManager:
    """Tests for StorageManager."""

    @pytest.mark.asyncio
    async def test_item_storage(self):
        """Test basic item storage."""
        config = StorageConfig(max_history_size=10, enable_auto_cleanup=False)
        manager = StorageManager(config)

        await manager.add_item("item1", {"data": "test1"})
        await manager.add_item("item2", {"data": "test2"})

        items = manager.get_items()
        assert len(items) == 2
        assert manager.get_count() == 2

    @pytest.mark.asyncio
    async def test_size_limit_enforcement(self):
        """Test size limit enforcement."""
        config = StorageConfig(max_history_size=3, enable_auto_cleanup=False)
        manager = StorageManager(config)

        # Add items up to limit
        for i in range(5):
            await manager.add_item(f"item{i}", {"data": f"test{i}"})

        # Should only keep last 3 items due to deque maxlen
        assert manager.get_count() == 3

    @pytest.mark.asyncio
    async def test_ttl_cleanup(self):
        """Test TTL-based cleanup."""
        config = StorageConfig(
            history_ttl_hours=1, enable_auto_cleanup=False
        )  # 1 hour TTL
        manager = StorageManager(config)

        # Add items with backdated timestamps
        await manager.add_item("item1", {"data": "test1"})
        manager.item_timestamps["item1"] = datetime.now() - timedelta(
            hours=2
        )  # Expired

        await manager.add_item("item2", {"data": "test2"})  # Current, not expired

        # Cleanup expired items
        expired_count = await manager.cleanup_expired()
        assert expired_count == 1
        assert manager.get_count() == 1

    @pytest.mark.asyncio
    async def test_get_items_with_limit(self):
        """Test getting items with limit."""
        config = StorageConfig(max_history_size=10, enable_auto_cleanup=False)
        manager = StorageManager(config)

        for i in range(5):
            await manager.add_item(f"item{i}", {"data": f"test{i}"})

        items = manager.get_items(limit=2)
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test storage manager shutdown."""
        config = StorageConfig(enable_auto_cleanup=True, cleanup_interval_minutes=1)
        manager = StorageManager(config)

        # Shutdown should cancel cleanup task
        await manager.shutdown()

        # Cleanup task should be cancelled
        assert manager._cleanup_task.cancelled() or manager._cleanup_task.done()


class TestTaskCancellationManager:
    """Tests for TaskCancellationManager."""

    @pytest.mark.asyncio
    async def test_task_registration(self):
        """Test task registration and tracking."""
        manager = TaskCancellationManager()

        async def dummy_task():
            await asyncio.sleep(1)

        task = asyncio.create_task(dummy_task())
        await manager.register_task("req1", task)

        assert manager.get_pending_count("req1") == 1

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_cancel_all_tasks(self):
        """Test cancelling all tasks for a request."""
        manager = TaskCancellationManager()

        async def long_running_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass

        # Create multiple tasks
        tasks = [asyncio.create_task(long_running_task()) for _ in range(3)]
        for task in tasks:
            await manager.register_task("req1", task)

        # Give tasks a moment to start
        await asyncio.sleep(0.01)

        # Cancel all tasks
        cancelled_count = await manager.cancel_all_tasks("req1", "Test cancellation")
        assert cancelled_count == 3

        # Wait for cancellation to propagate
        await asyncio.sleep(0.01)

        # Verify all tasks are done (either cancelled or completed)
        for task in tasks:
            assert task.done()

    @pytest.mark.asyncio
    async def test_unregister_completed_task(self):
        """Test unregistering completed tasks."""
        manager = TaskCancellationManager()

        async def quick_task():
            await asyncio.sleep(0.1)

        task = asyncio.create_task(quick_task())
        await manager.register_task("req1", task)
        await task
        await manager.unregister_task("req1", task)

        assert manager.get_pending_count("req1") == 0


class TestOperationalConfig:
    """Tests for OperationalConfig presets."""

    def test_conservative_config(self):
        """Test conservative configuration preset."""
        config = OperationalConfig.conservative()

        assert config.concurrency.max_concurrent_tasks == 3
        assert config.quota.max_api_calls_per_request == 10
        assert config.failure.cancel_on_critical_failure is True

    def test_aggressive_config(self):
        """Test aggressive configuration preset."""
        config = OperationalConfig.aggressive()

        assert config.concurrency.max_concurrent_tasks == 10
        assert config.quota.max_api_calls_per_request == 50
        assert config.failure.cancel_on_first_failure is False

    def test_default_config(self):
        """Test default configuration."""
        config = OperationalConfig()

        assert config.concurrency.max_concurrent_tasks == 5
        assert config.quota.max_api_calls_per_request == 20
        assert config.storage.max_history_size == 1000
        assert config.enable_monitoring is True


class TestIntegration:
    """Integration tests for operational controls."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_controls(self):
        """Test full workflow with all controls active."""
        config = OperationalConfig.conservative()
        limiter = ConcurrencyLimiter(config.concurrency)
        tracker = QuotaTracker(config.quota)
        controller = FailureController(config.failure)

        # Simulate request workflow
        request_id = "test_request"

        # Acquire slot
        acquired = await limiter.acquire_task_slot(request_id)
        assert acquired

        try:
            # Check quota
            can_proceed, _ = await tracker.check_and_increment(request_id, tokens=100)
            assert can_proceed

            # Simulate processing
            await asyncio.sleep(0.1)

            # Success case
            controller.record_circuit_breaker_success("test_component")

        finally:
            limiter.release_task_slot(request_id)
            tracker.reset_request(request_id)

    @pytest.mark.asyncio
    async def test_failure_cascade_prevention(self):
        """Test that failures are properly contained."""
        config = OperationalConfig(
            failure=FailureConfig(
                max_failures_before_cancel=2, cancel_on_critical_failure=True
            )
        )
        controller = FailureController(config.failure)
        cancellation_manager = TaskCancellationManager()

        request_id = "test_request"

        # Create tasks
        async def failing_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass

        tasks = [asyncio.create_task(failing_task()) for _ in range(3)]
        for task in tasks:
            await cancellation_manager.register_task(request_id, task)

        # Give tasks a moment to start
        await asyncio.sleep(0.01)

        # Record critical failure
        should_cancel = await controller.record_failure(
            request_id, "Critical error", is_critical=True
        )
        assert should_cancel

        # Cancel all pending tasks
        cancelled = await cancellation_manager.cancel_all_tasks(
            request_id, "Failure cascade prevention"
        )
        assert cancelled == 3

        # Wait for cancellation
        await asyncio.sleep(0.01)

        # Verify all tasks are done
        for task in tasks:
            assert task.done()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
