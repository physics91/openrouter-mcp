"""
Collective Intelligence MCP Handler

This module provides MCP tools for accessing collective intelligence capabilities,
enabling multi-model consensus, ensemble reasoning, adaptive model selection,
cross-model validation, and collaborative problem-solving.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from ..collective_intelligence import (
    CollectiveIntelligenceLifecycleManager,
    ConsensusConfig,
    ConsensusStrategy,
    ProcessingResult,
    TaskContext,
    TaskType,
    get_lifecycle_manager,
    shutdown_lifecycle_manager,
)

# Import centralized configuration constants
from ..config.constants import CollectiveDefaults, ConsensusDefaults

# Import shared MCP instance and client manager from registry
from ..mcp_registry import get_openrouter_client, mcp
from ..models.requests import BaseCollectiveRequest, BaseConsensusRequest
from ..utils.async_utils import maybe_await
from ._collective_serialization import (
    _serialize_consensus_result,
    _serialize_cross_validation_result,
    _serialize_ensemble_result,
    _serialize_routing_decision,
    _serialize_solving_result,
)
from ._openrouter_model_provider import OpenRouterModelProvider

logger = logging.getLogger(__name__)


async def _get_configured_lifecycle_manager() -> CollectiveIntelligenceLifecycleManager:
    """Return lifecycle manager configured with a shared OpenRouter model provider."""
    client = await maybe_await(get_openrouter_client())
    lifecycle_manager = await get_lifecycle_manager()
    existing_provider = getattr(lifecycle_manager, "_model_provider", None)
    existing_client = getattr(existing_provider, "client", None)

    if existing_client is not None and existing_client is not client:
        await shutdown_lifecycle_manager()
        lifecycle_manager = await get_lifecycle_manager()

    model_provider = OpenRouterModelProvider(client)
    lifecycle_manager.configure(model_provider)
    return lifecycle_manager


def _resolve_collective_max_tokens(max_tokens: Optional[int]) -> int:
    """Apply a safe default cap for live collective requests."""
    return max_tokens if max_tokens is not None else CollectiveDefaults.DEFAULT_MAX_TOKENS


def _build_requirements(
    *,
    base: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    models: Optional[List[str]] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build requirements dict with consistent keys for CI components."""
    requirements: Dict[str, Any] = {}
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
    base: Optional[Dict[str, Any]] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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


# Pydantic models for MCP tool inputs


