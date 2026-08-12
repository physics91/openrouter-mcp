"""Request models for collective intelligence handlers."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from ..config.constants import ConsensusDefaults
from ..models.requests import BaseCollectiveRequest, BaseConsensusRequest


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
    performance_requirements: Optional[Dict[str, float]] = Field(
        None,
        description="Performance requirements as metric-score pairs, e.g. {'accuracy': 0.9, 'speed': 0.7}. Keys are used as routing hints.",
    )
    constraints: Optional[Dict[str, Any]] = Field(
        None,
        description="Task constraints, e.g. {'max_cost': 0.01, 'preferred_provider': 'openai'}",
    )


class CrossValidationRequest(BaseCollectiveRequest):
    """Request for cross-model validation."""

    content: str = Field(..., description="Content to validate across models")
    validation_criteria: Optional[List[str]] = Field(
        None, description="Specific validation criteria"
    )
    threshold: float = Field(
        ConsensusDefaults.CONFIDENCE_THRESHOLD,
        description="Validation threshold (0.0-1.0). Content scoring below this is considered invalid",
    )


class CollaborativeSolvingRequest(BaseCollectiveRequest):
    """Request for collaborative problem solving."""

    problem: str = Field(..., description="Problem to solve collaboratively")
    requirements: Optional[Dict[str, Any]] = Field(
        None, description="Problem requirements"
    )
    constraints: Optional[Dict[str, Any]] = Field(
        None, description="Problem constraints"
    )
    max_iterations: int = Field(3, description="Maximum number of iteration rounds")


_ORIGINAL_MODULE = f"{__package__}.collective_intelligence"
for _request_model in (
    CollectiveChatRequest,
    EnsembleReasoningRequest,
    AdaptiveModelRequest,
    CrossValidationRequest,
    CollaborativeSolvingRequest,
):
    _request_model.__module__ = _ORIGINAL_MODULE

del _request_model
