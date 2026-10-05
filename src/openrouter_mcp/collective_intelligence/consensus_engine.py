"""
Multi-Model Consensus Engine

This module implements a consensus mechanism that aggregates responses from multiple
AI models to produce more reliable and accurate results through collective decision-making.
"""

import asyncio
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from time import perf_counter
from typing import Any, Optional

from ..config.constants import ConsensusDefaults, PricingDefaults
from ..utils.async_utils import raise_first_fatal_result
from ..utils.token_counter import count_tokens
from .base import (
    CollectiveIntelligenceComponent,
    ModelCapability,
    ModelInfo,
    ModelProvider,
    ProcessingResult,
    QualityMetrics,
    TaskContext,
    build_quality_metrics,
    require_complete_text,
)
from .operational_controls import OperationalConfig, init_operational_controls
from .semantic_similarity import ResponseGrouper, SemanticSimilarityCalculator

logger = logging.getLogger(__name__)


class QuotaExceededError(RuntimeError):
    """Observed provider usage exceeded the request budget."""


class ConsensusStrategy(Enum):
    """Strategies for building consensus among models."""

    MAJORITY_VOTE = "majority_vote"
    WEIGHTED_AVERAGE = "weighted_average"
    CONFIDENCE_THRESHOLD = "confidence_threshold"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    EXPERT_SELECTION = "expert_selection"


class AgreementLevel(Enum):
    """Levels of agreement among models."""

    UNANIMOUS = "unanimous"  # 100% agreement
    HIGH_CONSENSUS = "high_consensus"  # 80%+ agreement
    MODERATE_CONSENSUS = "moderate_consensus"  # 60%+ agreement
    LOW_CONSENSUS = "low_consensus"  # 40%+ agreement
    NO_CONSENSUS = "no_consensus"  # <40% agreement


@dataclass
class ConsensusConfig:
    """Configuration for consensus building."""

    strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY_VOTE
    min_models: int = ConsensusDefaults.MIN_MODELS
    max_models: int = ConsensusDefaults.MAX_MODELS
    confidence_threshold: float = ConsensusDefaults.CONFIDENCE_THRESHOLD
    agreement_threshold: float = ConsensusDefaults.AGREEMENT_THRESHOLD
    similarity_threshold: float = ConsensusDefaults.SIMILARITY_THRESHOLD
    timeout_seconds: float = ConsensusDefaults.TIMEOUT_SECONDS
    retry_attempts: int = ConsensusDefaults.RETRY_ATTEMPTS
    model_weights: dict[str, float] = field(default_factory=dict)
    exclude_models: set[str] = field(default_factory=set)
    operational_config: Optional[OperationalConfig] = None


@dataclass
class ModelResponse:
    """Response from a single model in consensus building."""

    model_id: str
    result: ProcessingResult
    weight: float = 1.0
    reliability_score: float = 1.0


