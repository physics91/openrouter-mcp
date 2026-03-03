"""
Pytest configuration and fixtures for collective intelligence tests.

This module provides shared fixtures and test utilities for all CI component tests.
"""

import asyncio
from typing import List
from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.collective_intelligence.base import (
    ModelCapability,
    ModelInfo,
    ModelProvider,
    ProcessingResult,
    TaskContext,
    TaskType,
)
from src.openrouter_mcp.collective_intelligence.consensus_engine import (
    ConsensusConfig,
    ConsensusStrategy,
)
from tests.fixtures.ci_compact import (
    build_consensus_config,
    build_generated_models,
    build_processing_results,
    build_sample_models,
    build_sample_task,
)


@pytest.fixture
def sample_models() -> List[ModelInfo]:
    """Fixture providing sample model information for testing."""
    return build_sample_models(ModelInfo, ModelCapability)


@pytest.fixture
def sample_task() -> TaskContext:
    """Fixture providing a sample task for testing."""
    return build_sample_task(TaskContext, TaskType)


@pytest.fixture
def sample_processing_results(sample_models: List[ModelInfo]) -> List[ProcessingResult]:
    """Fixture providing sample processing results from different models."""
    return build_processing_results(ProcessingResult, sample_models)


@pytest.fixture
def mock_model_provider(
    sample_models: List[ModelInfo], sample_processing_results: List[ProcessingResult]
) -> ModelProvider:
    """Mock model provider for testing."""
    provider = AsyncMock(spec=ModelProvider)
    provider.get_available_models.return_value = sample_models

    result_map = {result.model_id: result for result in sample_processing_results}

    async def mock_process_task(
        task: TaskContext, model_id: str, **kwargs
    ) -> ProcessingResult:
        if model_id in result_map:
            result = result_map[model_id]
            result.task_id = task.task_id
            return result
        raise ValueError(f"Model {model_id} not found in mock results")

    provider.process_task.side_effect = mock_process_task
    return provider


@pytest.fixture
def consensus_config() -> ConsensusConfig:
    """Standard consensus configuration for testing."""
    return build_consensus_config(
        ConsensusConfig,
        ConsensusStrategy,
        "majority_vote",
    )


@pytest.fixture
def consensus_config_weighted() -> ConsensusConfig:
    """Weighted average consensus configuration for testing."""
    return build_consensus_config(
        ConsensusConfig,
        ConsensusStrategy,
        "weighted_average",
    )


@pytest.fixture
def consensus_config_confidence() -> ConsensusConfig:
    """Confidence threshold consensus configuration for testing."""
    return build_consensus_config(
        ConsensusConfig,
        ConsensusStrategy,
        "confidence_threshold",
    )


@pytest.fixture
def failing_model_provider() -> ModelProvider:
    """Mock model provider that simulates failures for testing error handling."""
    provider = AsyncMock(spec=ModelProvider)
    provider.get_available_models.return_value = []

    async def mock_failing_process_task(task: TaskContext, model_id: str, **kwargs):
        if model_id == "failing_model":
            raise asyncio.TimeoutError("Model timeout")
        if model_id == "error_model":
            raise ValueError("Invalid request")
        raise Exception("Unexpected error")

    provider.process_task.side_effect = mock_failing_process_task
    return provider


@pytest.fixture
def performance_test_models() -> List[ModelInfo]:
    """Large set of models for performance testing."""
    return build_generated_models(ModelInfo, ModelCapability, count=10)


@pytest.fixture
def performance_mock_provider(
    performance_test_models: List[ModelInfo],
) -> ModelProvider:
    """Mock provider for performance testing with many models."""
    provider = AsyncMock(spec=ModelProvider)
    provider.get_available_models.return_value = performance_test_models

    async def mock_process_task(
        task: TaskContext, model_id: str, **kwargs
    ) -> ProcessingResult:
        model_index = int(model_id.split("_")[-1])
        processing_time = 1.0 + (model_index * 0.1)
        confidence = 0.6 + (model_index * 0.04)

        await asyncio.sleep(0.01)

        return ProcessingResult(
            task_id=task.task_id,
            model_id=model_id,
            content=f"Response from {model_id}: This is a test response with varying quality.",
            confidence=confidence,
            processing_time=processing_time,
            tokens_used=100 + (model_index * 10),
            cost=0.001 + (model_index * 0.0001),
        )

    provider.process_task.side_effect = mock_process_task
    return provider


class MockAsyncContext:
    """Helper class for mocking async context managers."""

    def __init__(self, return_value=None):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_async_context():
    """Factory for creating mock async context managers."""
    return MockAsyncContext
