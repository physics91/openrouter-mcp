"""Compact data builders for collective-intelligence test fixtures."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Sequence, Type

# Compact tuple format to avoid repeating verbose object construction in multiple files.
# (model_id, name, provider, capabilities, context, cost, latency, accuracy, availability)
_MODEL_ROWS: Sequence[
    tuple[str, str, str, Dict[str, float], int, float, float, float, float]
] = (
    (
        "openai/gpt-4",
        "GPT-4",
        "OpenAI",
        {"REASONING": 0.9, "ACCURACY": 0.85, "CREATIVITY": 0.8},
        8192,
        0.00003,
        2.5,
        0.85,
        0.95,
    ),
    (
        "anthropic/claude-3-haiku",
        "Claude 3 Haiku",
        "Anthropic",
        {"REASONING": 0.85, "SPEED": 0.95, "ACCURACY": 0.8},
        200000,
        0.00025,
        1.2,
        0.8,
        0.98,
    ),
    (
        "meta-llama/llama-3.1-70b",
        "Llama 3.1 70B",
        "Meta",
        {"REASONING": 0.8, "CREATIVITY": 0.85, "CODE": 0.9},
        131072,
        0.00015,
        3.1,
        0.78,
        0.92,
    ),
    (
        "google/gemini-pro",
        "Gemini Pro",
        "Google",
        {"REASONING": 0.82, "MULTIMODAL": 0.9, "ACCURACY": 0.83},
        32768,
        0.0002,
        2.8,
        0.83,
        0.94,
    ),
    (
        "mistralai/mixtral-8x7b",
        "Mixtral 8x7B",
        "Mistral",
        {"SPEED": 0.88, "CODE": 0.85, "REASONING": 0.75},
        32768,
        0.0001,
        1.8,
        0.75,
        0.96,
    ),
)

# (model_id, content, confidence, processing_time, tokens_used, cost)
_RESULT_ROWS: Sequence[tuple[str, str, float, float, int, float]] = (
    (
        "openai/gpt-4",
        "Renewable energy sources offer significant environmental benefits...",
        0.88,
        2.3,
        250,
        0.0075,
    ),
    (
        "anthropic/claude-3-haiku",
        "The advantages of renewable energy include sustainability...",
        0.82,
        1.1,
        220,
        0.0055,
    ),
    (
        "meta-llama/llama-3.1-70b",
        "Renewable energy technologies present both opportunities...",
        0.75,
        2.8,
        280,
        0.0042,
    ),
    (
        "google/gemini-pro",
        "The transition to renewable energy sources involves...",
        0.79,
        2.5,
        240,
        0.0048,
    ),
)

# (strategy_name, min_models, max_models, confidence, agreement, timeout, retry, weights)
_CONSENSUS_ROWS: Dict[
    str,
    tuple[str, int, int, float, float, float, int | None, Dict[str, float] | None],
] = {
    "majority_vote": (
        "MAJORITY_VOTE",
        3,
        5,
        0.7,
        0.6,
        10.0,
        1,
        {
            "openai/gpt-4": 1.2,
            "anthropic/claude-3-haiku": 1.0,
            "meta-llama/llama-3.1-70b": 0.9,
        },
    ),
    "weighted_average": (
        "WEIGHTED_AVERAGE",
        3,
        4,
        0.75,
        0.7,
        15.0,
        None,
        {
            "openai/gpt-4": 1.5,
            "anthropic/claude-3-haiku": 1.0,
            "google/gemini-pro": 1.1,
        },
    ),
    "confidence_threshold": (
        "CONFIDENCE_THRESHOLD",
        2,
        5,
        0.8,
        0.5,
        20.0,
        None,
        None,
    ),
}


def build_sample_models(
    model_info_cls: Type[Any], capability_enum: Type[Any], count: int = 5
) -> List[Any]:
    """Build deterministic ModelInfo-style objects with the target enum/class types."""
    models: List[Any] = []
    for row in _MODEL_ROWS[: min(count, len(_MODEL_ROWS))]:
        (
            model_id,
            name,
            provider,
            capabilities,
            context_length,
            cost_per_token,
            response_time_avg,
            accuracy_score,
            availability,
        ) = row
        models.append(
            model_info_cls(
                model_id=model_id,
                name=name,
                provider=provider,
                capabilities={
                    capability_enum[cap_name]: value
                    for cap_name, value in capabilities.items()
                },
                context_length=context_length,
                cost_per_token=cost_per_token,
                response_time_avg=response_time_avg,
                accuracy_score=accuracy_score,
                availability=availability,
            )
        )

    for i in range(len(_MODEL_ROWS), count):
        models.append(
            model_info_cls(
                model_id=f"test_model_{i}",
                name=f"Test Model {i}",
                provider=f"Provider {i % 3}",
                capabilities={
                    capability_enum.REASONING: 0.5 + (i * 0.05),
                    capability_enum.SPEED: 0.6 + (i * 0.04),
                },
                context_length=4096 * (i + 1),
                cost_per_token=0.0001 * (i + 1),
                response_time_avg=1.0 + (i * 0.2),
                accuracy_score=0.7 + (i * 0.03),
                availability=0.9 + (i * 0.01),
            )
        )

    return models


def build_generated_models(
    model_info_cls: Type[Any],
    capability_enum: Type[Any],
    *,
    count: int,
    start_index: int = 0,
) -> List[Any]:
    """Build synthetic ``test_model_<n>`` objects used by performance fixtures."""
    return [
        model_info_cls(
            model_id=f"test_model_{i}",
            name=f"Test Model {i}",
            provider=f"Provider {i % 3}",
            capabilities={
                capability_enum.REASONING: 0.5 + (i * 0.05),
                capability_enum.SPEED: 0.6 + (i * 0.04),
            },
            context_length=4096 * (i + 1),
            cost_per_token=0.0001 * (i + 1),
            response_time_avg=1.0 + (i * 0.2),
            accuracy_score=0.7 + (i * 0.03),
            availability=0.9 + (i * 0.01),
        )
        for i in range(start_index, start_index + count)
    ]


def build_sample_task(
    task_context_cls: Type[Any],
    task_type_enum: Type[Any],
    task_id: str = "test_task_001",
    task_type: str = "REASONING",
    content: str = "What are the main advantages and disadvantages of renewable energy sources?",
    priority: int = 7,
    deadline_hours: float = 1.0,
) -> Any:
    """Build deterministic TaskContext-style objects."""
    return task_context_cls(
        task_id=task_id,
        task_type=task_type_enum[task_type],
        content=content,
        requirements={"detail_level": "comprehensive", "include_examples": True},
        constraints={"max_tokens": 1000, "response_time": 30},
        priority=priority,
        deadline=datetime.now() + timedelta(hours=deadline_hours),
    )


def build_processing_results(
    processing_result_cls: Type[Any],
    models: Sequence[Any],
    task_id: str = "test_task_001",
) -> List[Any]:
    """Build deterministic ProcessingResult-style objects aligned with provided model IDs."""
    model_ids = {model.model_id for model in models}
    results: List[Any] = []
    for (
        model_id,
        content,
        confidence,
        processing_time,
        tokens_used,
        cost,
    ) in _RESULT_ROWS:
        if model_id in model_ids:
            results.append(
                processing_result_cls(
                    task_id=task_id,
                    model_id=model_id,
                    content=content,
                    confidence=confidence,
                    processing_time=processing_time,
                    tokens_used=tokens_used,
                    cost=cost,
                    metadata={"temperature": 0.7},
                )
            )
    return results


def build_consensus_config(
    consensus_config_cls: Type[Any],
    strategy_enum: Type[Any],
    preset: str,
) -> Any:
    """Build ConsensusConfig-style objects from compact preset rows."""
    (
        strategy_name,
        min_models,
        max_models,
        confidence_threshold,
        agreement_threshold,
        timeout_seconds,
        retry_attempts,
        model_weights,
    ) = _CONSENSUS_ROWS[preset]

    kwargs: Dict[str, Any] = {
        "strategy": strategy_enum[strategy_name],
        "min_models": min_models,
        "max_models": max_models,
        "confidence_threshold": confidence_threshold,
        "agreement_threshold": agreement_threshold,
        "timeout_seconds": timeout_seconds,
    }
    if retry_attempts is not None:
        kwargs["retry_attempts"] = retry_attempts
    if model_weights is not None:
        kwargs["model_weights"] = model_weights
    return consensus_config_cls(**kwargs)


__all__ = [
    "build_sample_models",
    "build_generated_models",
    "build_sample_task",
    "build_processing_results",
    "build_consensus_config",
]