@dataclass
class ConsensusResult:
    """Result of consensus building process."""

    task_id: str
    consensus_content: str
    agreement_level: AgreementLevel
    confidence_score: float
    participating_models: list[str]
    model_responses: list[ModelResponse]
    strategy_used: ConsensusStrategy
    processing_time: float
    quality_metrics: QualityMetrics
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class ConsensusEngine(CollectiveIntelligenceComponent):
    """
    Multi-model consensus engine that aggregates responses from multiple AI models
    to produce more reliable and accurate results.
    """

    def __init__(
        self, model_provider: ModelProvider, config: Optional[ConsensusConfig] = None
    ):
        super().__init__(model_provider)
        self.config = config or ConsensusConfig()

        # Initialize operational controls
        controls = init_operational_controls(self.config.operational_config)
        self.concurrency_limiter = controls.concurrency_limiter
        self.quota_tracker = controls.quota_tracker
        self.failure_controller = controls.failure_controller
        self.storage_manager = controls.storage_manager
        self.cancellation_manager = controls.cancellation_manager
        self.operational_config = controls.config

        self.model_reliability: dict[str, float] = {}

        # Initialize semantic similarity components
        self.similarity_calculator = SemanticSimilarityCalculator()
        self.response_grouper = ResponseGrouper(
            similarity_threshold=self.config.similarity_threshold,
            calculator=self.similarity_calculator,
        )

    @property
    def consensus_history(self) -> list[ConsensusResult]:
        """Get consensus history as a list for backward compatibility."""
        return self.storage_manager.get_items()

    @consensus_history.setter
    def consensus_history(self, value: list[ConsensusResult]) -> None:
        """Set consensus history for backward compatibility."""
        self.storage_manager.replace_items(value, id_prefix="consensus")

    async def process(self, task: TaskContext, **kwargs: Any) -> ConsensusResult:
        """
        Build consensus among multiple models for the given task.

        Args:
            task: The task to process
            **kwargs: Additional configuration options

        Returns:
            ConsensusResult containing the consensus and metadata

        Raises:
            RuntimeError: If quota exceeded or operational limits hit
            ValueError: If insufficient valid responses
            asyncio.CancelledError: If execution cancelled due to failures
        """
        start_time = perf_counter()
        request_id = task.task_id

        # Acquire task execution slot
        if not await self.concurrency_limiter.acquire_task_slot(request_id):
            raise RuntimeError(
                f"Failed to acquire execution slot for {request_id} - system at capacity"
            )

        try:
            # Check circuit breaker
            if not await self.failure_controller.check_circuit_breaker(
                "consensus_engine"
            ):
                raise RuntimeError(
                    "Circuit breaker open for ConsensusEngine - too many recent failures"
                )

            # Select models for consensus
            models = await self._select_models(task)
            logger.info(f"Selected {len(models)} models for consensus: {models}")

            # Each provider call reserves its own quota exactly once.
            # Get responses from all models with cancellation support
            required_models = kwargs.get("min_models", self.config.min_models)
            if (
                type(required_models) is not int
                or not 1 <= required_models <= self.config.max_models
            ):
                raise ValueError(
                    "min_models must be positive and must not exceed max_models"
                )
            if len(models) < required_models:
                raise ValueError(
                    "Insufficient responses for consensus: "
                    f"only {len(models)} available models, need {required_models}"
                )
            model_responses = await self._get_model_responses(
                task, models, request_id, min_models=required_models
            )

            # Build consensus
            consensus_result = await self._build_consensus(task, model_responses)

            # Update metrics and history with TTL management
            processing_time = perf_counter() - start_time
            consensus_result.processing_time = processing_time

            self._update_model_reliability(model_responses, consensus_result)
            await self.storage_manager.add_item(request_id, consensus_result)

            # Record success for circuit breaker
            self.failure_controller.record_circuit_breaker_success("consensus_engine")

            logger.info(
                f"Consensus completed: {consensus_result.agreement_level.value}, "
                f"confidence: {consensus_result.confidence_score:.3f}"
            )

            return consensus_result

        except asyncio.CancelledError:
            logger.warning(f"Consensus building cancelled for {request_id}")
            self.failure_controller.record_circuit_breaker_failure("consensus_engine")
            raise

        except Exception as e:
            logger.exception(f"Consensus building failed for {request_id}: {e!s}")

            # Record failure and check if we should cancel pending tasks
            should_cancel = await self.failure_controller.record_failure(
                request_id,
                str(e),
                is_critical=isinstance(e, (RuntimeError, ValueError)),
            )

            if should_cancel:
                cancelled = await self.cancellation_manager.cancel_all_tasks(
                    request_id, f"Cancelling due to failure: {e!s}"
                )
                logger.info(f"Cancelled {cancelled} pending tasks for {request_id}")

            self.failure_controller.record_circuit_breaker_failure("consensus_engine")
            raise

        finally:
            # Always release the execution slot
            self.concurrency_limiter.release_task_slot(request_id)
            # Reset quota tracking for this request
            self.quota_tracker.reset_request(request_id)

    async def _select_models(self, task: TaskContext) -> list[str]:
        """Select appropriate models for consensus building."""
        available_models = await self.model_provider.get_available_models()
        preferred = task.requirements.get("preferred_models")

        # Filter excluded models
        eligible_models = [
            model
            for model in available_models
            if model.model_id not in self.config.exclude_models
            and (not preferred or model.model_id in preferred)
        ]
        eligible_models = list(
            {model.model_id: model for model in eligible_models}.values()
        )

        # Sort by relevance to task type and reliability
        scored_models = []
        for model in eligible_models:
            relevance_score = self._calculate_model_relevance(model, task)
            reliability_score = self.model_reliability.get(model.model_id, 1.0)
            total_score = relevance_score * reliability_score
            scored_models.append((model.model_id, total_score))

        # Select top models within configured limits
        scored_models.sort(key=lambda x: x[1], reverse=True)
        selected_count = min(
            max(self.config.min_models, len(scored_models)), self.config.max_models
        )

        return [model_id for model_id, _ in scored_models[:selected_count]]

    def _calculate_model_relevance(self, model: ModelInfo, task: TaskContext) -> float:
        """Calculate how relevant a model is for the given task."""
        # This is a simplified relevance calculation
        # In practice, this would use more sophisticated matching
        base_score = 0.5

        # Boost score based on task type and model capabilities
        if hasattr(model, "capabilities"):
            task_type_mapping = {
                "reasoning": ModelCapability.REASONING,
                "creative": ModelCapability.CREATIVITY,
                "factual": ModelCapability.ACCURACY,
                "code_generation": ModelCapability.CODE,
            }

            relevant_capability = task_type_mapping.get(task.task_type.value)
            if relevant_capability and relevant_capability in model.capabilities:
                base_score += model.capabilities[relevant_capability] * 0.5

        return min(1.0, base_score)

    async def _reconcile_quota_usage(
        self,
        request_id: str,
        model_id: str,
        result: ProcessingResult,
        estimated_tokens: int,
        estimated_cost: float,
    ) -> None:
        """Reconcile estimated quota usage with a model's actual usage."""
        if result.tokens_used > 0 or result.cost > 0:
            actual_token_diff = result.tokens_used - estimated_tokens
            actual_cost_diff = result.cost - estimated_cost

            if actual_token_diff != 0 or actual_cost_diff != 0:
                can_proceed, reason = await self.quota_tracker.reconcile_usage(
                    request_id, tokens=actual_token_diff, cost=actual_cost_diff
                )
                if not can_proceed:
                    raise QuotaExceededError(reason)
                logger.debug(
                    f"Updated quota for {model_id}: "
                    f"token_diff={actual_token_diff}, cost_diff=${actual_cost_diff:.6f}"
                )

    async def _get_model_responses(
        self,
        task: TaskContext,
        model_ids: list[str],
        request_id: str,
        *,
        min_models: int | None = None,
    ) -> list[ModelResponse]:
        """Get responses from all selected models with concurrency control."""

        async def get_single_response(model_id: str) -> Optional[ModelResponse]:
            # Acquire model API slot
            if not await self.concurrency_limiter.acquire_model_slot():
                logger.warning(f"Failed to acquire model slot for {model_id}")
                return None

            api_task = None
            try:
                # Estimate tokens for this specific API call using tiktoken
                estimated_tokens = count_tokens(task.content, model_id=model_id)

                # Conservative cost estimate - will be updated with actual cost from response
                estimated_cost_per_token = PricingDefaults.ESTIMATED_TOKEN_PRICE
                estimated_cost = estimated_tokens * estimated_cost_per_token

                # Check quota for this specific API call
                can_proceed, reason = await self.quota_tracker.check_and_increment(
                    request_id, tokens=estimated_tokens, cost=estimated_cost
                )
                if not can_proceed:
                    logger.warning(f"Quota exceeded for {model_id}: {reason}")
                    return None

                # Create the API call task
                api_task = asyncio.create_task(
                    self.model_provider.process_task(task, model_id)
                )

                # Register for cancellation
                await self.cancellation_manager.register_task(request_id, api_task)

                # Wait with timeout
                result = await asyncio.wait_for(
                    api_task, timeout=self.config.timeout_seconds
                )

                # Update quota tracker with actual costs from response
                # The result now contains real token counts and costs
                await self._reconcile_quota_usage(
                    request_id,
                    model_id,
                    result,
                    estimated_tokens,
                    estimated_cost,
                )
                require_complete_text(result)

                weight = self.config.model_weights.get(model_id, 1.0)
                reliability = self.model_reliability.get(model_id, 1.0)

                return ModelResponse(
                    model_id=model_id,
                    result=result,
                    weight=weight,
                    reliability_score=reliability,
                )

            except QuotaExceededError:
                await self.cancellation_manager.cancel_all_tasks(
                    request_id, "Observed usage exceeded quota"
                )
                raise

            except asyncio.CancelledError:
                logger.info(f"Model {model_id} call cancelled")
                return None

            except asyncio.TimeoutError:
                logger.warning(
                    f"Model {model_id} timed out after {self.config.timeout_seconds}s"
                )
                if api_task and not api_task.done():
                    api_task.cancel()
                return None

            except Exception as e:
                logger.warning(f"Model {model_id} failed to respond: {e!s}")
                return None

            finally:
                # Always release model slot and unregister task
                self.concurrency_limiter.release_model_slot()
                if api_task:
                    await self.cancellation_manager.unregister_task(
                        request_id, api_task
                    )

        # Execute all model calls with controlled concurrency
        tasks = [get_single_response(model_id) for model_id in model_ids]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        raise_first_fatal_result(responses)
        for response in responses:
            if isinstance(response, QuotaExceededError):
                raise response

        # Filter out failed responses
        valid_responses = [
            response
            for response in responses
            if isinstance(response, ModelResponse) and response is not None
        ]

        logger.info(f"Got {len(valid_responses)}/{len(model_ids)} valid responses")

        required_models = self.config.min_models if min_models is None else min_models
        if len(valid_responses) < required_models:
            raise ValueError(
                f"Insufficient responses for consensus: got {len(valid_responses)}, "
                f"need at least {required_models}"
            )

        return valid_responses

    async def _build_consensus(
        self, task: TaskContext, responses: list[ModelResponse]
    ) -> ConsensusResult:
        """Build consensus from model responses using the configured strategy."""
        strategy_dispatch = {
            ConsensusStrategy.MAJORITY_VOTE: self._majority_vote_consensus,
            ConsensusStrategy.WEIGHTED_AVERAGE: self._weighted_average_consensus,
            ConsensusStrategy.CONFIDENCE_THRESHOLD: self._confidence_threshold_consensus,
        }
        handler = strategy_dispatch.get(
            self.config.strategy, self._majority_vote_consensus
        )
        return handler(task, responses)

    def _build_consensus_result(
        self,
        task: TaskContext,
        responses: list[ModelResponse],
        selected_response: ModelResponse,
        agreement_level: AgreementLevel,
        confidence_score: float,
        quality_metrics: QualityMetrics,
    ) -> ConsensusResult:
        """Build the result envelope shared by consensus strategies."""
        return ConsensusResult(
            task_id=task.task_id,
            consensus_content=selected_response.result.content,
            agreement_level=agreement_level,
            confidence_score=confidence_score,
            participating_models=[response.model_id for response in responses],
            model_responses=responses,
            strategy_used=self.config.strategy,
            processing_time=0.0,
            quality_metrics=quality_metrics,
            metadata={"quality_evaluation": "not_evaluated"},
        )

    def _majority_vote_consensus(
        self, task: TaskContext, responses: list[ModelResponse]
    ) -> ConsensusResult:
        """Build consensus using majority vote strategy."""

        # Group similar responses (simplified approach)
        response_groups = self._group_similar_responses(responses)

        # Find the group with highest total weight
        best_group = max(response_groups, key=lambda g: sum(r.weight for r in g))

        # Calculate agreement level
        total_weight = sum(r.weight for r in responses)
        consensus_weight = sum(r.weight for r in best_group)
        agreement_ratio = consensus_weight / total_weight

        agreement_level = self._calculate_agreement_level(agreement_ratio)

        # Select best response from winning group
        best_response = max(
            best_group, key=lambda r: r.result.confidence * r.reliability_score
        )

        # Calculate consensus confidence
        consensus_confidence = self._calculate_consensus_confidence(
            best_group, responses
        )

        # Calculate quality metrics
        quality_metrics = self._calculate_quality_metrics(best_group, responses)

        return self._build_consensus_result(
            task,
            responses,
            best_response,
            agreement_level,
            consensus_confidence,
            quality_metrics,
        )

    def _weighted_average_consensus(
        self, task: TaskContext, responses: list[ModelResponse]
    ) -> ConsensusResult:
        """Build consensus using weighted average strategy."""
        # This is a simplified implementation
        # In practice, this would need semantic averaging

        total_weight = sum(r.weight * r.reliability_score for r in responses)

        if total_weight == 0:
            raise ValueError("Total weight is zero, cannot compute weighted average")

        # For now, select the response with highest weighted confidence
        best_response = max(
            responses,
            key=lambda r: r.result.confidence * r.weight * r.reliability_score,
        )

        # Calculate average confidence
        avg_confidence = (
            sum(r.result.confidence * r.weight * r.reliability_score for r in responses)
            / total_weight
        )

        quality_metrics = self._calculate_quality_metrics(responses, responses)

        return self._build_consensus_result(
            task,
            responses,
            best_response,
            AgreementLevel.MODERATE_CONSENSUS,
            avg_confidence,
            quality_metrics,
        )

    def _confidence_threshold_consensus(
        self, task: TaskContext, responses: list[ModelResponse]
    ) -> ConsensusResult:
        """Build consensus using confidence threshold strategy."""

        # Filter responses by confidence threshold
        high_confidence_responses = [
            r
            for r in responses
            if r.result.confidence >= self.config.confidence_threshold
        ]

        if not high_confidence_responses:
            # Fall back to best available response
            high_confidence_responses = [
                max(responses, key=lambda r: r.result.confidence)
            ]

        # Use majority vote among high-confidence responses
        return self._majority_vote_consensus(task, high_confidence_responses)

    def _group_similar_responses(
        self, responses: list[ModelResponse]
    ) -> list[list[ModelResponse]]:
        """
        Group similar responses together using semantic similarity.

        This method replaces the old length-based heuristic with actual semantic
        similarity detection, enabling better consensus by grouping responses that
        convey the same meaning even with different formatting or phrasing.

        Args:
            responses: List of model responses to group

        Returns:
            List of groups, where each group contains semantically similar responses
        """
        if not responses:
            return []

        if len(responses) == 1:
            return [responses]

        # Extract response texts
        texts = [r.result.content for r in responses]

        # Group responses using semantic similarity
        group_indices = self.response_grouper.group_responses(texts)

        # Convert index groups back to ModelResponse groups
        groups = []
        for index_group in group_indices:
            response_group = [responses[idx] for idx in index_group]
            groups.append(response_group)

        # Log grouping results for transparency
        logger.info(
            f"Grouped {len(responses)} responses into {len(groups)} semantic groups "
            f"(threshold={self.config.similarity_threshold})"
        )
        for i, group in enumerate(groups):
            logger.debug(
                f"Group {i+1}: {len(group)} responses from models: "
                f"{[r.model_id for r in group]}"
            )

        return groups

    def _calculate_agreement_level(self, agreement_ratio: float) -> AgreementLevel:
        """Calculate agreement level based on consensus ratio."""
        if agreement_ratio >= 1.0:
            return AgreementLevel.UNANIMOUS
        if agreement_ratio >= 0.8:
            return AgreementLevel.HIGH_CONSENSUS
        if agreement_ratio >= 0.6:
            return AgreementLevel.MODERATE_CONSENSUS
        if agreement_ratio >= 0.4:
            return AgreementLevel.LOW_CONSENSUS
        return AgreementLevel.NO_CONSENSUS

    def _calculate_consensus_confidence(
        self, consensus_group: list[ModelResponse], all_responses: list[ModelResponse]
    ) -> float:
        """Calculate confidence score for the consensus."""

        if not consensus_group:
            return 0.0

        # Average confidence of consensus group
        group_confidence = statistics.mean(r.result.confidence for r in consensus_group)

        # Weight by group size relative to total
        size_weight = len(consensus_group) / len(all_responses)

        # Weight by reliability scores
        reliability_weight = statistics.mean(
            r.reliability_score for r in consensus_group
        )

        return group_confidence * size_weight * reliability_weight

    def _calculate_quality_metrics(
        self, consensus_group: list[ModelResponse], all_responses: list[ModelResponse]
    ) -> QualityMetrics:
        """Calculate quality metrics for the consensus."""

        if not consensus_group:
            return QualityMetrics()

        # Calculate metrics based on response characteristics
        confidences = [r.result.confidence for r in consensus_group]

        accuracy = statistics.mean(confidences)
        consistency = 1.0 - (
            statistics.stdev(confidences) if len(confidences) > 1 else 0.0
        )
        completeness = min(1.0, len(consensus_group) / len(all_responses))
        relevance = accuracy  # Simplified
        confidence = statistics.mean(confidences)
        coherence = consistency  # Simplified

        metric_values = {
            "accuracy": accuracy,
            "consistency": consistency,
            "completeness": completeness,
            "relevance": relevance,
            "confidence": confidence,
            "coherence": coherence,
        }
        return build_quality_metrics(**metric_values)

    def _update_model_reliability(
        self, responses: list[ModelResponse], consensus: ConsensusResult
    ) -> None:
        """Update model reliability scores based on consensus participation."""

        for response in responses:
            current_reliability = self.model_reliability.get(response.model_id, 1.0)

            # Models that contributed to consensus get reliability boost
            if response.model_id in consensus.participating_models:
                # Small positive adjustment
                new_reliability = min(1.0, current_reliability + 0.01)
            else:
                # Small negative adjustment for non-contributing models
                new_reliability = max(0.1, current_reliability - 0.005)

            self.model_reliability[response.model_id] = new_reliability

    def get_consensus_history(
        self, limit: Optional[int] = None
    ) -> list[ConsensusResult]:
        """Get historical consensus results with TTL enforcement."""
        return self.storage_manager.get_items(limit)

    def get_model_reliability_scores(self) -> dict[str, float]:
        """Get current model reliability scores."""
        return self.model_reliability.copy()

    def get_operational_metrics(self) -> dict[str, Any]:
        """Get operational metrics and limits status."""
        return {
            "active_tasks": self.concurrency_limiter.get_active_count(),
            "at_capacity": self.concurrency_limiter.is_at_capacity(),
            "history_size": self.storage_manager.get_count(),
            **self.operational_config.limits_snapshot(),
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown the consensus engine."""
        logger.info("Shutting down ConsensusEngine...")
        await self.storage_manager.shutdown()
        # Cancel any remaining tasks
        await self.cancellation_manager.cancel_all_pending_tasks("Shutdown requested")
        logger.info("ConsensusEngine shutdown complete")
