"""
Collective Intelligence MCP Handler

This module provides MCP tools for accessing collective intelligence capabilities,
enabling multi-model consensus, ensemble reasoning, adaptive model selection,
cross-model validation, and collaborative problem-solving.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

import httpx
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ..client.openrouter import OpenRouterClient

from ..collective_intelligence import (
    CollectiveIntelligenceLifecycleManager,
    ConsensusConfig,
    ConsensusStrategy,
    ModelInfo,
    ProcessingResult,
    TaskContext,
    TaskType,
    get_lifecycle_manager,
)
from ..collective_intelligence.base import ModelCapability

# Import centralized configuration constants
from ..config.constants import ConsensusDefaults, ModelDefaults, PricingDefaults

# Import shared MCP instance and client manager from registry
from ..mcp_registry import get_openrouter_client, mcp
from ..models.requests import BaseCollectiveRequest, BaseConsensusRequest
from ..utils.async_utils import maybe_await
from ..utils.pricing import estimate_cost_from_usage, normalize_pricing

logger = logging.getLogger(__name__)


class OpenRouterModelProvider:
    """OpenRouter implementation of ModelProvider protocol."""

    def __init__(self, client: OpenRouterClient):
        """
        Initialize the model provider.

        Args:
            client: OpenRouterClient instance that already has cache configured
        """
        self.client = client
        self._model_pricing_cache: Dict[str, Dict[str, float]] = {}

    async def process_task(
        self, task: TaskContext, model_id: str, **kwargs: Any
    ) -> ProcessingResult:
        """Process a task using the specified model."""
        start_time = datetime.now()

        try:
            # Prepare messages for the model
            messages = [{"role": "user", "content": task.content}]

            # Add system message if requirements specify behavior
            if task.requirements.get("system_prompt"):
                messages.insert(
                    0, {"role": "system", "content": task.requirements["system_prompt"]}
                )

            # Extract temperature from task requirements or kwargs, with fallback to default
            # Use explicit None check to preserve valid 0.0 temperature values
            temp_from_req = task.requirements.get("temperature")
            temp_from_kwargs = kwargs.get("temperature")
            temperature = (
                temp_from_req
                if temp_from_req is not None
                else (
                    temp_from_kwargs if temp_from_kwargs is not None else ModelDefaults.TEMPERATURE
                )
            )

            # Extract max_tokens from kwargs or task requirements
            # Use explicit None check to preserve valid 0 values
            kw_max = kwargs.get("max_tokens")
            max_tokens_val = kw_max if kw_max is not None else task.requirements.get("max_tokens")

            # Call OpenRouter API
            response = await self.client.chat_completion(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens_val,
                stream=False,
            )

            processing_time = (datetime.now() - start_time).total_seconds()

            # Extract response content
            content = ""
            if response.get("choices") and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]

            # Calculate confidence (simplified heuristic)
            confidence = self._calculate_confidence(response, content)

            # Extract usage information
            usage = response.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)

            # Calculate actual cost using real pricing
            cost = await self._estimate_cost(model_id, usage)

            return ProcessingResult(
                task_id=task.task_id,
                model_id=model_id,
                content=content,
                confidence=confidence,
                processing_time=processing_time,
                tokens_used=tokens_used,
                cost=cost,
                metadata={
                    "usage": usage,
                    "response_metadata": response.get("model", {}),
                },
            )

        except Exception as e:
            logger.error(f"Task processing failed for model {model_id}: {str(e)}")
            raise

    async def get_available_models(self) -> List[ModelInfo]:
        """
        Get list of available models.

        This method delegates to the client's cache system, eliminating
        the redundant local cache and preventing unnecessary API calls.
        """
        try:
            # Use client's built-in cache system
            raw_models = await self.client.list_models(use_cache=True)

            # Convert to ModelInfo objects
            models = []
            for raw_model in raw_models:
                model_info = ModelInfo(
                    model_id=raw_model["id"],
                    name=raw_model.get("name", raw_model["id"]),
                    provider=raw_model.get("provider", "unknown"),
                    context_length=raw_model.get("context_length", 4096),
                    cost_per_token=self._extract_cost(raw_model.get("pricing", {})),
                    metadata=raw_model,
                )

                # Add capability estimates based on model properties
                model_info.capabilities = self._estimate_capabilities(raw_model)

                models.append(model_info)

            return models

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"Failed to fetch models: {str(e)}")
            raise RuntimeError(
                f"Unable to fetch available models from OpenRouter: {type(e).__name__}. "
                "Check network connectivity and API key configuration."
            ) from e

    def _calculate_confidence(self, response: Dict[str, Any], content: str) -> float:
        """Calculate confidence score based on response characteristics."""
        # This is a simplified confidence calculation
        # In practice, this could use more sophisticated methods

        base_confidence = float(ConsensusDefaults.CONFIDENCE_THRESHOLD)

        # Adjust based on response length (longer responses often more confident)
        if len(content) > 100:
            base_confidence += 0.1
        elif len(content) < 20:
            base_confidence -= 0.2

        # Adjust based on finish reason
        finish_reason = response.get("choices", [{}])[0].get("finish_reason")
        if finish_reason == "stop":
            base_confidence += 0.1
        elif finish_reason == "length":
            base_confidence -= 0.1

        return float(max(0.0, min(1.0, base_confidence)))

    async def _get_model_pricing(self, model_id: str) -> Dict[str, float]:
        """
        Get pricing information for a specific model.

        Delegates to the client's public ``get_model_pricing()`` API which
        already handles cache look-up, fallback, and normalisation.

        Args:
            model_id: Model identifier

        Returns:
            Dictionary with 'prompt' and 'completion' cost per token
        """
        if model_id in self._model_pricing_cache:
            return self._model_pricing_cache[model_id]

        try:
            normalized_raw = await self.client.get_model_pricing(model_id)
        except Exception as e:
            logger.warning(f"Failed to fetch pricing for model {model_id}: {e}")
            normalized_raw = normalize_pricing({}, PricingDefaults.DEFAULT_TOKEN_PRICE)

        normalized = {
            "prompt": float(normalized_raw.get("prompt", 0.0)),
            "completion": float(normalized_raw.get("completion", 0.0)),
        }

        self._model_pricing_cache[model_id] = normalized
        return normalized

    async def _estimate_cost(self, model_id: str, usage: Dict[str, int]) -> float:
        """
        Estimate cost based on actual model pricing and token usage.

        Args:
            model_id: Model identifier
            usage: Usage dictionary with 'prompt_tokens' and 'completion_tokens'

        Returns:
            Estimated cost in USD
        """
        pricing = await self._get_model_pricing(model_id)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_cost = float(
            estimate_cost_from_usage(
                usage,
                pricing,
                PricingDefaults.DEFAULT_TOKEN_PRICE,
            )
        )
        prompt_cost = prompt_tokens * pricing["prompt"]
        completion_cost = completion_tokens * pricing["completion"]

        logger.debug(
            f"Cost calculation for {model_id}: "
            f"{prompt_tokens} prompt tokens (${prompt_cost:.6f}) + "
            f"{completion_tokens} completion tokens (${completion_cost:.6f}) = "
            f"${total_cost:.6f}"
        )

        return total_cost

    def _extract_cost(self, pricing: Dict[str, Any]) -> float:
        """Extract cost per token from pricing information."""
        normalized = normalize_pricing(pricing, PricingDefaults.DEFAULT_TOKEN_PRICE)
        return float(normalized.get("completion", PricingDefaults.DEFAULT_TOKEN_PRICE))

    def _estimate_capabilities(self, raw_model: Dict[str, Any]) -> Dict[ModelCapability, float]:
        """Estimate model capabilities based on model metadata."""
        capabilities: Dict[ModelCapability, float] = {}
        model_id = raw_model["id"].lower()

        # Reasoning capability
        if any(term in model_id for term in ["gpt-4", "claude", "o1"]):
            capabilities[ModelCapability.REASONING] = 0.9
        elif any(term in model_id for term in ["gpt-3.5", "llama"]):
            capabilities[ModelCapability.REASONING] = 0.7
        else:
            capabilities[ModelCapability.REASONING] = 0.5

        # Creativity capability
        if any(term in model_id for term in ["claude", "gpt-4"]):
            capabilities[ModelCapability.CREATIVITY] = 0.8
        else:
            capabilities[ModelCapability.CREATIVITY] = 0.6

        # Code capability
        if any(term in model_id for term in ["code", "codestral", "deepseek"]):
            capabilities[ModelCapability.CODE] = 0.9
        elif any(term in model_id for term in ["gpt-4", "claude"]):
            capabilities[ModelCapability.CODE] = 0.8
        else:
            capabilities[ModelCapability.CODE] = 0.5

        # Accuracy capability
        if any(term in model_id for term in ["gpt-4", "claude", "o1"]):
            capabilities[ModelCapability.ACCURACY] = 0.9
        else:
            capabilities[ModelCapability.ACCURACY] = 0.7

        return capabilities


async def _get_configured_lifecycle_manager() -> CollectiveIntelligenceLifecycleManager:
    """Return lifecycle manager configured with a shared OpenRouter model provider."""
    client = await maybe_await(get_openrouter_client())
    model_provider = OpenRouterModelProvider(client)
    lifecycle_manager = await get_lifecycle_manager()
    lifecycle_manager.configure(model_provider)
    return lifecycle_manager


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
        extras = {}
        if request.system_prompt:
            extras["system_prompt"] = request.system_prompt
        requirements = _build_requirements(
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            models=request.models,
            extras=extras or None,
        )

        task = create_task_context(content=request.prompt, requirements=requirements)

        # Process with consensus - NO async with client (client is singleton managed by lifecycle)
        result = await consensus_engine.process(task)

        return {
            "consensus_response": result.consensus_content,
            "agreement_level": result.agreement_level.value,
            "confidence_score": result.confidence_score,
            "participating_models": result.participating_models,
            "individual_responses": [
                {
                    "model": resp.model_id,
                    "content": resp.result.content,
                    "confidence": resp.result.confidence,
                }
                for resp in result.model_responses
            ],
            "strategy_used": result.strategy_used.value,
            "processing_time": result.processing_time,
            "quality_metrics": {
                "accuracy": result.quality_metrics.accuracy,
                "consistency": result.quality_metrics.consistency,
                "completeness": result.quality_metrics.completeness,
                "overall_score": result.quality_metrics.overall_score(),
            },
        }

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
        extras = {}
        if request.system_prompt:
            extras["system_prompt"] = request.system_prompt
        requirements = _build_requirements(
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            models=request.models,
            extras=extras or None,
        )

        task = create_task_context(
            content=request.problem,
            task_type=request.task_type,
            requirements=requirements,
        )

        # Process with ensemble reasoning - NO async with (singleton managed by lifecycle)
        result = await ensemble_reasoner.process(task, decompose=request.decompose)

        return {
            "final_result": result.final_content,
            "subtask_results": [
                {
                    "subtask": subtask.sub_task.content,
                    "model": subtask.assignment.model_id,
                    "result": subtask.result.content,
                    "confidence": subtask.result.confidence,
                    "success": subtask.success,
                }
                for subtask in result.sub_task_results
            ],
            "model_assignments": {
                subtask.assignment.model_id: subtask.sub_task.content
                for subtask in result.sub_task_results
            },
            "reasoning_quality": {
                "overall_quality": result.overall_quality.overall_score(),
                "consistency": result.overall_quality.consistency,
                "completeness": result.overall_quality.completeness,
            },
            "processing_time": result.total_time,
            "strategy_used": result.decomposition_strategy.value,
            "success_rate": result.success_rate,
            "total_cost": result.total_cost,
        }

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

        return {
            "selected_model": decision.selected_model_id,
            "selection_reasoning": decision.justification,
            "confidence": decision.confidence_score,
            "alternative_models": [
                {"model": alt[0], "score": alt[1]}
                for alt in decision.alternative_models[:3]  # Top 3 alternatives
            ],
            "routing_metrics": {
                "expected_performance": decision.expected_performance,
                "strategy_used": decision.strategy_used.value,
                "total_candidates": decision.metadata.get("total_candidates", 0),
            },
            "selection_time": decision.routing_time,
        }

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
        if request.system_prompt:
            extras["system_prompt"] = request.system_prompt
        requirements = _build_requirements(
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            models=request.models,
            extras=extras,
        )

        task = create_task_context(
            content=request.content, task_type="analysis", requirements=requirements
        )

        # Perform cross-validation - NO async with (singleton managed by lifecycle)
        result = await cross_validator.process(dummy_result, task)

        report = result.validation_report
        issues = report.issues
        validator_models = getattr(report, "validator_models", []) or []
        if not validator_models:
            seen_models = set()
            for issue in issues:
                model_id = getattr(issue, "validator_model_id", None)
                if model_id and model_id not in seen_models:
                    seen_models.add(model_id)
                    validator_models.append(model_id)

        model_validations = []
        for model_id in validator_models:
            model_issues = [issue for issue in issues if issue.validator_model_id == model_id]
            criteria_values = {
                (issue.criteria.value if hasattr(issue.criteria, "value") else str(issue.criteria))
                for issue in model_issues
            }
            if not criteria_values:
                criteria_label = "none"
            elif len(criteria_values) == 1:
                criteria_label = next(iter(criteria_values))
            else:
                criteria_label = "multiple"

            model_validations.append(
                {
                    "model": model_id,
                    "criteria": criteria_label,
                    "issues_found": len(model_issues),
                }
            )

        return {
            "validation_result": "VALID" if result.is_valid else "INVALID",
            "validation_score": result.validation_confidence,
            "validation_issues": [
                {
                    "criteria": issue.criteria.value,
                    "severity": issue.severity.value,
                    "description": issue.description,
                    "suggestion": issue.suggestion,
                    "confidence": issue.confidence,
                }
                for issue in issues
            ],
            "model_validations": model_validations,
            "recommendations": result.improvement_suggestions,
            "confidence": result.validation_confidence,
            "processing_time": result.processing_time,
            "quality_metrics": {
                "overall_score": result.quality_metrics.overall_score(),
                "accuracy": result.quality_metrics.accuracy,
                "consistency": result.quality_metrics.consistency,
            },
        }

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
        if request.system_prompt:
            extras["system_prompt"] = request.system_prompt
        requirements = _build_requirements(
            base=request.requirements,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            models=request.models,
            extras=extras,
        )

        task = create_task_context(
            content=request.problem,
            requirements=requirements,
            constraints=request.constraints,
        )

        # Start collaborative solving session - NO async with (singleton managed by lifecycle)
        result = await collaborative_solver.process(task, strategy="iterative")

        return {
            "final_solution": result.final_content,
            "solution_path": result.solution_path,
            "alternative_solutions": result.alternative_solutions,
            "quality_assessment": {
                "overall_score": result.quality_assessment.overall_score(),
                "accuracy": result.quality_assessment.accuracy,
                "consistency": result.quality_assessment.consistency,
                "completeness": result.quality_assessment.completeness,
            },
            "component_contributions": result.component_contributions,
            "confidence": result.confidence_score,
            "improvement_suggestions": result.improvement_suggestions,
            "processing_time": result.total_processing_time,
            "session_id": result.session.session_id,
            "strategy_used": result.session.strategy.value,
            "components_used": result.session.components_used,
        }

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
