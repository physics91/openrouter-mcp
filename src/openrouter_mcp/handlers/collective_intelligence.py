"""
Collective Intelligence MCP Handler

This module provides MCP tools for accessing collective intelligence capabilities,
enabling multi-model consensus, ensemble reasoning, adaptive model selection,
cross-model validation, and collaborative problem-solving.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from ..client.openrouter import OpenRouterClient
from ..collective_intelligence import (
    ConsensusEngine,
    EnsembleReasoner,
    AdaptiveRouter,
    CrossValidator,
    CollaborativeSolver,
    ConsensusConfig,
    ConsensusStrategy,
    AgreementLevel,
    TaskContext,
    TaskType,
    ModelInfo,
    ProcessingResult,
    ModelProvider,
    get_lifecycle_manager
)
from ..collective_intelligence.base import ModelCapability
# Import shared MCP instance from registry to prevent duplicate registration
from ..mcp_registry import mcp
from ..utils.token_counter import count_message_tokens

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
        self,
        task: TaskContext,
        model_id: str,
        **kwargs
    ) -> ProcessingResult:
        """Process a task using the specified model."""
        start_time = datetime.now()

        try:
            # Prepare messages for the model
            messages = [
                {"role": "user", "content": task.content}
            ]

            # Add system message if requirements specify behavior
            if task.requirements.get("system_prompt"):
                messages.insert(0, {
                    "role": "system",
                    "content": task.requirements["system_prompt"]
                })

            # Extract temperature from task requirements or kwargs, with fallback to default
            temperature = task.requirements.get("temperature") or kwargs.get("temperature", 0.7)

            # Call OpenRouter API
            response = await self.client.chat_completion(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=kwargs.get("max_tokens"),
                stream=False
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
                    "response_metadata": response.get("model", {})
                }
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
                    metadata=raw_model
                )

                # Add capability estimates based on model properties
                model_info.capabilities = self._estimate_capabilities(raw_model)

                models.append(model_info)

            return models

        except Exception as e:
            logger.error(f"Failed to fetch models: {str(e)}")
            return []
    
    def _calculate_confidence(self, response: Dict[str, Any], content: str) -> float:
        """Calculate confidence score based on response characteristics."""
        # This is a simplified confidence calculation
        # In practice, this could use more sophisticated methods
        
        base_confidence = 0.7
        
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
        
        return max(0.0, min(1.0, base_confidence))
    
    async def _get_model_pricing(self, model_id: str) -> Dict[str, float]:
        """
        Get pricing information for a specific model from cache.

        Args:
            model_id: Model identifier

        Returns:
            Dictionary with 'prompt' and 'completion' cost per token
        """
        # Check if already cached
        if model_id in self._model_pricing_cache:
            return self._model_pricing_cache[model_id]

        # Fetch from model cache
        try:
            if self.client._model_cache:
                model_info = await self.client._model_cache.get_model_info(model_id)
                if model_info and "pricing" in model_info:
                    pricing = model_info["pricing"]
                    cost_data = {
                        "prompt": float(pricing.get("prompt", 0)),
                        "completion": float(pricing.get("completion", 0))
                    }
                    self._model_pricing_cache[model_id] = cost_data
                    return cost_data
        except Exception as e:
            logger.warning(f"Failed to fetch pricing for model {model_id}: {e}")

        # Fallback to conservative default
        default_pricing = {"prompt": 0.00002, "completion": 0.00002}
        self._model_pricing_cache[model_id] = default_pricing
        return default_pricing

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

        # Calculate cost: pricing is typically per 1000 tokens, so divide by 1000
        # OpenRouter pricing is per token, not per 1000
        prompt_cost = prompt_tokens * pricing["prompt"]
        completion_cost = completion_tokens * pricing["completion"]

        total_cost = prompt_cost + completion_cost

        logger.debug(
            f"Cost calculation for {model_id}: "
            f"{prompt_tokens} prompt tokens (${prompt_cost:.6f}) + "
            f"{completion_tokens} completion tokens (${completion_cost:.6f}) = "
            f"${total_cost:.6f}"
        )

        return total_cost
    
    def _extract_cost(self, pricing: Dict[str, Any]) -> float:
        """Extract cost per token from pricing information."""
        # Try to get completion cost, fallback to prompt cost
        completion_cost = pricing.get("completion")
        prompt_cost = pricing.get("prompt") 
        
        if completion_cost:
            return float(completion_cost)
        elif prompt_cost:
            return float(prompt_cost)
        else:
            return 0.00002  # Default estimate
    
    def _estimate_capabilities(self, raw_model: Dict[str, Any]) -> Dict[str, float]:
        """Estimate model capabilities based on model metadata."""
        capabilities = {}
        model_id = raw_model["id"].lower()
        
        # Reasoning capability
        if any(term in model_id for term in ["gpt-4", "claude", "o1"]):
            capabilities["reasoning"] = 0.9
        elif any(term in model_id for term in ["gpt-3.5", "llama"]):
            capabilities["reasoning"] = 0.7
        else:
            capabilities["reasoning"] = 0.5
        
        # Creativity capability
        if any(term in model_id for term in ["claude", "gpt-4"]):
            capabilities["creativity"] = 0.8
        else:
            capabilities["creativity"] = 0.6
        
        # Code capability
        if any(term in model_id for term in ["code", "codestral", "deepseek"]):
            capabilities["code"] = 0.9
        elif any(term in model_id for term in ["gpt-4", "claude"]):
            capabilities["code"] = 0.8
        else:
            capabilities["code"] = 0.5
        
        # Accuracy capability
        if any(term in model_id for term in ["gpt-4", "claude", "o1"]):
            capabilities["accuracy"] = 0.9
        else:
            capabilities["accuracy"] = 0.7
        
        return capabilities


# Pydantic models for MCP tool inputs

class CollectiveChatRequest(BaseModel):
    """Request for collective chat completion."""
    prompt: str = Field(..., description="The prompt to process collectively")
    models: Optional[List[str]] = Field(None, description="Specific models to use (optional)")
    strategy: str = Field("majority_vote", description="Consensus strategy: majority_vote, weighted_average, confidence_threshold")
    min_models: int = Field(3, description="Minimum number of models to use")
    max_models: int = Field(5, description="Maximum number of models to use")
    temperature: float = Field(0.7, description="Sampling temperature")
    system_prompt: Optional[str] = Field(None, description="System prompt for all models")


class EnsembleReasoningRequest(BaseModel):
    """Request for ensemble reasoning."""
    problem: str = Field(..., description="Problem to solve with ensemble reasoning")
    task_type: str = Field("reasoning", description="Type of task: reasoning, analysis, creative, factual, code_generation")
    decompose: bool = Field(True, description="Whether to decompose the problem into subtasks")
    models: Optional[List[str]] = Field(None, description="Specific models to use (optional)")
    temperature: float = Field(0.7, description="Sampling temperature")


class AdaptiveModelRequest(BaseModel):
    """Request for adaptive model selection."""
    query: str = Field(..., description="Query for adaptive model selection")
    task_type: str = Field("reasoning", description="Type of task")
    performance_requirements: Optional[Dict[str, float]] = Field(None, description="Performance requirements")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Task constraints")


class CrossValidationRequest(BaseModel):
    """Request for cross-model validation."""
    content: str = Field(..., description="Content to validate across models")
    validation_criteria: Optional[List[str]] = Field(None, description="Specific validation criteria")
    models: Optional[List[str]] = Field(None, description="Models to use for validation")
    threshold: float = Field(0.7, description="Validation threshold")


class CollaborativeSolvingRequest(BaseModel):
    """Request for collaborative problem solving."""
    problem: str = Field(..., description="Problem to solve collaboratively")
    requirements: Optional[Dict[str, Any]] = Field(None, description="Problem requirements")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Problem constraints")
    max_iterations: int = Field(3, description="Maximum number of iteration rounds")
    models: Optional[List[str]] = Field(None, description="Specific models to use")


def get_openrouter_client() -> OpenRouterClient:
    """Get configured OpenRouter client."""
    return OpenRouterClient.from_env()


def create_task_context(
    content: str, 
    task_type: str = "reasoning",
    requirements: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None
) -> TaskContext:
    """Create a TaskContext from request parameters."""
    try:
        task_type_enum = TaskType(task_type.lower())
    except ValueError:
        task_type_enum = TaskType.REASONING
    
    return TaskContext(
        task_type=task_type_enum,
        content=content,
        requirements=requirements or {},
        constraints=constraints or {}
    )


async def _collective_chat_completion_impl(request: CollectiveChatRequest) -> Dict[str, Any]:
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
        # Setup - get_openrouter_client() is synchronous, NOT async
        client = get_openrouter_client()
        model_provider = OpenRouterModelProvider(client)

        # Get lifecycle manager and configure it with temperature parameter
        lifecycle_manager = await get_lifecycle_manager()
        lifecycle_manager.configure(model_provider)

        # Configure consensus engine
        try:
            strategy = ConsensusStrategy(request.strategy.lower())
        except ValueError:
            strategy = ConsensusStrategy.MAJORITY_VOTE

        config = ConsensusConfig(
            strategy=strategy,
            min_models=request.min_models,
            max_models=request.max_models,
            timeout_seconds=60.0
        )

        # Get singleton consensus engine from lifecycle manager
        consensus_engine = await lifecycle_manager.get_consensus_engine(config)

        # Create task context
        requirements = {
            "temperature": request.temperature  # Wire temperature to requirements
        }
        if request.system_prompt:
            requirements["system_prompt"] = request.system_prompt
        if request.models:
            requirements["preferred_models"] = request.models  # Wire models to requirements

        task = create_task_context(
            content=request.prompt,
            requirements=requirements
        )

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
                    "confidence": resp.result.confidence
                }
                for resp in result.model_responses
            ],
            "strategy_used": result.strategy_used.value,
            "processing_time": result.processing_time,
            "quality_metrics": {
                "accuracy": result.quality_metrics.accuracy,
                "consistency": result.quality_metrics.consistency,
                "completeness": result.quality_metrics.completeness,
                "overall_score": result.quality_metrics.overall_score()
            }
        }

    except Exception as e:
        logger.error(f"Collective chat completion failed: {str(e)}")
        raise


@mcp.tool()
async def collective_chat_completion(request: CollectiveChatRequest) -> Dict[str, Any]:
    """MCP tool wrapper for collective chat completion."""
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
        # Setup - get_openrouter_client() is synchronous
        client = get_openrouter_client()
        model_provider = OpenRouterModelProvider(client)

        # Get lifecycle manager and configure it
        lifecycle_manager = await get_lifecycle_manager()
        lifecycle_manager.configure(model_provider)

        # Get singleton ensemble reasoner from lifecycle manager
        ensemble_reasoner = await lifecycle_manager.get_ensemble_reasoner()

        # Create task context with temperature and models
        requirements = {
            "temperature": request.temperature  # Wire temperature
        }
        if request.models:
            requirements["preferred_models"] = request.models  # Wire models

        task = create_task_context(
            content=request.problem,
            task_type=request.task_type,
            requirements=requirements
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
                    "success": subtask.success
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
                "completeness": result.overall_quality.completeness
            },
            "processing_time": result.total_time,
            "strategy_used": result.decomposition_strategy.value,
            "success_rate": result.success_rate,
            "total_cost": result.total_cost
        }

    except Exception as e:
        logger.error(f"Ensemble reasoning failed: {str(e)}")
        raise


@mcp.tool()
async def ensemble_reasoning(request: EnsembleReasoningRequest) -> Dict[str, Any]:
    """MCP tool wrapper for ensemble reasoning."""
    return await _ensemble_reasoning_impl(request)


async def _adaptive_model_selection_impl(request: AdaptiveModelRequest) -> Dict[str, Any]:
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
        # Setup - get_openrouter_client() is synchronous
        client = get_openrouter_client()
        model_provider = OpenRouterModelProvider(client)

        # Get lifecycle manager and configure it
        lifecycle_manager = await get_lifecycle_manager()
        lifecycle_manager.configure(model_provider)

        # Get singleton adaptive router from lifecycle manager
        adaptive_router = await lifecycle_manager.get_adaptive_router()

        # Create task context with performance requirements
        requirements = {}
        if request.performance_requirements:
            requirements.update(request.performance_requirements)

        task = create_task_context(
            content=request.query,
            task_type=request.task_type,
            requirements=requirements,
            constraints=request.constraints
        )

        # Perform adaptive routing - NO async with (singleton managed by lifecycle)
        decision = await adaptive_router.process(task)

        return {
            "selected_model": decision.selected_model_id,
            "selection_reasoning": decision.justification,
            "confidence": decision.confidence_score,
            "alternative_models": [
                {
                    "model": alt[0],
                    "score": alt[1]
                }
                for alt in decision.alternative_models[:3]  # Top 3 alternatives
            ],
            "routing_metrics": {
                "expected_performance": decision.expected_performance,
                "strategy_used": decision.strategy_used.value,
                "total_candidates": decision.metadata.get("total_candidates", 0)
            },
            "selection_time": decision.routing_time
        }

    except Exception as e:
        logger.error(f"Adaptive model selection failed: {str(e)}")
        raise


@mcp.tool()
async def adaptive_model_selection(request: AdaptiveModelRequest) -> Dict[str, Any]:
    """MCP tool wrapper for adaptive model selection."""
    return await _adaptive_model_selection_impl(request)


async def _cross_model_validation_impl(request: CrossValidationRequest) -> Dict[str, Any]:
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
        - consensus_issues: Issues found by multiple models
        - model_validations: Individual validation results
        - recommendations: Suggested improvements

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
        # Setup - get_openrouter_client() is synchronous
        client = get_openrouter_client()
        model_provider = OpenRouterModelProvider(client)

        # Get lifecycle manager and configure it
        lifecycle_manager = await get_lifecycle_manager()
        lifecycle_manager.configure(model_provider)

        # Get singleton cross validator from lifecycle manager
        cross_validator = await lifecycle_manager.get_cross_validator()

        # Create a dummy result to validate
        dummy_result = ProcessingResult(
            task_id="validation_task",
            model_id="content_to_validate",
            content=request.content,
            confidence=1.0
        )

        # Create task context for validation with criteria and models
        requirements = {
            "validation_threshold": request.threshold
        }
        if request.validation_criteria:
            requirements["validation_criteria"] = request.validation_criteria
        if request.models:
            requirements["preferred_models"] = request.models  # Wire models

        task = create_task_context(
            content=request.content,
            task_type="analysis",
            requirements=requirements
        )

        # Perform cross-validation - NO async with (singleton managed by lifecycle)
        result = await cross_validator.process(dummy_result, task)

        return {
            "validation_result": "VALID" if result.is_valid else "INVALID",
            "validation_score": result.validation_confidence,
            "validation_issues": [
                {
                    "criteria": issue.criteria.value,
                    "severity": issue.severity.value,
                    "description": issue.description,
                    "suggestion": issue.suggestion,
                    "confidence": issue.confidence
                }
                for issue in result.validation_report.issues
            ],
            "model_validations": [
                {
                    "model": validation.validator_model_id,
                    "criteria": validation.criteria.value,
                    "issues_found": len(validation.validation_issues)
                }
                for validation in result.validation_report.individual_validations
            ],
            "recommendations": result.improvement_suggestions,
            "confidence": result.validation_confidence,
            "processing_time": result.processing_time,
            "quality_metrics": {
                "overall_score": result.quality_metrics.overall_score(),
                "accuracy": result.quality_metrics.accuracy,
                "consistency": result.quality_metrics.consistency
            }
        }

    except Exception as e:
        logger.error(f"Cross-model validation failed: {str(e)}")
        raise


@mcp.tool()
async def cross_model_validation(request: CrossValidationRequest) -> Dict[str, Any]:
    """MCP tool wrapper for cross-model validation."""
    return await _cross_model_validation_impl(request)


async def _collaborative_problem_solving_impl(request: CollaborativeSolvingRequest) -> Dict[str, Any]:
    """
    Solve complex problems through collaborative multi-model interaction.
    
    This tool orchestrates multiple models to work together on complex problems,
    with models building on each other's contributions through iterative refinement.
    
    Args:
        request: Collaborative problem solving request
        
    Returns:
        Dictionary containing:
        - final_solution: The collaborative solution
        - solution_iterations: Step-by-step solution development
        - model_contributions: Individual model contributions
        - collaboration_quality: Quality metrics for collaboration
        - convergence_metrics: How the solution evolved
        
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
        # Setup - get_openrouter_client() is synchronous
        client = get_openrouter_client()
        model_provider = OpenRouterModelProvider(client)

        # Get lifecycle manager and configure it
        lifecycle_manager = await get_lifecycle_manager()
        lifecycle_manager.configure(model_provider)

        # Get singleton collaborative solver from lifecycle manager
        collaborative_solver = await lifecycle_manager.get_collaborative_solver()

        # Create task context with max_iterations and models
        requirements = request.requirements or {}
        requirements["max_iterations"] = request.max_iterations  # Wire max_iterations
        if request.models:
            requirements["preferred_models"] = request.models  # Wire models

        task = create_task_context(
            content=request.problem,
            requirements=requirements,
            constraints=request.constraints
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
                "completeness": result.quality_assessment.completeness
            },
            "component_contributions": result.component_contributions,
            "confidence": result.confidence_score,
            "improvement_suggestions": result.improvement_suggestions,
            "processing_time": result.total_processing_time,
            "session_id": result.session.session_id,
            "strategy_used": result.session.strategy.value,
            "components_used": result.session.components_used
        }

    except Exception as e:
        logger.error(f"Collaborative problem solving failed: {str(e)}")
        raise


@mcp.tool()
async def collaborative_problem_solving(request: CollaborativeSolvingRequest) -> Dict[str, Any]:
    """MCP tool wrapper for collaborative problem solving."""
    return await _collaborative_problem_solving_impl(request)