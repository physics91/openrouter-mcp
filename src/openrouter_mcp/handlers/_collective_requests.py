"""Request models for collective intelligence handlers."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from ..collective_intelligence import TaskContext, TaskType
from ..config.constants import CollectiveDefaults, ConsensusDefaults
from ..models.requests import BaseCollectiveRequest, BaseConsensusRequest


def _resolve_collective_max_tokens(max_tokens: Optional[int]) -> int:
    """Apply a safe default cap for live collective requests."""
    return (
        max_tokens if max_tokens is not None else CollectiveDefaults.DEFAULT_MAX_TOKENS
    )


def _build_requirements(
    *,
    base: Optional[dict[str, Any]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    models: Optional[list[str]] = None,
    extras: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build requirements dict with consistent keys for CI components."""
    requirements: dict[str, Any] = {}
    if base:
        requirements.update(base)
    if extras:
        requirements.update(extras)
    if temperature is not None:
        requirements["temperature"] = temperature
    if max_tokens is not None:
        requirements["max_tokens"] = max_tokens
    if models:
        requirements["preferred_models"] = models
    return requirements


def _build_collective_request_requirements(
    request: BaseCollectiveRequest,
    *,
    base: Optional[dict[str, Any]] = None,
    extras: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build requirements shared by collective request types."""
    request_extras = dict(extras or {})
    if request.system_prompt:
        request_extras["system_prompt"] = request.system_prompt

    return _build_requirements(
        base=base,
        temperature=request.temperature,
        max_tokens=_resolve_collective_max_tokens(request.max_tokens),
        models=request.models,
        extras=request_extras or None,
    )


def create_task_context(
    content: str,
    task_type: str = "reasoning",
    requirements: Optional[dict[str, Any]] = None,
    constraints: Optional[dict[str, Any]] = None,
) -> TaskContext:
    """Create a TaskContext from request parameters."""
    try:
        task_type_enum = TaskType(task_type.lower())
    except ValueError as exc:
        valid = ", ".join(sorted(e.value for e in TaskType))
        raise ValueError(f"Invalid task_type '{task_type}'. Valid: {valid}") from exc

    return TaskContext(
        task_type=task_type_enum,
        content=content,
        requirements=requirements or {},
        constraints=constraints or {},
    )


class CollectiveChatRequest(BaseConsensusRequest):
    """Request for collective chat completion."""

    prompt: str = Field(..., description="The prompt to process collectively")
    strategy: Literal["majority_vote", "weighted_average", "confidence_threshold"] = (
        Field(
            "majority_vote",
            description="Consensus strategy: majority_vote, weighted_average, confidence_threshold",
        )
    )


_TASK_TYPE_LITERAL = Literal[
    "reasoning",
    "analysis",
    "creative",
    "factual",
    "code_generation",
    "summarization",
    "translation",
    "math",
    "classification",
]


class EnsembleReasoningRequest(BaseCollectiveRequest):
    """Request for ensemble reasoning."""

    problem: str = Field(..., description="Problem to solve with ensemble reasoning")
    task_type: _TASK_TYPE_LITERAL = Field(
        "reasoning",
        description="Type of task: reasoning, analysis, creative, factual, code_generation, summarization, translation, math, classification",
    )
    decompose: bool = Field(
        True, description="Whether to decompose the problem into subtasks"
    )


class AdaptiveModelRequest(BaseModel):
    """Request for adaptive model selection."""

    query: str = Field(..., description="Query for adaptive model selection")
    task_type: _TASK_TYPE_LITERAL = Field(
        "reasoning",
        description="Type of task: reasoning, analysis, creative, factual, code_generation, summarization, translation, math, classification",
    )
    performance_requirements: Optional[dict[str, float]] = Field(
        None,
        description="Performance requirements as metric-score pairs, e.g. {'accuracy': 0.9, 'speed': 0.7}. Keys are used as routing hints.",
    )
    constraints: Optional[dict[str, Any]] = Field(
        None,
        description="Task constraints, e.g. {'max_cost': 0.01, 'preferred_provider': 'openai'}",
    )


class CrossValidationRequest(BaseCollectiveRequest):
    """Request for cross-model validation."""

    content: str = Field(..., description="Content to validate across models")
    validation_criteria: Optional[list[str]] = Field(
        None, description="Specific validation criteria"
    )
    threshold: float = Field(
        ConsensusDefaults.CONFIDENCE_THRESHOLD,
        description="Validation threshold (0.0-1.0). Content scoring below this is considered invalid",
    )


class CollaborativeSolvingRequest(BaseCollectiveRequest):
    """Request for collaborative problem solving."""

    problem: str = Field(..., description="Problem to solve collaboratively")
    requirements: Optional[dict[str, Any]] = Field(
        None, description="Problem requirements"
    )
    constraints: Optional[dict[str, Any]] = Field(
        None, description="Problem constraints"
    )
    max_iterations: int = Field(3, description="Maximum number of iteration rounds")


_ORIGINAL_MODULE = f"{__package__}.collective_intelligence"
for _compatibility_export in (
    _resolve_collective_max_tokens,
    _build_requirements,
    _build_collective_request_requirements,
    create_task_context,
    CollectiveChatRequest,
    EnsembleReasoningRequest,
    AdaptiveModelRequest,
    CrossValidationRequest,
    CollaborativeSolvingRequest,
):
    _compatibility_export.__module__ = _ORIGINAL_MODULE

del _compatibility_export