class CollectiveChatRequest(BaseConsensusRequest):
    """Request for collective chat completion."""

    prompt: str = Field(..., description="The prompt to process collectively")
    strategy: Literal["majority_vote", "weighted_average", "confidence_threshold"] = Field(
        "majority_vote",
        description="Consensus strategy: majority_vote, weighted_average, confidence_threshold",
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
    decompose: bool = Field(True, description="Whether to decompose the problem into subtasks")


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
    requirements: Optional[Dict[str, Any]] = Field(None, description="Problem requirements")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Problem constraints")
    max_iterations: int = Field(3, description="Maximum number of iteration rounds")


def create_task_context(
    content: str,
    task_type: str = "reasoning",
    requirements: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
) -> TaskContext:
    """Create a TaskContext from request parameters."""
    try:
        task_type_enum = TaskType(task_type.lower())
    except ValueError:
        valid = ", ".join(sorted(e.value for e in TaskType))
        raise ValueError(f"Invalid task_type '{task_type}'. Valid: {valid}")

    return TaskContext(
        task_type=task_type_enum,
        content=content,
        requirements=requirements or {},
        constraints=constraints or {},
    )


async def _collective_chat_completion_impl(
    request: CollectiveChatRequest,
) -> Dict[str, Any]:
    """
    Generate chat completion using collective intelligence with multiple models.

    This tool leverages multiple AI models to reach consensus on responses,
    providing more reliable and accurate results through collective decision-making.

    Args:
        request: Collective chat completion request

    Returns:
        Dictionary containing:
        - consensus_response: The agreed-upon response
        - agreement_level: Level of agreement between models
        - confidence_score: Confidence in the consensus
        - participating_models: List of models that participated
        - individual_responses: Responses from each model
        - processing_time: Total time taken

    Example:
        request = CollectiveChatRequest(
            prompt="Explain quantum computing in simple terms",
            strategy="majority_vote",
            min_models=3
        )
        result = await collective_chat_completion(request)
    """
    logger.info(f"Processing collective chat completion with strategy: {request.strategy}")

    try:
        # Setup - use shared singleton client from registry
        lifecycle_manager = await _get_configured_lifecycle_manager()

        # Configure consensus engine (Pydantic validates the Literal type)
        strategy = ConsensusStrategy(request.strategy)

        config = ConsensusConfig(
            strategy=strategy,
            min_models=request.min_models,
            max_models=request.max_models,
            timeout_seconds=ConsensusDefaults.TIMEOUT_SECONDS,
            confidence_threshold=request.confidence_threshold,
        )

        # Get singleton consensus engine from lifecycle manager
        consensus_engine = await lifecycle_manager.get_consensus_engine(config)

        # Create task context
        requirements = _build_collective_request_requirements(request)

        task = create_task_context(content=request.prompt, requirements=requirements)

        # Process with consensus - NO async with client (client is singleton managed by lifecycle)
        result = await consensus_engine.process(task)
        return _serialize_consensus_result(result)

    except Exception as e:
        logger.error(f"Collective chat completion failed: {str(e)}")
        raise


async def collective_chat_completion(request: CollectiveChatRequest) -> Dict[str, Any]:
    """Generate a chat completion using multiple AI models to reach consensus.

    Queries several models in parallel and combines their responses using the chosen
    consensus strategy, producing a single agreed-upon answer with confidence metrics.

    Returns keys: consensus_response, agreement_level, confidence_score,
    participating_models, individual_responses, strategy_used, processing_time,
    quality_metrics.
    """
    return await _collective_chat_completion_impl(request)


async def _ensemble_reasoning_impl(request: EnsembleReasoningRequest) -> Dict[str, Any]:
    """
    Perform ensemble reasoning using specialized models for different aspects.

    This tool decomposes complex problems and routes different parts to models
    best suited for each subtask, then combines the results intelligently.

    Args:
        request: Ensemble reasoning request

    Returns:
        Dictionary containing:
        - final_result: The combined reasoning result
        - subtask_results: Results from individual subtasks
        - model_assignments: Which models handled which subtasks
        - reasoning_quality: Quality metrics for the reasoning

    Example:
        request = EnsembleReasoningRequest(
            problem="Design a sustainable energy system for a smart city",
            task_type="analysis",
            decompose=True
        )
        result = await ensemble_reasoning(request)
    """
    logger.info(f"Processing ensemble reasoning for task type: {request.task_type}")

    try:
        # Setup - use shared singleton client from registry
        lifecycle_manager = await _get_configured_lifecycle_manager()

        # Get singleton ensemble reasoner from lifecycle manager
        ensemble_reasoner = await lifecycle_manager.get_ensemble_reasoner()

        # Create task context with temperature, max_tokens, system_prompt and models
        requirements = _build_collective_request_requirements(request)

        task = create_task_context(
            content=request.problem,
            task_type=request.task_type,
            requirements=requirements,
        )

        # Process with ensemble reasoning - NO async with (singleton managed by lifecycle)
        result = await ensemble_reasoner.process(task, decompose=request.decompose)
        return _serialize_ensemble_result(result)

    except Exception as e:
        logger.error(f"Ensemble reasoning failed: {str(e)}")
        raise


async def ensemble_reasoning(request: EnsembleReasoningRequest) -> Dict[str, Any]:
    """Decompose a complex problem and route subtasks to specialized models.

    Breaks the problem into subtasks, assigns each to the best-suited model, and
    synthesizes the partial results into a unified answer.

    Returns keys: final_result, subtask_results, model_assignments,
    reasoning_quality, processing_time, strategy_used, success_rate, total_cost.
    """
    return await _ensemble_reasoning_impl(request)


async def _adaptive_model_selection_impl(
    request: AdaptiveModelRequest,
) -> Dict[str, Any]:
    """
    Intelligently select the best model for a given task using adaptive routing.

    This tool analyzes the query characteristics and selects the most appropriate
    model based on the task type, performance requirements, and current model metrics.

    Args:
        request: Adaptive model selection request

    Returns:
        Dictionary containing:
        - selected_model: The chosen model ID
        - selection_reasoning: Why this model was selected
        - confidence: Confidence in the selection
        - alternative_models: Other viable options
        - routing_metrics: Performance metrics used in selection

    Example:
        request = AdaptiveModelRequest(
            query="Write a Python function to sort a list",
            task_type="code_generation",
            performance_requirements={"accuracy": 0.9, "speed": 0.7}
        )
        result = await adaptive_model_selection(request)
    """
    logger.info(f"Processing adaptive model selection for task: {request.task_type}")

    try:
        # Setup - use shared singleton client from registry
        lifecycle_manager = await _get_configured_lifecycle_manager()

        # Get singleton adaptive router from lifecycle manager
        adaptive_router = await lifecycle_manager.get_adaptive_router()

        # Create task context with performance requirements
        requirements = _build_requirements(base=request.performance_requirements)

        task = create_task_context(
            content=request.query,
            task_type=request.task_type,
            requirements=requirements,
            constraints=request.constraints,
        )

        # Perform adaptive routing - NO async with (singleton managed by lifecycle)
        decision = await adaptive_router.process(task)
        return _serialize_routing_decision(decision)

    except Exception as e:
        logger.error(f"Adaptive model selection failed: {str(e)}")
        raise


async def adaptive_model_selection(request: AdaptiveModelRequest) -> Dict[str, Any]:
    """Select the best model for a task using adaptive performance-based routing.

    Analyzes the query and task type, then picks the most suitable model based on
    historical performance metrics and task requirements.

    Returns keys: selected_model, selection_reasoning, confidence,
    alternative_models, routing_metrics, selection_time.
    """
    return await _adaptive_model_selection_impl(request)


async def _cross_model_validation_impl(
    request: CrossValidationRequest,
) -> Dict[str, Any]:
    """
    Validate content quality and accuracy across multiple models.

    This tool uses multiple models to cross-validate content, checking for
    accuracy, consistency, and identifying potential errors or biases.

    Args:
        request: Cross-validation request

    Returns:
        Dictionary containing:
        - validation_result: Overall validation result
        - validation_score: Numerical validation score
        - validation_issues: Issues found by multiple models
        - model_validations: Individual validation results
        - recommendations: Suggested improvements
        - confidence: Validation confidence score
        - processing_time: Total processing time
        - quality_metrics: Overall quality metrics

    Example:
        request = CrossValidationRequest(
            content="The Earth is flat and the moon landing was fake",
            validation_criteria=["factual_accuracy", "scientific_consensus"],
            threshold=0.7
        )
        result = await cross_model_validation(request)
    """
    logger.info("Processing cross-model validation")

    try:
        # Setup - use shared singleton client from registry
        lifecycle_manager = await _get_configured_lifecycle_manager()

        # Get singleton cross validator from lifecycle manager
        cross_validator = await lifecycle_manager.get_cross_validator()

        # Create a dummy result to validate
        dummy_result = ProcessingResult(
            task_id="validation_task",
            model_id="content_to_validate",
            content=request.content,
            confidence=1.0,
        )

        # Create task context for validation with criteria and models
        extras: Dict[str, Any] = {"validation_threshold": request.threshold}
        if request.validation_criteria:
            extras["validation_criteria"] = request.validation_criteria
        requirements = _build_collective_request_requirements(
            request,
            extras=extras,
        )

        task = create_task_context(
            content=request.content, task_type="analysis", requirements=requirements
        )

        # Perform cross-validation - NO async with (singleton managed by lifecycle)
        result = await cross_validator.process(dummy_result, task)
        return _serialize_cross_validation_result(result)

    except Exception as e:
        logger.error(f"Cross-model validation failed: {str(e)}")
        raise


async def cross_model_validation(request: CrossValidationRequest) -> Dict[str, Any]:
    """Validate content accuracy and quality by cross-checking with multiple models.

    Multiple models independently review the content for errors, inconsistencies,
    and biases, then aggregate findings into a validation report.

    Returns keys: validation_result, validation_score, validation_issues,
    model_validations, recommendations, confidence, processing_time,
    quality_metrics.
    """
    return await _cross_model_validation_impl(request)


async def _collaborative_problem_solving_impl(
    request: CollaborativeSolvingRequest,
) -> Dict[str, Any]:
    """
    Solve complex problems through collaborative multi-model interaction.

    This tool orchestrates multiple models to work together on complex problems,
    with models building on each other's contributions through iterative refinement.

    Args:
        request: Collaborative problem solving request

    Returns:
        Dictionary containing:
        - final_solution: The collaborative solution
        - solution_path: Step-by-step solution development
        - alternative_solutions: Alternative approaches discovered
        - quality_assessment: Quality metrics for the solution
        - component_contributions: Individual component contributions
        - confidence: Confidence score
        - improvement_suggestions: Suggested improvements
        - processing_time: Total processing time
        - session_id: Collaboration session identifier
        - strategy_used: Strategy used for solving
        - components_used: Components involved in solving

    Example:
        request = CollaborativeSolvingRequest(
            problem="Design an AI ethics framework for autonomous vehicles",
            requirements={"stakeholders": ["drivers", "pedestrians", "lawmakers"]},
            max_iterations=3
        )
        result = await collaborative_problem_solving(request)
    """
    logger.info("Processing collaborative problem solving")

    try:
        # Setup - use shared singleton client from registry
        lifecycle_manager = await _get_configured_lifecycle_manager()

        # Get singleton collaborative solver from lifecycle manager
        collaborative_solver = await lifecycle_manager.get_collaborative_solver()

        # Create task context with max_iterations, system_prompt and models
        extras: Dict[str, Any] = {"max_iterations": request.max_iterations}
        requirements = _build_collective_request_requirements(
            request,
            base=request.requirements,
            extras=extras,
        )

        task = create_task_context(
            content=request.problem,
            requirements=requirements,
            constraints=request.constraints,
        )

        # Start collaborative solving session - NO async with (singleton managed by lifecycle)
        result = await collaborative_solver.process(task, strategy="iterative")
        return _serialize_solving_result(result)

    except Exception as e:
        logger.error(f"Collaborative problem solving failed: {str(e)}")
        raise


async def collaborative_problem_solving(
    request: CollaborativeSolvingRequest,
) -> Dict[str, Any]:
    """Solve complex problems through iterative multi-model collaboration.

    Orchestrates multiple models to build on each other's contributions through
    iterative refinement rounds until the solution converges.

    Returns keys: final_solution, solution_path, alternative_solutions,
    quality_assessment, component_contributions, confidence,
    improvement_suggestions, processing_time, session_id, strategy_used,
    components_used.
    """
    return await _collaborative_problem_solving_impl(request)


# Register tools without replacing the callable references (for direct use in tests/scripts).
_collective_chat_completion_tool = mcp.tool(collective_chat_completion)
_ensemble_reasoning_tool = mcp.tool(ensemble_reasoning)
_adaptive_model_selection_tool = mcp.tool(adaptive_model_selection)
_cross_model_validation_tool = mcp.tool(cross_model_validation)
_collaborative_problem_solving_tool = mcp.tool(collaborative_problem_solving)
