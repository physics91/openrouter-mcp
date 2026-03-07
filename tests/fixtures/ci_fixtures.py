"""
Collective Intelligence specific test fixtures.

This module provides fixtures and factories specifically for testing
collective intelligence components like ConsensusEngine, EnsembleReasoner,
AdaptiveRouter, etc.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from unittest.mock import AsyncMock

from openrouter_mcp.collective_intelligence.base import (
    ModelCapability,
    ModelInfo,
    ModelProvider,
    ProcessingResult,
    TaskContext,
    TaskType,
)
from openrouter_mcp.collective_intelligence.consensus_engine import (
    ConsensusConfig,
    ConsensusStrategy,
)
from openrouter_mcp.collective_intelligence.operational_controls import (
    ConcurrencyConfig,
    FailureConfig,
    OperationalConfig,
    QuotaConfig,
    StorageConfig,
)


def create_sample_models(count: int = 5) -> List[ModelInfo]:
    """
    Create a list of sample models for testing.

    Args:
        count: Number of models to create (max 5 for pre-defined, otherwise generated)

    Returns:
        List of ModelInfo instances
    """
    predefined_models = [
        ModelInfo(
            model_id="openai/gpt-4",
            name="GPT-4",
            provider="OpenAI",
            capabilities={
                ModelCapability.REASONING: 0.9,
                ModelCapability.ACCURACY: 0.85,
                ModelCapability.CREATIVITY: 0.8,
            },
            context_length=8192,
            cost_per_token=0.00003,
            response_time_avg=2.5,
            accuracy_score=0.85,
            availability=0.95,
        ),
        ModelInfo(
            model_id="anthropic/claude-3-haiku",
            name="Claude 3 Haiku",
            provider="Anthropic",
            capabilities={
                ModelCapability.REASONING: 0.85,
                ModelCapability.SPEED: 0.95,
                ModelCapability.ACCURACY: 0.8,
            },
            context_length=200000,
            cost_per_token=0.00025,
            response_time_avg=1.2,
            accuracy_score=0.8,
            availability=0.98,
        ),
        ModelInfo(
            model_id="meta-llama/llama-3.1-70b",
            name="Llama 3.1 70B",
            provider="Meta",
            capabilities={
                ModelCapability.REASONING: 0.8,
                ModelCapability.CREATIVITY: 0.85,
                ModelCapability.CODE: 0.9,
            },
            context_length=131072,
            cost_per_token=0.00015,
            response_time_avg=3.1,
            accuracy_score=0.78,
            availability=0.92,
        ),
        ModelInfo(
            model_id="google/gemini-pro",
            name="Gemini Pro",
            provider="Google",
            capabilities={
                ModelCapability.REASONING: 0.82,
                ModelCapability.MULTIMODAL: 0.9,
                ModelCapability.ACCURACY: 0.83,
            },
            context_length=32768,
            cost_per_token=0.0002,
            response_time_avg=2.8,
            accuracy_score=0.83,
            availability=0.94,
        ),
        ModelInfo(
            model_id="mistralai/mixtral-8x7b",
            name="Mixtral 8x7B",
            provider="Mistral",
            capabilities={
                ModelCapability.SPEED: 0.88,
                ModelCapability.CODE: 0.85,
                ModelCapability.REASONING: 0.75,
            },
            context_length=32768,
            cost_per_token=0.0001,
            response_time_avg=1.8,
            accuracy_score=0.75,
            availability=0.96,
        ),
    ]

    if count <= len(predefined_models):
        return predefined_models[:count]

    # Generate additional models if needed
    models = predefined_models.copy()
    for i in range(len(predefined_models), count):
        models.append(
            ModelInfo(
                model_id=f"test_model_{i}",
                name=f"Test Model {i}",
                provider=f"Provider {i % 3}",
                capabilities={
                    ModelCapability.REASONING: 0.5 + (i * 0.05),
                    ModelCapability.SPEED: 0.6 + (i * 0.04),
                },
                context_length=4096 * (i + 1),
                cost_per_token=0.0001 * (i + 1),
                response_time_avg=1.0 + (i * 0.2),
                accuracy_score=0.7 + (i * 0.03),
                availability=0.9 + (i * 0.01),
            )
        )
    return models


def create_sample_task(
    task_id: str = "test_task_001",
    task_type: TaskType = TaskType.REASONING,
    content: str = "What are the main advantages and disadvantages of renewable energy sources?",
    priority: int = 7,
    deadline_hours: float = 1.0,
) -> TaskContext:
    """
    Create a sample task for testing.

    Args:
        task_id: Unique task identifier
        task_type: Type of task
        content: Task content/prompt
        priority: Task priority (1-10)
        deadline_hours: Hours from now until deadline

    Returns:
        TaskContext instance
    """
    return TaskContext(
        task_id=task_id,
        task_type=task_type,
        content=content,
        requirements={"detail_level": "comprehensive", "include_examples": True},
        constraints={"max_tokens": 1000, "response_time": 30},
        priority=priority,
        deadline=datetime.now() + timedelta(hours=deadline_hours),
    )


def create_processing_results(
    task_id: str = "test_task_001",
    models: Optional[List[ModelInfo]] = None,
) -> List[ProcessingResult]:
    """
    Create sample processing results for testing.

    Args:
        task_id: Task ID to associate with results
        models: Optional list of models, uses defaults if not provided

    Returns:
        List of ProcessingResult instances
    """
    if models is None:
        models = create_sample_models(4)

    results_data = [
        {
            "model_id": "openai/gpt-4",
            "content": "Renewable energy sources offer significant environmental benefits...",
            "confidence": 0.88,
            "processing_time": 2.3,
            "tokens_used": 250,
            "cost": 0.0075,
        },
        {
            "model_id": "anthropic/claude-3-haiku",
            "content": "The advantages of renewable energy include sustainability...",
            "confidence": 0.82,
            "processing_time": 1.1,
            "tokens_used": 220,
            "cost": 0.0055,
        },
        {
            "model_id": "meta-llama/llama-3.1-70b",
            "content": "Renewable energy technologies present both opportunities...",
            "confidence": 0.75,
            "processing_time": 2.8,
            "tokens_used": 280,
            "cost": 0.0042,
        },
        {
            "model_id": "google/gemini-pro",
            "content": "The transition to renewable energy sources involves...",
            "confidence": 0.79,
            "processing_time": 2.5,
            "tokens_used": 240,
            "cost": 0.0048,
        },
    ]

    model_ids = {m.model_id for m in models}
    return [
        ProcessingResult(
            task_id=task_id,
            model_id=data["model_id"],
            content=data["content"],
            confidence=data["confidence"],
            processing_time=data["processing_time"],
            tokens_used=data["tokens_used"],
            cost=data["cost"],
            metadata={"temperature": 0.7},
        )
        for data in results_data
        if data["model_id"] in model_ids
    ]


class MockModelProviderFactory:
    """
    Factory for creating mock ModelProvider instances with various behaviors.
    """

    @staticmethod
    def standard(
        models: Optional[List[ModelInfo]] = None,
        results: Optional[List[ProcessingResult]] = None,
    ) -> AsyncMock:
        """
        Create a standard mock provider with configurable responses.

        Args:
            models: Models to return from get_available_models
            results: Results to return from process_task

        Returns:
            Configured AsyncMock ModelProvider
        """
        provider = AsyncMock(spec=ModelProvider)

        if models is None:
            models = create_sample_models()
        provider.get_available_models.return_value = models

        if results is None:
            results = create_processing_results()

        result_map = {r.model_id: r for r in results}

        async def mock_process_task(task, model_id, **kwargs):
            if model_id in result_map:
                result = result_map[model_id]
                result.task_id = task.task_id
                return result
            raise ValueError(f"Model {model_id} not found")

        provider.process_task.side_effect = mock_process_task
        return provider

    @staticmethod
    def failing(
        timeout_models: Optional[List[str]] = None,
        error_models: Optional[List[str]] = None,
    ) -> AsyncMock:
        """
        Create a mock provider that simulates failures.

        Args:
            timeout_models: Model IDs that should timeout
            error_models: Model IDs that should raise errors

        Returns:
            Configured AsyncMock ModelProvider that fails
        """
        provider = AsyncMock(spec=ModelProvider)
        provider.get_available_models.return_value = []

        timeout_models = timeout_models or ["timeout_model"]
        error_models = error_models or ["error_model"]

        async def mock_failing_process(task, model_id, **kwargs):
            if model_id in timeout_models:
                raise asyncio.TimeoutError("Model timeout")
            elif model_id in error_models:
                raise ValueError("Invalid request")
            raise Exception("Unexpected error")

        provider.process_task.side_effect = mock_failing_process
        return provider

    @staticmethod
    def performance(model_count: int = 10) -> AsyncMock:
        """
        Create a mock provider for performance testing.

        Args:
            model_count: Number of models to simulate

        Returns:
            Configured AsyncMock ModelProvider
        """
        provider = AsyncMock(spec=ModelProvider)
        models = create_sample_models(model_count)
        provider.get_available_models.return_value = models

        async def mock_process_task(task, model_id, **kwargs):
            # Extract model index for varying responses
            try:
                model_index = int(model_id.split("_")[-1])
            except (ValueError, IndexError):
                model_index = 0

            processing_time = 1.0 + (model_index * 0.1)
            confidence = 0.6 + (model_index * 0.04)

            await asyncio.sleep(0.01)  # Simulate processing

            return ProcessingResult(
                task_id=task.task_id,
                model_id=model_id,
                content=f"Response from {model_id}: Test response.",
                confidence=min(confidence, 0.99),
                processing_time=processing_time,
                tokens_used=100 + (model_index * 10),
                cost=0.001 + (model_index * 0.0001),
            )

        provider.process_task.side_effect = mock_process_task
        return provider


class ConsensusConfigFactory:
    """Factory for creating ConsensusConfig instances."""

    @staticmethod
    def majority_vote() -> ConsensusConfig:
        """Create standard majority vote config."""
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
                "meta-llama/llama-3.1-70b": 0.9,
            },
        )

    @staticmethod
    def weighted_average() -> ConsensusConfig:
        """Create weighted average config."""
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
                "google/gemini-pro": 1.1,
            },
        )

    @staticmethod
    def confidence_threshold() -> ConsensusConfig:
        """Create confidence threshold config."""
        return ConsensusConfig(
            strategy=ConsensusStrategy.CONFIDENCE_THRESHOLD,
            min_models=2,
            max_models=5,
            confidence_threshold=0.8,
            agreement_threshold=0.5,
            timeout_seconds=20.0,
        )


class OperationalConfigFactory:
    """Factory for creating OperationalConfig instances for testing."""

    @staticmethod
    def conservative() -> OperationalConfig:
        """Create conservative config for production-like testing."""
        return OperationalConfig.conservative()

    @staticmethod
    def aggressive() -> OperationalConfig:
        """Create aggressive config for high-volume testing."""
        return OperationalConfig.aggressive()

    @staticmethod
    def test_minimal() -> OperationalConfig:
        """Create minimal config for fast unit tests."""
        return OperationalConfig(
            concurrency=ConcurrencyConfig(
                max_concurrent_tasks=2,
                max_concurrent_models=2,
                max_pending_tasks=10,
                queue_timeout_seconds=5.0,
            ),
            quota=QuotaConfig(
                max_api_calls_per_request=5,
                max_api_calls_per_minute=20,
                max_api_calls_per_hour=100,
                max_tokens_per_request=10000,
                max_cost_per_request=0.1,
            ),
            storage=StorageConfig(
                max_history_size=100,
                history_ttl_hours=1,
                enable_auto_cleanup=False,
            ),
            failure=FailureConfig(
                cancel_on_first_failure=False,
                max_failures_before_cancel=2,
                retry_failed_tasks=False,
            ),
            enable_monitoring=False,
            enable_alerting=False,
        )


__all__ = [
    "create_sample_models",
    "create_sample_task",
    "create_processing_results",
    "MockModelProviderFactory",
    "ConsensusConfigFactory",
    "OperationalConfigFactory",
]
