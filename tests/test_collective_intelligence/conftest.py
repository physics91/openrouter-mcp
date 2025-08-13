"""
Pytest configuration and fixtures for collective intelligence tests.

This module provides shared fixtures and test utilities for all CI component tests.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock

import pytest

from src.openrouter_mcp.collective_intelligence.base import (
    ModelInfo, TaskContext, ProcessingResult, ModelProvider,
    TaskType, ModelCapability
)
from src.openrouter_mcp.collective_intelligence.consensus_engine import (
    ConsensusConfig, ConsensusStrategy
)


@pytest.fixture
def sample_models() -> List[ModelInfo]:
    """Fixture providing sample model information for testing."""
    return [
        ModelInfo(
            model_id="openai/gpt-4",
            name="GPT-4",
            provider="OpenAI",
            capabilities={
                ModelCapability.REASONING: 0.9,
                ModelCapability.ACCURACY: 0.85,
                ModelCapability.CREATIVITY: 0.8
            },
            context_length=8192,
            cost_per_token=0.00003,
            response_time_avg=2.5,
            accuracy_score=0.85,
            availability=0.95
        ),
        ModelInfo(
            model_id="anthropic/claude-3-haiku",
            name="Claude 3 Haiku",
            provider="Anthropic",
            capabilities={
                ModelCapability.REASONING: 0.85,
                ModelCapability.SPEED: 0.95,
                ModelCapability.ACCURACY: 0.8
            },
            context_length=200000,
            cost_per_token=0.00025,
            response_time_avg=1.2,
            accuracy_score=0.8,
            availability=0.98
        ),
        ModelInfo(
            model_id="meta-llama/llama-3.1-70b",
            name="Llama 3.1 70B",
            provider="Meta",
            capabilities={
                ModelCapability.REASONING: 0.8,
                ModelCapability.CREATIVITY: 0.85,
                ModelCapability.CODE: 0.9
            },
            context_length=131072,
            cost_per_token=0.00015,
            response_time_avg=3.1,
            accuracy_score=0.78,
            availability=0.92
        ),
        ModelInfo(
            model_id="google/gemini-pro",
            name="Gemini Pro",
            provider="Google",
            capabilities={
                ModelCapability.REASONING: 0.82,
                ModelCapability.MULTIMODAL: 0.9,
                ModelCapability.ACCURACY: 0.83
            },
            context_length=32768,
            cost_per_token=0.0002,
            response_time_avg=2.8,
            accuracy_score=0.83,
            availability=0.94
        ),
        ModelInfo(
            model_id="mistralai/mixtral-8x7b",
            name="Mixtral 8x7B",
            provider="Mistral",
            capabilities={
                ModelCapability.SPEED: 0.88,
                ModelCapability.CODE: 0.85,
                ModelCapability.REASONING: 0.75
            },
            context_length=32768,
            cost_per_token=0.0001,
            response_time_avg=1.8,
            accuracy_score=0.75,
            availability=0.96
        )
    ]


@pytest.fixture
def sample_task() -> TaskContext:
    """Fixture providing a sample task for testing."""
    return TaskContext(
        task_id="test_task_001",
        task_type=TaskType.REASONING,
        content="What are the main advantages and disadvantages of renewable energy sources?",
        requirements={"detail_level": "comprehensive", "include_examples": True},
        constraints={"max_tokens": 1000, "response_time": 30},
        priority=7,
        deadline=datetime.now() + timedelta(hours=1)
    )


@pytest.fixture
def sample_processing_results(sample_models: List[ModelInfo]) -> List[ProcessingResult]:
    """Fixture providing sample processing results from different models."""
    return [
        ProcessingResult(
            task_id="test_task_001",
            model_id="openai/gpt-4",
            content="Renewable energy sources offer significant environmental benefits...",
            confidence=0.88,
            processing_time=2.3,
            tokens_used=250,
            cost=0.0075,
            metadata={"temperature": 0.7}
        ),
        ProcessingResult(
            task_id="test_task_001",
            model_id="anthropic/claude-3-haiku",
            content="The advantages of renewable energy include sustainability...",
            confidence=0.82,
            processing_time=1.1,
            tokens_used=220,
            cost=0.0055,
            metadata={"temperature": 0.7}
        ),
        ProcessingResult(
            task_id="test_task_001",
            model_id="meta-llama/llama-3.1-70b",
            content="Renewable energy technologies present both opportunities...",
            confidence=0.75,
            processing_time=2.8,
            tokens_used=280,
            cost=0.0042,
            metadata={"temperature": 0.7}
        ),
        ProcessingResult(
            task_id="test_task_001",
            model_id="google/gemini-pro",
            content="The transition to renewable energy sources involves...",
            confidence=0.79,
            processing_time=2.5,
            tokens_used=240,
            cost=0.0048,
            metadata={"temperature": 0.7}
        )
    ]


@pytest.fixture
def mock_model_provider(
    sample_models: List[ModelInfo], 
    sample_processing_results: List[ProcessingResult]
) -> ModelProvider:
    """Mock model provider for testing."""
    provider = AsyncMock(spec=ModelProvider)
    
    # Configure mock methods
    provider.get_available_models.return_value = sample_models
    
    # Create a mapping of model_id to result for process_task
    result_map = {result.model_id: result for result in sample_processing_results}
    
    async def mock_process_task(task: TaskContext, model_id: str, **kwargs) -> ProcessingResult:
        if model_id in result_map:
            result = result_map[model_id]
            # Update task_id to match the input task
            result.task_id = task.task_id
            return result
        else:
            raise ValueError(f"Model {model_id} not found in mock results")
    
    provider.process_task.side_effect = mock_process_task
    
    return provider


@pytest.fixture
def consensus_config() -> ConsensusConfig:
    """Standard consensus configuration for testing."""
    return ConsensusConfig(
        strategy=ConsensusStrategy.MAJORITY_VOTE,
        min_models=3,
        max_models=5,
        confidence_threshold=0.7,
        agreement_threshold=0.6,
        timeout_seconds=10.0,
        retry_attempts=1,
        model_weights={
            "openai/gpt-4": 1.2,
            "anthropic/claude-3-haiku": 1.0,
            "meta-llama/llama-3.1-70b": 0.9
        }
    )


@pytest.fixture
def consensus_config_weighted() -> ConsensusConfig:
    """Weighted average consensus configuration for testing."""
    return ConsensusConfig(
        strategy=ConsensusStrategy.WEIGHTED_AVERAGE,
        min_models=3,
        max_models=4,
        confidence_threshold=0.75,
        agreement_threshold=0.7,
        timeout_seconds=15.0,
        model_weights={
            "openai/gpt-4": 1.5,
            "anthropic/claude-3-haiku": 1.0,
            "google/gemini-pro": 1.1
        }
    )


@pytest.fixture
def consensus_config_confidence() -> ConsensusConfig:
    """Confidence threshold consensus configuration for testing."""
    return ConsensusConfig(
        strategy=ConsensusStrategy.CONFIDENCE_THRESHOLD,
        min_models=2,
        max_models=5,
        confidence_threshold=0.8,
        agreement_threshold=0.5,
        timeout_seconds=20.0
    )


@pytest.fixture
def failing_model_provider() -> ModelProvider:
    """Mock model provider that simulates failures for testing error handling."""
    provider = AsyncMock(spec=ModelProvider)
    
    provider.get_available_models.return_value = []
    
    async def mock_failing_process_task(task: TaskContext, model_id: str, **kwargs):
        if model_id == "failing_model":
            raise asyncio.TimeoutError("Model timeout")
        elif model_id == "error_model":
            raise ValueError("Invalid request")
        else:
            raise Exception("Unexpected error")
    
    provider.process_task.side_effect = mock_failing_process_task
    
    return provider


@pytest.fixture
def performance_test_models() -> List[ModelInfo]:
    """Large set of models for performance testing."""
    models = []
    for i in range(10):
        models.append(
            ModelInfo(
                model_id=f"test_model_{i}",
                name=f"Test Model {i}",
                provider=f"Provider {i % 3}",
                capabilities={
                    ModelCapability.REASONING: 0.5 + (i * 0.05),
                    ModelCapability.SPEED: 0.6 + (i * 0.04)
                },
                context_length=4096 * (i + 1),
                cost_per_token=0.0001 * (i + 1),
                response_time_avg=1.0 + (i * 0.2),
                accuracy_score=0.7 + (i * 0.03),
                availability=0.9 + (i * 0.01)
            )
        )
    return models


@pytest.fixture
def performance_mock_provider(performance_test_models: List[ModelInfo]) -> ModelProvider:
    """Mock provider for performance testing with many models."""
    provider = AsyncMock(spec=ModelProvider)
    provider.get_available_models.return_value = performance_test_models
    
    async def mock_process_task(task: TaskContext, model_id: str, **kwargs) -> ProcessingResult:
        # Simulate varying processing times and results
        model_index = int(model_id.split('_')[-1])
        processing_time = 1.0 + (model_index * 0.1)
        confidence = 0.6 + (model_index * 0.04)
        
        # Simulate async processing time
        await asyncio.sleep(0.01)  # Small delay to simulate real processing
        
        return ProcessingResult(
            task_id=task.task_id,
            model_id=model_id,
            content=f"Response from {model_id}: This is a test response with varying quality.",
            confidence=confidence,
            processing_time=processing_time,
            tokens_used=100 + (model_index * 10),
            cost=0.001 + (model_index * 0.0001)
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