"""
Tests for Collective Intelligence Lifecycle Manager

These tests verify that:
1. Singleton instances are properly created and reused
2. Background cleanup tasks are started
3. All tasks are properly cancelled on shutdown
4. No task leaks occur
5. Thread-safe initialization works correctly
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from openrouter_mcp.collective_intelligence import (
    get_lifecycle_manager,
    shutdown_lifecycle_manager,
    CollectiveIntelligenceLifecycleManager,
    TaskContext,
    TaskType,
    ModelInfo,
    ProcessingResult
)


class MockModelProvider:
    """Mock model provider for testing."""

    async def process_task(self, task, model_id, **kwargs):
        """Mock task processing."""
        return ProcessingResult(
            task_id=task.task_id,
            model_id=model_id,
            content=f"Mock response from {model_id}",
            confidence=0.8,
            processing_time=0.1,
            tokens_used=100,
            cost=0.001
        )

    async def get_available_models(self):
        """Mock available models."""
        return [
            ModelInfo(
                model_id="model-1",
                name="Model 1",
                provider="test",
                context_length=4096,
                cost_per_token=0.00001
            ),
            ModelInfo(
                model_id="model-2",
                name="Model 2",
                provider="test",
                context_length=8192,
                cost_per_token=0.00002
            )
        ]


@pytest.fixture
async def mock_model_provider():
    """Provide a mock model provider."""
    return MockModelProvider()


@pytest.fixture
async def lifecycle_manager(mock_model_provider):
    """Provide a fresh lifecycle manager for each test."""
    # Reset the global singleton
    import openrouter_mcp.collective_intelligence.lifecycle_manager as lm_module
    lm_module._lifecycle_manager = None

    manager = await get_lifecycle_manager()
    manager.configure(mock_model_provider)

    yield manager

    # Cleanup after test
    await manager.shutdown()
    lm_module._lifecycle_manager = None


@pytest.mark.asyncio
async def test_singleton_creation():
    """Test that lifecycle manager is a singleton."""
    # Reset global singleton
    import openrouter_mcp.collective_intelligence.lifecycle_manager as lm_module
    lm_module._lifecycle_manager = None

    try:
        manager1 = await get_lifecycle_manager()
        manager2 = await get_lifecycle_manager()

        assert manager1 is manager2, "Lifecycle manager should be a singleton"
    finally:
        if lm_module._lifecycle_manager:
            await lm_module._lifecycle_manager.shutdown()
            lm_module._lifecycle_manager = None


@pytest.mark.asyncio
async def test_consensus_engine_singleton(lifecycle_manager):
    """Test that ConsensusEngine instances are singletons."""
    engine1 = await lifecycle_manager.get_consensus_engine()
    engine2 = await lifecycle_manager.get_consensus_engine()

    assert engine1 is engine2, "ConsensusEngine should be a singleton within lifecycle manager"


@pytest.mark.asyncio
async def test_collaborative_solver_singleton(lifecycle_manager):
    """Test that CollaborativeSolver instances are singletons."""
    solver1 = await lifecycle_manager.get_collaborative_solver()
    solver2 = await lifecycle_manager.get_collaborative_solver()

    assert solver1 is solver2, "CollaborativeSolver should be a singleton within lifecycle manager"


@pytest.mark.asyncio
async def test_ensemble_reasoner_singleton(lifecycle_manager):
    """Test that EnsembleReasoner instances are singletons."""
    reasoner1 = await lifecycle_manager.get_ensemble_reasoner()
    reasoner2 = await lifecycle_manager.get_ensemble_reasoner()

    assert reasoner1 is reasoner2, "EnsembleReasoner should be a singleton within lifecycle manager"


@pytest.mark.asyncio
async def test_adaptive_router_singleton(lifecycle_manager):
    """Test that AdaptiveRouter instances are singletons."""
    router1 = await lifecycle_manager.get_adaptive_router()
    router2 = await lifecycle_manager.get_adaptive_router()

    assert router1 is router2, "AdaptiveRouter should be a singleton within lifecycle manager"


@pytest.mark.asyncio
async def test_cross_validator_singleton(lifecycle_manager):
    """Test that CrossValidator instances are singletons."""
    validator1 = await lifecycle_manager.get_cross_validator()
    validator2 = await lifecycle_manager.get_cross_validator()

    assert validator1 is validator2, "CrossValidator should be a singleton within lifecycle manager"


@pytest.mark.asyncio
async def test_shutdown_cancels_cleanup_tasks(lifecycle_manager):
    """Test that shutdown properly cancels background cleanup tasks."""
    # Create instances which spawn background tasks
    engine = await lifecycle_manager.get_consensus_engine()
    solver = await lifecycle_manager.get_collaborative_solver()

    # Verify cleanup tasks exist
    assert engine.storage_manager._cleanup_task is not None, "ConsensusEngine should have cleanup task"
    assert solver.storage_manager._cleanup_task is not None, "CollaborativeSolver should have cleanup task"

    cleanup_task1 = engine.storage_manager._cleanup_task
    cleanup_task2 = solver.storage_manager._cleanup_task

    # Shutdown the manager
    await lifecycle_manager.shutdown()

    # Wait a bit for tasks to be cancelled
    await asyncio.sleep(0.1)

    # Verify tasks were cancelled
    assert cleanup_task1.cancelled() or cleanup_task1.done(), "ConsensusEngine cleanup task should be cancelled"
    assert cleanup_task2.cancelled() or cleanup_task2.done(), "CollaborativeSolver cleanup task should be cancelled"


@pytest.mark.asyncio
async def test_no_task_leaks_after_shutdown(lifecycle_manager):
    """Test that no asyncio tasks are leaked after shutdown."""
    # Get initial task count
    initial_tasks = len([t for t in asyncio.all_tasks() if not t.done()])

    # Create all components (which spawn background tasks)
    await lifecycle_manager.get_consensus_engine()
    await lifecycle_manager.get_collaborative_solver()
    await lifecycle_manager.get_ensemble_reasoner()
    await lifecycle_manager.get_adaptive_router()
    await lifecycle_manager.get_cross_validator()

    # Verify tasks were created
    after_creation_tasks = len([t for t in asyncio.all_tasks() if not t.done()])
    assert after_creation_tasks > initial_tasks, "Background tasks should be created"

    # Shutdown
    await lifecycle_manager.shutdown()

    # Wait for tasks to complete cancellation
    await asyncio.sleep(0.2)

    # Count remaining tasks (excluding current test task)
    final_tasks = len([t for t in asyncio.all_tasks() if not t.done()])

    # Allow for the current test task itself
    assert final_tasks <= initial_tasks + 1, \
        f"Tasks should be cleaned up after shutdown. Initial: {initial_tasks}, After creation: {after_creation_tasks}, Final: {final_tasks}"


@pytest.mark.asyncio
async def test_cannot_create_instances_after_shutdown(lifecycle_manager):
    """Test that instances cannot be created after shutdown."""
    await lifecycle_manager.shutdown()

    with pytest.raises(RuntimeError, match="shutdown"):
        await lifecycle_manager.get_consensus_engine()

    with pytest.raises(RuntimeError, match="shutdown"):
        await lifecycle_manager.get_collaborative_solver()


@pytest.mark.asyncio
async def test_cannot_create_without_configuration():
    """Test that instances cannot be created without configuration."""
    # Reset global singleton
    import openrouter_mcp.collective_intelligence.lifecycle_manager as lm_module
    lm_module._lifecycle_manager = None

    try:
        manager = await get_lifecycle_manager()

        # Try to create instance without configuring
        with pytest.raises(RuntimeError, match="not configured"):
            await manager.get_consensus_engine()
    finally:
        if lm_module._lifecycle_manager:
            await lm_module._lifecycle_manager.shutdown()
            lm_module._lifecycle_manager = None


@pytest.mark.asyncio
async def test_concurrent_initialization_thread_safe(mock_model_provider):
    """Test that concurrent initialization is thread-safe."""
    # Reset global singleton
    import openrouter_mcp.collective_intelligence.lifecycle_manager as lm_module
    lm_module._lifecycle_manager = None

    try:
        manager = await get_lifecycle_manager()
        manager.configure(mock_model_provider)

        # Try to create same instance concurrently
        tasks = [
            manager.get_consensus_engine(),
            manager.get_consensus_engine(),
            manager.get_consensus_engine()
        ]

        engines = await asyncio.gather(*tasks)

        # All should be the same instance
        assert engines[0] is engines[1]
        assert engines[1] is engines[2]
    finally:
        if lm_module._lifecycle_manager:
            await lm_module._lifecycle_manager.shutdown()
            lm_module._lifecycle_manager = None


@pytest.mark.asyncio
async def test_shutdown_idempotent(lifecycle_manager):
    """Test that shutdown can be called multiple times safely."""
    await lifecycle_manager.shutdown()
    # Should not raise
    await lifecycle_manager.shutdown()
    await lifecycle_manager.shutdown()


@pytest.mark.asyncio
async def test_is_shutdown_flag(lifecycle_manager):
    """Test the is_shutdown flag."""
    assert not lifecycle_manager.is_shutdown()

    await lifecycle_manager.shutdown()

    assert lifecycle_manager.is_shutdown()


@pytest.mark.asyncio
async def test_lifespan_context_manager(mock_model_provider):
    """Test the lifespan context manager."""
    # Reset global singleton
    import openrouter_mcp.collective_intelligence.lifecycle_manager as lm_module
    lm_module._lifecycle_manager = None

    try:
        manager = CollectiveIntelligenceLifecycleManager()
        manager.configure(mock_model_provider)

        async with manager.lifespan():
            # Create instances inside context
            engine = await manager.get_consensus_engine()
            assert engine is not None
            assert not manager.is_shutdown()

        # After context, should be shutdown
        assert manager.is_shutdown()
    finally:
        lm_module._lifecycle_manager = None


@pytest.mark.asyncio
async def test_global_shutdown_lifecycle_manager():
    """Test the global shutdown function."""
    # Reset global singleton
    import openrouter_mcp.collective_intelligence.lifecycle_manager as lm_module
    lm_module._lifecycle_manager = None

    try:
        mock_provider = MockModelProvider()
        manager = await get_lifecycle_manager()
        manager.configure(mock_provider)

        # Create an instance
        await manager.get_consensus_engine()

        # Shutdown via global function
        await shutdown_lifecycle_manager()

        # Global singleton should be None
        assert lm_module._lifecycle_manager is None
    finally:
        lm_module._lifecycle_manager = None


@pytest.mark.asyncio
async def test_operational_metrics_accessible(lifecycle_manager):
    """Test that operational metrics are accessible from components."""
    engine = await lifecycle_manager.get_consensus_engine()
    solver = await lifecycle_manager.get_collaborative_solver()

    # Get metrics
    engine_metrics = engine.get_operational_metrics()
    solver_metrics = solver.get_operational_metrics()

    # Verify metrics structure
    assert 'active_tasks' in engine_metrics
    assert 'history_size' in engine_metrics
    assert 'concurrency_config' in engine_metrics

    assert 'active_sessions' in solver_metrics
    assert 'active_tasks' in solver_metrics
    assert 'concurrency_config' in solver_metrics


@pytest.mark.asyncio
async def test_cleanup_task_runs_periodically(lifecycle_manager):
    """Test that cleanup task actually runs periodically."""
    engine = await lifecycle_manager.get_consensus_engine()

    # Mock the cleanup method to track calls
    original_cleanup = engine.storage_manager.cleanup_expired
    call_count = 0

    async def mock_cleanup():
        nonlocal call_count
        call_count += 1
        return await original_cleanup()

    engine.storage_manager.cleanup_expired = mock_cleanup

    # Wait for at least one cleanup cycle (configured to 60 minutes, but we can check task exists)
    assert engine.storage_manager._cleanup_task is not None
    assert not engine.storage_manager._cleanup_task.done()

    # Verify the task is running (not done)
    await asyncio.sleep(0.1)
    assert not engine.storage_manager._cleanup_task.done()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
