"""
Adaptive Model Router

This module implements intelligent, real-time model selection based on task characteristics,
model performance history, current load, and optimization objectives. The router learns
from past decisions to continuously improve model selection accuracy.
"""

import asyncio
import itertools
import logging
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..runtime_thrift.metrics import get_thrift_metrics_snapshot_for_dates
from ..utils.metadata import extract_provider_from_id
from .base import (
    CollectiveIntelligenceComponent,
    ModelCapability,
    ModelInfo,
    ModelProvider,
    ProcessingResult,
    TaskContext,
    TaskType,
)

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """Strategies for model routing decisions."""

    PERFORMANCE_BASED = "performance_based"  # Select based on historical performance
    COST_OPTIMIZED = "cost_optimized"  # Minimize cost while maintaining quality
    SPEED_OPTIMIZED = "speed_optimized"  # Minimize response time
    QUALITY_OPTIMIZED = "quality_optimized"  # Maximize output quality
    LOAD_BALANCED = "load_balanced"  # Distribute load evenly
    ADAPTIVE = "adaptive"  # Dynamic strategy based on context


class OptimizationObjective(Enum):
    """Optimization objectives for routing decisions."""

    MINIMIZE_COST = "minimize_cost"
    MINIMIZE_TIME = "minimize_time"
    MAXIMIZE_QUALITY = "maximize_quality"
    MAXIMIZE_THROUGHPUT = "maximize_throughput"
    BALANCE_ALL = "balance_all"


@dataclass
class ModelPerformanceHistory:
    """Historical performance data for a model."""

    model_id: str
    task_completions: int = 0
    success_rate: float = 1.0
    avg_response_time: float = 0.0
    avg_quality_score: float = 0.0
    avg_cost: float = 0.0
    recent_response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    recent_quality_scores: deque = field(default_factory=lambda: deque(maxlen=100))
    recent_costs: deque = field(default_factory=lambda: deque(maxlen=100))
    task_type_performance: Dict[TaskType, Dict[str, float]] = field(default_factory=dict)
    capability_scores: Dict[ModelCapability, float] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)

    def update_performance(self, result: ProcessingResult, task_type: TaskType) -> None:
        """Update performance metrics with new result."""
        self.task_completions += 1
        self.recent_response_times.append(result.processing_time)
        self.recent_quality_scores.append(result.confidence)
        self.recent_costs.append(result.cost)

        # Update averages
        if self.recent_response_times:
            self.avg_response_time = statistics.mean(self.recent_response_times)
        if self.recent_quality_scores:
            self.avg_quality_score = statistics.mean(self.recent_quality_scores)
        if self.recent_costs:
            self.avg_cost = statistics.mean(self.recent_costs)

        # Update task type specific performance
        if task_type not in self.task_type_performance:
            self.task_type_performance[task_type] = {
                "response_time": 0.0,
                "quality": 0.0,
                "cost": 0.0,
                "count": 0,
            }

        perf = self.task_type_performance[task_type]
        count = perf["count"]
        perf["response_time"] = (perf["response_time"] * count + result.processing_time) / (
            count + 1
        )
        perf["quality"] = (perf["quality"] * count + result.confidence) / (count + 1)
        perf["cost"] = (perf["cost"] * count + result.cost) / (count + 1)
        perf["count"] += 1

        self.last_updated = datetime.now()


@dataclass
class ModelLoadStatus:
    """Current load status for a model."""

    model_id: str
    active_requests: int = 0
    avg_queue_time: float = 0.0
    last_request_time: Optional[datetime] = None
    availability_score: float = 1.0  # 0.0 to 1.0
    estimated_next_available: Optional[datetime] = None


@dataclass
class RoutingDecision:
    """A routing decision with justification and metadata."""

    task_id: str
    selected_model_id: str
    strategy_used: RoutingStrategy
    confidence_score: float  # Confidence in the routing decision
    expected_performance: Dict[str, float]  # Expected metrics
    alternative_models: List[Tuple[str, float]]  # Other candidates with scores
    justification: str
    routing_time: float  # Time taken to make the decision
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RoutingMetrics:
    """Metrics for evaluating routing effectiveness."""

    total_routings: int = 0
    successful_routings: int = 0
    avg_routing_time: float = 0.0
    cost_savings: float = 0.0
    time_savings: float = 0.0
    quality_improvement: float = 0.0
    strategy_performance: Dict[RoutingStrategy, Dict[str, float]] = field(default_factory=dict)
    model_utilization: Dict[str, float] = field(default_factory=dict)

    def success_rate(self) -> float:
        """Calculate routing success rate."""
        return self.successful_routings / max(self.total_routings, 1)


class ModelLoadMonitor:
    """Monitors and tracks current load for all models."""

    def __init__(self) -> None:
        self.model_loads: Dict[str, ModelLoadStatus] = {}
        self.request_history: Dict[str, deque[Dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self.monitor_lock = asyncio.Lock()

    async def register_request_start(self, model_id: str, task_id: str) -> None:
        """Register the start of a request for load tracking."""
        async with self.monitor_lock:
            if model_id not in self.model_loads:
                self.model_loads[model_id] = ModelLoadStatus(model_id=model_id)

            load_status = self.model_loads[model_id]
            load_status.active_requests += 1
            load_status.last_request_time = datetime.now()

            # Update availability based on load
            load_status.availability_score = max(0.1, 1.0 - (load_status.active_requests * 0.1))

    async def register_request_complete(
        self, model_id: str, task_id: str, processing_time: float, success: bool
    ) -> None:
        """Register the completion of a request."""
        async with self.monitor_lock:
            if model_id in self.model_loads:
                load_status = self.model_loads[model_id]
                load_status.active_requests = max(0, load_status.active_requests - 1)

                # Update queue time estimate
                self.request_history[model_id].append(
                    {
                        "timestamp": datetime.now(),
                        "processing_time": processing_time,
                        "success": success,
                    }
                )

                # Calculate average queue time from recent history
                recent_times = [r["processing_time"] for r in self.request_history[model_id]]
                if recent_times:
                    load_status.avg_queue_time = statistics.mean(recent_times)

                # Update availability
                load_status.availability_score = min(1.0, load_status.availability_score + 0.1)

    def get_load_status(self, model_id: str) -> ModelLoadStatus:
        """Get current load status for a model."""
        return self.model_loads.get(model_id, ModelLoadStatus(model_id=model_id))

    def get_all_load_statuses(self) -> Dict[str, ModelLoadStatus]:
        """Get load status for all monitored models."""
        return self.model_loads.copy()


class PerformancePredictor:
    """Predicts model performance for given tasks based on historical data."""

    def __init__(self) -> None:
        self.prediction_cache: Dict[str, Tuple[datetime, Dict[str, float]]] = {}
        self.cache_ttl = timedelta(minutes=10)

    def predict_performance(
        self,
        model_info: ModelInfo,
        task: TaskContext,
        performance_history: ModelPerformanceHistory,
    ) -> Dict[str, float]:
        """Predict expected performance metrics for a model on a task."""

        # Check cache first
        cache_key = f"{model_info.model_id}_{task.task_type.value}_{hash(task.content[:100])}"
        if cache_key in self.prediction_cache:
            cached_time, predictions = self.prediction_cache[cache_key]
            if datetime.now() - cached_time < self.cache_ttl:
                return predictions

        # Base predictions on model info
        base_response_time = model_info.response_time_avg
        base_quality = model_info.accuracy_score
        base_cost = model_info.cost_per_token * self._estimate_tokens(task.content)

        # Adjust based on historical performance
        if performance_history.task_completions > 0:
            # Use historical averages if available
            response_time = performance_history.avg_response_time
            quality = performance_history.avg_quality_score
            cost = performance_history.avg_cost

            # Check for task-specific performance
            if task.task_type in performance_history.task_type_performance:
                task_perf = performance_history.task_type_performance[task.task_type]
                response_time = task_perf["response_time"]
                quality = task_perf["quality"]
                cost = task_perf["cost"]
        else:
            # Use base model characteristics
            response_time = base_response_time
            quality = base_quality
            cost = base_cost

        # Adjust for task complexity
        complexity_factor = self._calculate_complexity_factor(task)
        response_time *= complexity_factor
        cost *= complexity_factor

        # Adjust for model capability match
        capability_match = self._calculate_capability_match(model_info, task)
        quality *= capability_match

        predictions = {
            "response_time": response_time,
            "quality": quality,
            "cost": cost,
            "success_probability": performance_history.success_rate,
        }

        # Cache the predictions
        self.prediction_cache[cache_key] = (datetime.now(), predictions)

        return predictions

    def _estimate_tokens(self, content: str) -> int:
        """Estimate token count for content."""
        # Simple word-based estimation (actual implementation would use proper tokenizer)
        return int(len(content.split()) * 1.3)

    def _calculate_complexity_factor(self, task: TaskContext) -> float:
        """Calculate complexity factor based on task characteristics."""
        base_factor = 1.0

        # Adjust for content length
        content_factor = min(2.0, 1.0 + len(task.content) / 1000.0)

        # Adjust for task type complexity
        type_factors = {
            TaskType.REASONING: 1.5,
            TaskType.CREATIVE: 1.3,
            TaskType.CODE_GENERATION: 1.4,
            TaskType.ANALYSIS: 1.2,
            TaskType.MATH: 1.3,
            TaskType.FACTUAL: 1.0,
        }

        type_factor = type_factors.get(task.task_type, 1.0)

        # Adjust for requirements complexity
        req_factor = 1.0 + len(task.requirements) * 0.1

        return base_factor * content_factor * type_factor * req_factor

    def _calculate_capability_match(self, model_info: ModelInfo, task: TaskContext) -> float:
        """Calculate how well model capabilities match task requirements."""
        # Simplified capability matching
        base_match = 0.7

        # Map task types to required capabilities
        required_capabilities = {
            TaskType.REASONING: [ModelCapability.REASONING],
            TaskType.CREATIVE: [ModelCapability.CREATIVITY],
            TaskType.CODE_GENERATION: [ModelCapability.CODE],
            TaskType.ANALYSIS: [ModelCapability.REASONING, ModelCapability.ACCURACY],
            TaskType.MATH: [ModelCapability.MATH],
            TaskType.FACTUAL: [ModelCapability.ACCURACY],
        }.get(task.task_type, [])

        if not required_capabilities:
            return base_match

        # Calculate match score
        capability_scores = []
        for cap in required_capabilities:
            if cap in model_info.capabilities:
                capability_scores.append(model_info.capabilities[cap])
            else:
                capability_scores.append(0.5)  # Default score

        match_score = statistics.mean(capability_scores) if capability_scores else base_match
        return min(1.0, base_match + match_score * 0.3)


class AdaptiveRouter(CollectiveIntelligenceComponent):
    """
    Adaptive model router that intelligently selects the best model for each task
    based on performance history, current load, and optimization objectives.
    """

    def __init__(
        self,
        model_provider: ModelProvider,
        default_strategy: RoutingStrategy = RoutingStrategy.ADAPTIVE,
        optimization_objective: OptimizationObjective = OptimizationObjective.BALANCE_ALL,
    ) -> None:
        super().__init__(model_provider)
        self.default_strategy = default_strategy
        self.optimization_objective = optimization_objective

        # Components
        self.load_monitor = ModelLoadMonitor()
        self.performance_predictor = PerformancePredictor()

        # Performance tracking
        self.model_performance_history: Dict[str, ModelPerformanceHistory] = {}
        self.routing_decisions: deque = deque(maxlen=1000)
        self.routing_metrics = RoutingMetrics()

        # Configuration
        self.config = {
            "max_concurrent_evaluations": 10,
            "decision_timeout": 5.0,
            "min_confidence_threshold": 0.6,
            "exploration_rate": 0.1,  # Rate of trying less optimal models for learning
            "performance_history_weight": 0.7,
            "load_balancing_weight": 0.3,
            "thrift_feedback_enabled": True,
            "thrift_feedback_lookback_days": 7,
            "thrift_penalty_cap": 0.35,
        }

    async def process(self, task: TaskContext, **kwargs: Any) -> RoutingDecision:
        """
        Route a task to the most appropriate model.

        Args:
            task: The task to route
            **kwargs: Additional routing options

        Returns:
            RoutingDecision with selected model and metadata
        """
        start_time = time.time()

        try:
            # Get strategy for this routing
            strategy = kwargs.get("strategy", self.default_strategy)

            # Get available models
            available_models = await self.model_provider.get_available_models()

            if not available_models:
                raise ValueError("No models available for routing")

            routing_policy = self._build_routing_policy(task)
            routing_metadata = self._build_routing_metadata(routing_policy)
            eligible_models = self._prefilter_available_models(
                available_models,
                routing_policy,
                routing_metadata,
            )
            if not eligible_models:
                raise ValueError(self._build_constraints_error_message(routing_metadata))

            thrift_feedback_context = self._get_thrift_feedback_context()

            # Evaluate all models for this task
            model_evaluations = await self._evaluate_models(
                task,
                eligible_models,
                strategy,
                thrift_feedback_context=thrift_feedback_context,
                routing_policy=routing_policy,
                routing_metadata=routing_metadata,
            )

            if not model_evaluations:
                raise ValueError(self._build_constraints_error_message(routing_metadata))

            # Select best model
            selected_model_id, confidence, alternatives = self._select_best_model(
                model_evaluations, strategy
            )
            selected_evaluation = model_evaluations[selected_model_id]
            routing_metadata["preference_matches"] = selected_evaluation.get(
                "preference_matches", []
            )

            # Create routing decision
            routing_time = time.time() - start_time
            decision = RoutingDecision(
                task_id=task.task_id,
                selected_model_id=selected_model_id,
                strategy_used=strategy,
                confidence_score=confidence,
                expected_performance=selected_evaluation["metrics"],
                alternative_models=alternatives,
                justification=self._generate_justification(
                    selected_model_id, selected_evaluation, strategy
                ),
                routing_time=routing_time,
                metadata={
                    "total_candidates": len(eligible_models),
                    "evaluation_time": routing_time,
                    "optimization_objective": self.optimization_objective.value,
                    "thrift_feedback": selected_evaluation.get("thrift_feedback"),
                    "constraints_applied": routing_metadata["constraints_applied"],
                    "constraints_unmet": routing_metadata["constraints_unmet"],
                    "filtered_candidates": routing_metadata["filtered_candidates"],
                    "performance_weights": routing_metadata["performance_weights"],
                    "preference_matches": routing_metadata["preference_matches"],
                },
            )

            # Update metrics and history
            self.routing_decisions.append(decision)
            self._update_routing_metrics(decision)

            logger.info(
                f"Routed task {task.task_id} to {selected_model_id} "
                f"(confidence: {confidence:.3f}, strategy: {strategy.value})"
            )

            return decision

        except Exception as e:
            logger.error(f"Routing failed for task {task.task_id}: {str(e)}")
            raise

    async def _evaluate_models(
        self,
        task: TaskContext,
        available_models: List[ModelInfo],
        strategy: RoutingStrategy,
        thrift_feedback_context: Optional[Dict[str, Any]] = None,
        routing_policy: Optional[Dict[str, Any]] = None,
        routing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Evaluate all available models for the given task."""

        evaluations: Dict[str, Dict[str, Any]] = {}

        # Evaluate models concurrently
        evaluation_tasks = [
            self._evaluate_single_model(
                task,
                model,
                strategy,
                thrift_feedback_context=thrift_feedback_context,
                routing_policy=routing_policy,
            )
            for model in available_models
        ]

        results = await asyncio.gather(*evaluation_tasks, return_exceptions=True)

        for model, result in zip(available_models, results):
            if isinstance(result, BaseException):
                logger.warning(f"Failed to evaluate model {model.model_id}: {str(result)}")
                continue

            if result.get("filtered"):
                if routing_metadata is not None:
                    self._record_filtered_candidate(
                        routing_metadata,
                        result.get("filter_reasons", []),
                    )
                continue

            evaluations[model.model_id] = result

        if not evaluations:
            if routing_metadata and routing_metadata.get("filtered_candidates", 0) > 0:
                return {}
            raise ValueError("No models could be evaluated")

        return evaluations

    async def _evaluate_single_model(
        self,
        task: TaskContext,
        model: ModelInfo,
        strategy: RoutingStrategy,
        thrift_feedback_context: Optional[Dict[str, Any]] = None,
        routing_policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate a single model for the given task."""

        # Get performance history
        if model.model_id not in self.model_performance_history:
            self.model_performance_history[model.model_id] = ModelPerformanceHistory(
                model_id=model.model_id
            )

        performance_history = self.model_performance_history[model.model_id]

        # Get current load status
        load_status = self.load_monitor.get_load_status(model.model_id)

        # Predict performance
        predicted_metrics = self.performance_predictor.predict_performance(
            model, task, performance_history
        )

        filter_reasons = self._get_dynamic_filter_reasons(model, predicted_metrics, routing_policy)
        if filter_reasons:
            return {
                "model": model,
                "filtered": True,
                "filter_reasons": filter_reasons,
            }

        thrift_feedback = self._build_thrift_feedback_for_model(
            model.model_id,
            thrift_feedback_context.get("metrics", {}) if thrift_feedback_context else {},
            window_start=(
                thrift_feedback_context.get("window_start") if thrift_feedback_context else None
            ),
            window_end=(
                thrift_feedback_context.get("window_end") if thrift_feedback_context else None
            ),
            lookback_days=(
                thrift_feedback_context.get("lookback_days", 0) if thrift_feedback_context else 0
            ),
        )

        # Calculate strategy-specific score
        strategy_score = self._calculate_strategy_score(
            model,
            predicted_metrics,
            load_status,
            strategy,
            thrift_feedback if routing_policy is None else thrift_feedback,
            routing_policy=routing_policy,
        )
        preference_matches = self._get_preference_matches(model, routing_policy)

        # Apply exploration factor
        if self._should_explore(model.model_id):
            exploration_bonus = 0.1
            strategy_score += exploration_bonus

        return {
            "model": model,
            "metrics": predicted_metrics,
            "load_status": load_status,
            "performance_history": performance_history,
            "thrift_feedback": thrift_feedback,
            "preference_matches": preference_matches,
            "strategy_score": strategy_score,
            "final_score": strategy_score * load_status.availability_score,
        }

    def _calculate_strategy_score(
        self,
        model: ModelInfo,
        predicted_metrics: Dict[str, float],
        load_status: ModelLoadStatus,
        strategy: RoutingStrategy,
        thrift_feedback: Optional[Dict[str, Any]] = None,
        routing_policy: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate score based on the routing strategy."""

        score_calculators = {
            RoutingStrategy.PERFORMANCE_BASED: self._score_performance_based,
            RoutingStrategy.COST_OPTIMIZED: self._score_cost_optimized,
            RoutingStrategy.SPEED_OPTIMIZED: self._score_speed_optimized,
            RoutingStrategy.QUALITY_OPTIMIZED: self._score_quality_optimized,
            RoutingStrategy.LOAD_BALANCED: self._score_load_balanced,
            RoutingStrategy.ADAPTIVE: self._score_adaptive,
        }
        calculator = score_calculators.get(strategy, self._score_adaptive)
        base_score = calculator(predicted_metrics, load_status)
        weighted_score = self._apply_performance_requirement_weights(
            base_score,
            predicted_metrics,
            load_status,
            strategy,
            routing_policy,
        )
        preferred_score = self._apply_preference_boost(
            weighted_score,
            model,
            routing_policy,
        )
        return self._apply_thrift_feedback_penalty(preferred_score, strategy, thrift_feedback)

    def _build_routing_policy(self, task: TaskContext) -> Dict[str, Any]:
        """Normalize raw task requirements/constraints into one routing policy."""
        constraints = task.constraints if isinstance(task.constraints, dict) else {}
        requirements = task.requirements if isinstance(task.requirements, dict) else {}

        hard_constraints: Dict[str, Any] = {}
        preferences: Dict[str, str] = {}

        max_cost = self._coerce_float_constraint(constraints, "max_cost")
        if max_cost is not None:
            hard_constraints["max_cost"] = max_cost

        excluded_providers = self._normalize_provider_values(constraints.get("excluded_provider"))
        if excluded_providers:
            hard_constraints["excluded_provider"] = sorted(excluded_providers)

        required_capabilities = self._normalize_required_capabilities(
            constraints.get("required_capabilities")
        )
        if required_capabilities:
            hard_constraints["required_capabilities"] = required_capabilities

        min_context_length = self._coerce_int_constraint(constraints, "min_context_length")
        if min_context_length is not None:
            hard_constraints["min_context_length"] = min_context_length

        preferred_provider = self._normalize_optional_string(constraints.get("preferred_provider"))
        if preferred_provider:
            preferences["preferred_provider"] = preferred_provider

        preferred_model_family = self._normalize_optional_string(
            constraints.get("preferred_model_family")
        )
        if preferred_model_family:
            preferences["preferred_model_family"] = preferred_model_family

        return {
            "hard_constraints": hard_constraints,
            "preferences": preferences,
            "performance_weights": self._normalize_performance_weights(requirements),
        }

    def _build_routing_metadata(self, routing_policy: Dict[str, Any]) -> Dict[str, Any]:
        """Create compact routing metadata scaffold for one decision."""
        hard_constraints = routing_policy.get("hard_constraints", {})
        preferences = routing_policy.get("preferences", {})
        constraints_applied = sorted(list(hard_constraints.keys()) + list(preferences.keys()))
        return {
            "constraints_applied": constraints_applied,
            "constraints_unmet": [],
            "filtered_candidates": 0,
            "performance_weights": routing_policy.get("performance_weights", {}),
            "preference_matches": [],
            "_filtered_reason_counts": {},
        }

    def _prefilter_available_models(
        self,
        available_models: List[ModelInfo],
        routing_policy: Dict[str, Any],
        routing_metadata: Dict[str, Any],
    ) -> List[ModelInfo]:
        """Filter candidates using model-only hard constraints."""
        survivors: List[ModelInfo] = []
        for model in available_models:
            reasons = self._get_static_filter_reasons(model, routing_policy)
            if reasons:
                self._record_filtered_candidate(routing_metadata, reasons)
                continue
            survivors.append(model)
        return survivors

    def _get_static_filter_reasons(
        self,
        model: ModelInfo,
        routing_policy: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Return hard-constraint reasons that do not require predictions."""
        if not routing_policy:
            return []

        hard_constraints = routing_policy.get("hard_constraints", {})
        reasons: List[str] = []

        excluded_providers = hard_constraints.get("excluded_provider", [])
        if excluded_providers and self._model_provider_matches(model, excluded_providers):
            reasons.append("excluded_provider")

        required_capabilities = hard_constraints.get("required_capabilities", [])
        if required_capabilities:
            missing_capabilities = [
                capability
                for capability in required_capabilities
                if model.capabilities.get(capability, 0.0) <= 0.0
            ]
            if missing_capabilities:
                reasons.append("required_capabilities")

        min_context_length = hard_constraints.get("min_context_length")
        if min_context_length is not None and model.context_length < min_context_length:
            reasons.append("min_context_length")

        return reasons

    def _get_dynamic_filter_reasons(
        self,
        model: ModelInfo,
        predicted_metrics: Dict[str, float],
        routing_policy: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Return hard-constraint reasons that depend on predicted metrics."""
        if not routing_policy:
            return []

        hard_constraints = routing_policy.get("hard_constraints", {})
        reasons: List[str] = []
        max_cost = hard_constraints.get("max_cost")
        if max_cost is not None and predicted_metrics.get("cost", 0.0) > max_cost:
            reasons.append("max_cost")
        return reasons

    def _record_filtered_candidate(
        self, routing_metadata: Dict[str, Any], reasons: List[str]
    ) -> None:
        """Track filtered candidate counts and unmet constraint classes."""
        routing_metadata["filtered_candidates"] += 1
        reason_counts = routing_metadata.setdefault("_filtered_reason_counts", {})
        for reason in reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            if reason not in routing_metadata["constraints_unmet"]:
                routing_metadata["constraints_unmet"].append(reason)

    def _build_constraints_error_message(self, routing_metadata: Dict[str, Any]) -> str:
        """Build one explicit routing failure message for hard-constraint exhaustion."""
        unmet = routing_metadata.get("constraints_unmet") or routing_metadata.get(
            "constraints_applied", []
        )
        suffix = ", ".join(unmet) if unmet else "unknown"
        return f"No models satisfy routing constraints: {suffix}"

    def _coerce_float_constraint(self, constraints: Dict[str, Any], key: str) -> Optional[float]:
        """Safely parse positive float constraint values."""
        raw_value = constraints.get(key)
        if raw_value is None:
            return None
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid routing constraint %s=%r", key, raw_value)
            return None
        return value if value > 0 else None

    def _coerce_int_constraint(self, constraints: Dict[str, Any], key: str) -> Optional[int]:
        """Safely parse positive integer constraint values."""
        raw_value = constraints.get(key)
        if raw_value is None:
            return None
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid routing constraint %s=%r", key, raw_value)
            return None
        return value if value > 0 else None

    def _normalize_provider_values(self, raw_value: Any) -> List[str]:
        """Normalize provider filters from strings or lists."""
        if raw_value is None:
            return []
        if isinstance(raw_value, str):
            candidates = [raw_value]
        elif isinstance(raw_value, (list, tuple, set)):
            candidates = list(raw_value)
        else:
            logger.warning("Ignoring invalid routing constraint excluded_provider=%r", raw_value)
            return []

        return sorted(
            {
                normalized
                for value in candidates
                if (normalized := self._normalize_optional_string(value)) is not None
            }
        )

    def _normalize_required_capabilities(self, raw_value: Any) -> List[ModelCapability]:
        """Normalize requested capabilities into enum members."""
        if raw_value is None:
            return []
        if isinstance(raw_value, (str, ModelCapability)):
            candidates = [raw_value]
        elif isinstance(raw_value, (list, tuple, set)):
            candidates = list(raw_value)
        else:
            logger.warning(
                "Ignoring invalid routing constraint required_capabilities=%r",
                raw_value,
            )
            return []

        normalized: List[ModelCapability] = []
        seen = set()
        for candidate in candidates:
            capability = self._parse_capability(candidate)
            if capability is None or capability in seen:
                continue
            normalized.append(capability)
            seen.add(capability)
        return normalized

    def _parse_capability(self, raw_value: Any) -> Optional[ModelCapability]:
        """Parse one capability token into a ModelCapability enum."""
        if isinstance(raw_value, ModelCapability):
            return raw_value

        normalized = self._normalize_optional_string(raw_value)
        if normalized is None:
            logger.warning("Ignoring invalid capability token %r", raw_value)
            return None

        for capability in ModelCapability:
            if normalized in {capability.value.lower(), capability.name.lower()}:
                return capability

        logger.warning("Ignoring unknown required capability %r", raw_value)
        return None

    def _normalize_optional_string(self, raw_value: Any) -> Optional[str]:
        """Normalize optional string values to lowercase."""
        if raw_value is None:
            return None
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip().lower()
        return normalized or None

    def _normalize_performance_weights(self, requirements: Dict[str, Any]) -> Dict[str, float]:
        """Keep only known positive performance weights and normalize them."""
        aliases = {
            "accuracy": "accuracy",
            "quality": "accuracy",
            "speed": "speed",
            "latency": "speed",
            "cost": "cost",
        }
        collected: Dict[str, float] = {}
        for raw_key, raw_value in requirements.items():
            normalized_key = aliases.get(str(raw_key).lower())
            if normalized_key is None:
                continue
            try:
                numeric_value = float(raw_value)
            except (TypeError, ValueError):
                continue
            if numeric_value <= 0:
                continue
            collected[normalized_key] = collected.get(normalized_key, 0.0) + numeric_value

        total = sum(collected.values())
        if total <= 0:
            return {}

        return {key: round(value / total, 4) for key, value in sorted(collected.items())}

    def _model_provider_matches(self, model: ModelInfo, providers: List[str]) -> bool:
        """Check whether a model matches any normalized provider token."""
        normalized_providers = {
            token
            for token in {
                self._normalize_optional_string(model.provider),
                self._normalize_optional_string(extract_provider_from_id(model.model_id).value),
            }
            if token is not None
        }
        return any(provider in normalized_providers for provider in providers)

    def _get_preference_matches(
        self,
        model: ModelInfo,
        routing_policy: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Return soft preferences matched by the candidate."""
        if not routing_policy:
            return []

        preferences = routing_policy.get("preferences", {})
        matches: List[str] = []
        preferred_provider = preferences.get("preferred_provider")
        if preferred_provider and self._model_provider_matches(model, [preferred_provider]):
            matches.append("preferred_provider")

        preferred_model_family = preferences.get("preferred_model_family")
        if preferred_model_family:
            family_haystacks = [
                model.model_id.lower(),
                model.name.lower(),
            ]
            if any(preferred_model_family in haystack for haystack in family_haystacks):
                matches.append("preferred_model_family")

        return matches

    def _apply_performance_requirement_weights(
        self,
        base_score: float,
        predicted_metrics: Dict[str, float],
        load_status: ModelLoadStatus,
        strategy: RoutingStrategy,
        routing_policy: Optional[Dict[str, Any]],
    ) -> float:
        """Override scoring when explicit performance weights are present."""
        if not routing_policy:
            return base_score

        weights = routing_policy.get("performance_weights", {})
        if not weights:
            return base_score

        if strategy not in {
            RoutingStrategy.ADAPTIVE,
            RoutingStrategy.PERFORMANCE_BASED,
        }:
            return base_score

        weighted_score = self._calculate_weighted_requirement_score(predicted_metrics, weights)
        success = predicted_metrics["success_probability"]

        if strategy == RoutingStrategy.PERFORMANCE_BASED:
            return weighted_score * success

        availability = load_status.availability_score
        return (weighted_score * 0.85 + success * 0.15) * availability

    def _calculate_weighted_requirement_score(
        self,
        predicted_metrics: Dict[str, float],
        weights: Dict[str, float],
    ) -> float:
        """Score predicted metrics using normalized bounded requirement weights."""
        bounded_metrics = {
            "accuracy": max(0.0, min(1.0, float(predicted_metrics.get("quality", 0.0) or 0.0))),
            "speed": 1.0
            / (1.0 + max(0.0, float(predicted_metrics.get("response_time", 0.0) or 0.0))),
            "cost": 1.0
            / (1.0 + (max(0.0, float(predicted_metrics.get("cost", 0.0) or 0.0)) * 1000.0)),
        }
        return sum(bounded_metrics[key] * weight for key, weight in weights.items())

    def _apply_preference_boost(
        self,
        score: float,
        model: ModelInfo,
        routing_policy: Optional[Dict[str, Any]],
    ) -> float:
        """Apply bounded soft boosts for preferred provider/family matches."""
        matches = self._get_preference_matches(model, routing_policy)
        if not matches:
            return score

        boost = min(0.35, 0.2 * len(matches))
        return score * (1.0 + boost)

    def _get_int_config(self, key: str, default: int, *, minimum: Optional[int] = None) -> int:
        """Read integer config safely with fallback and optional clamping."""
        raw_value = self.config.get(key, default)
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid adaptive-router config for %s=%r; falling back to %s",
                key,
                raw_value,
                default,
            )
            value = default

        if minimum is not None:
            value = max(minimum, value)

        return value

    def _get_float_config(
        self, key: str, default: float, *, minimum: Optional[float] = None
    ) -> float:
        """Read float config safely with fallback and optional clamping."""
        raw_value = self.config.get(key, default)
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid adaptive-router config for %s=%r; falling back to %s",
                key,
                raw_value,
                default,
            )
            value = default

        if minimum is not None:
            value = max(minimum, value)

        return value

    def _get_thrift_feedback_context(self) -> Dict[str, Any]:
        """Fetch a recent thrift snapshot once per routing decision."""
        if not self.config.get("thrift_feedback_enabled", True):
            return {
                "metrics": {},
                "window_start": None,
                "window_end": None,
                "lookback_days": 0,
            }

        lookback_days = self._get_int_config(
            "thrift_feedback_lookback_days",
            7,
            minimum=1,
        )
        window_end = datetime.now().date()
        window_start = window_end - timedelta(days=lookback_days - 1)

        try:
            metrics = get_thrift_metrics_snapshot_for_dates(
                window_start.isoformat(),
                window_end.isoformat(),
            )
        except Exception:
            logger.debug(
                "Failed to read runtime thrift feedback for adaptive router", exc_info=True
            )
            metrics = {}

        return {
            "metrics": metrics if isinstance(metrics, dict) else {},
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "lookback_days": lookback_days,
        }

    def _build_thrift_feedback_for_model(
        self,
        model_id: str,
        thrift_metrics: Dict[str, Any],
        *,
        window_start: Optional[str],
        window_end: Optional[str],
        lookback_days: int,
    ) -> Dict[str, Any]:
        """Build machine-readable thrift feedback for a single model."""
        feedback = {
            "source": "none",
            "penalty": 0.0,
            "lookback_days": max(0, int(lookback_days)),
            "window_start": window_start,
            "window_end": window_end,
            "bucket_summary": None,
        }

        if not isinstance(thrift_metrics, dict):
            return feedback

        bucket: Optional[Dict[str, Any]] = None
        source = "none"

        model_breakdown = thrift_metrics.get("cache_efficiency_by_model")
        if isinstance(model_breakdown, dict) and isinstance(model_breakdown.get(model_id), dict):
            bucket = model_breakdown[model_id]
            source = "model"
        else:
            provider_id = extract_provider_from_id(model_id).value
            provider_breakdown = thrift_metrics.get("cache_efficiency_by_provider")
            if isinstance(provider_breakdown, dict) and isinstance(
                provider_breakdown.get(provider_id), dict
            ):
                bucket = provider_breakdown[provider_id]
                source = "provider"

        if bucket is None:
            return feedback

        try:
            bucket_summary = self._summarize_thrift_bucket(bucket)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Ignoring malformed runtime thrift bucket for %s (%s feedback): %s",
                model_id,
                source,
                exc,
            )
            return feedback

        feedback["source"] = source
        feedback["bucket_summary"] = bucket_summary
        feedback["penalty"] = self._calculate_thrift_penalty(bucket_summary)
        return feedback

    def _summarize_thrift_bucket(self, bucket: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw thrift bucket counters into one compact summary."""
        observed_requests = max(0, int(bucket.get("observed_requests", 0) or 0))
        cached_prompt_tokens = max(0, int(bucket.get("cached_prompt_tokens", 0) or 0))
        cache_write_prompt_tokens = max(0, int(bucket.get("cache_write_prompt_tokens", 0) or 0))
        cache_hit_requests = max(0, int(bucket.get("cache_hit_requests", 0) or 0))
        cache_write_requests = max(0, int(bucket.get("cache_write_requests", 0) or 0))
        saved_cost_usd = round(float(bucket.get("saved_cost_usd", 0.0) or 0.0), 8)

        cache_hit_request_rate_pct = 0.0
        cache_write_request_rate_pct = 0.0
        if observed_requests > 0:
            cache_hit_request_rate_pct = round(
                (cache_hit_requests / observed_requests) * 100.0,
                2,
            )
            cache_write_request_rate_pct = round(
                (cache_write_requests / observed_requests) * 100.0,
                2,
            )

        reuse_to_write_ratio = None
        if cache_write_prompt_tokens > 0:
            reuse_to_write_ratio = round(
                cached_prompt_tokens / cache_write_prompt_tokens,
                4,
            )

        return {
            "observed_requests": observed_requests,
            "cached_prompt_tokens": cached_prompt_tokens,
            "cache_write_prompt_tokens": cache_write_prompt_tokens,
            "cache_hit_requests": cache_hit_requests,
            "cache_write_requests": cache_write_requests,
            "cache_hit_request_rate_pct": cache_hit_request_rate_pct,
            "cache_write_request_rate_pct": cache_write_request_rate_pct,
            "reuse_to_write_ratio": reuse_to_write_ratio,
            "saved_cost_usd": saved_cost_usd,
        }

    def _calculate_thrift_penalty(self, bucket_summary: Dict[str, Any]) -> float:
        """Calculate bounded penalty for cache-deadspot behavior."""
        cache_write_requests = max(0, int(bucket_summary.get("cache_write_requests", 0) or 0))
        if cache_write_requests <= 0:
            return 0.0

        cache_hit_requests = max(0, int(bucket_summary.get("cache_hit_requests", 0) or 0))
        cache_hit_request_rate_pct = max(
            0.0,
            float(bucket_summary.get("cache_hit_request_rate_pct", 0.0) or 0.0),
        )
        cache_write_request_rate_pct = max(
            0.0,
            float(bucket_summary.get("cache_write_request_rate_pct", 0.0) or 0.0),
        )
        reuse_to_write_ratio = bucket_summary.get("reuse_to_write_ratio")
        reuse_to_write_ratio = (
            0.0
            if reuse_to_write_ratio is None
            else max(
                0.0,
                float(reuse_to_write_ratio),
            )
        )

        if (
            cache_hit_request_rate_pct >= cache_write_request_rate_pct
            and reuse_to_write_ratio >= 1.0
        ):
            return 0.0

        gap_ratio = max(0.0, cache_write_request_rate_pct - cache_hit_request_rate_pct) / 100.0
        reuse_penalty = max(0.0, 1.0 - min(reuse_to_write_ratio, 1.0))
        penalty = (gap_ratio * 0.7) + (reuse_penalty * 0.3)

        if cache_hit_requests == 0:
            penalty += 0.1

        penalty_cap = self._get_float_config(
            "thrift_penalty_cap",
            0.35,
            minimum=0.0,
        )
        return round(min(penalty, penalty_cap), 4)

    def _should_apply_thrift_feedback(
        self,
        strategy: RoutingStrategy,
        thrift_feedback: Optional[Dict[str, Any]],
    ) -> bool:
        """Only cost-sensitive strategies should react to thrift deadspots."""
        if not self.config.get("thrift_feedback_enabled", True):
            return False
        if not thrift_feedback:
            return False
        if float(thrift_feedback.get("penalty", 0.0) or 0.0) <= 0.0:
            return False
        if strategy == RoutingStrategy.COST_OPTIMIZED:
            return True
        if strategy == RoutingStrategy.ADAPTIVE:
            return self.optimization_objective in {
                OptimizationObjective.MINIMIZE_COST,
                OptimizationObjective.BALANCE_ALL,
            }
        return False

    def _apply_thrift_feedback_penalty(
        self,
        score: float,
        strategy: RoutingStrategy,
        thrift_feedback: Optional[Dict[str, Any]],
    ) -> float:
        """Apply bounded thrift penalty to cost-sensitive strategy scores."""
        if not self._should_apply_thrift_feedback(strategy, thrift_feedback):
            return score

        penalty = max(0.0, float(thrift_feedback.get("penalty", 0.0) or 0.0))
        return max(0.0, score * (1.0 - penalty))

    def _score_performance_based(
        self, predicted_metrics: Dict[str, float], load_status: ModelLoadStatus
    ) -> float:
        """Prioritize models with best historical performance."""
        return predicted_metrics["quality"] * predicted_metrics["success_probability"]

    def _score_cost_optimized(
        self, predicted_metrics: Dict[str, float], load_status: ModelLoadStatus
    ) -> float:
        """Minimize cost while maintaining reasonable quality."""
        cost_score = 1.0 / max(predicted_metrics["cost"], 0.001)
        quality_threshold = 0.7
        quality_penalty = max(0, quality_threshold - predicted_metrics["quality"])
        return cost_score - quality_penalty * 2.0

    def _score_speed_optimized(
        self, predicted_metrics: Dict[str, float], load_status: ModelLoadStatus
    ) -> float:
        """Minimize response time."""
        time_score = 1.0 / max(predicted_metrics["response_time"], 0.1)
        return time_score * predicted_metrics["success_probability"]

    def _score_quality_optimized(
        self, predicted_metrics: Dict[str, float], load_status: ModelLoadStatus
    ) -> float:
        """Maximize output quality regardless of cost/time."""
        return self._score_performance_based(predicted_metrics, load_status)

    def _score_load_balanced(
        self, predicted_metrics: Dict[str, float], load_status: ModelLoadStatus
    ) -> float:
        """Distribute load evenly across models."""
        load_factor = 1.0 / max(load_status.active_requests + 1, 1)
        base_score = predicted_metrics["quality"] * predicted_metrics["success_probability"]
        return base_score * load_factor

    def _score_adaptive(
        self, predicted_metrics: Dict[str, float], load_status: ModelLoadStatus
    ) -> float:
        """Balance multiple factors based on optimization objective."""
        return self._calculate_adaptive_score(predicted_metrics, load_status)

    def _calculate_adaptive_score(
        self, predicted_metrics: Dict[str, float], load_status: ModelLoadStatus
    ) -> float:
        """Calculate adaptive score based on optimization objective."""

        quality = predicted_metrics["quality"]
        speed = 1.0 / max(predicted_metrics["response_time"], 0.1)
        cost_efficiency = 1.0 / max(predicted_metrics["cost"], 0.001)
        success_prob = predicted_metrics["success_probability"]
        availability = load_status.availability_score

        if self.optimization_objective == OptimizationObjective.MINIMIZE_COST:
            weights = {"quality": 0.3, "speed": 0.2, "cost": 0.4, "success": 0.1}
        elif self.optimization_objective == OptimizationObjective.MINIMIZE_TIME:
            weights = {"quality": 0.3, "speed": 0.5, "cost": 0.1, "success": 0.1}
        elif self.optimization_objective == OptimizationObjective.MAXIMIZE_QUALITY:
            weights = {"quality": 0.6, "speed": 0.1, "cost": 0.1, "success": 0.2}
        elif self.optimization_objective == OptimizationObjective.MAXIMIZE_THROUGHPUT:
            weights = {"quality": 0.2, "speed": 0.4, "cost": 0.2, "success": 0.2}
        else:  # BALANCE_ALL
            weights = {"quality": 0.3, "speed": 0.25, "cost": 0.25, "success": 0.2}

        score = (
            quality * weights["quality"]
            + speed * weights["speed"]
            + cost_efficiency * weights["cost"]
            + success_prob * weights["success"]
        ) * availability

        return score

    def _select_best_model(
        self, evaluations: Dict[str, Dict[str, Any]], strategy: RoutingStrategy
    ) -> Tuple[str, float, List[Tuple[str, float]]]:
        """Select the best model from evaluations."""

        # Sort by final score
        sorted_models = sorted(evaluations.items(), key=lambda x: x[1]["final_score"], reverse=True)

        if not sorted_models:
            raise ValueError("No valid model evaluations")

        # Best model
        best_model_id, best_eval = sorted_models[0]
        confidence = min(1.0, best_eval["final_score"])

        # Alternative models (top 3)
        alternatives = [
            (model_id, eval_data["final_score"]) for model_id, eval_data in sorted_models[1:4]
        ]

        return best_model_id, confidence, alternatives

    def _should_explore(self, model_id: str) -> bool:
        """Determine if we should explore this model for learning."""
        # Simple exploration strategy based on usage frequency
        recent_decisions = itertools.islice(reversed(self.routing_decisions), 100)
        recent_usage = sum(
            1 for decision in recent_decisions if decision.selected_model_id == model_id
        )

        # Explore models that haven't been used much recently
        exploration_threshold = self.config["exploration_rate"] * 100
        return recent_usage < exploration_threshold

    def _generate_justification(
        self,
        selected_model_id: str,
        evaluation: Dict[str, Any],
        strategy: RoutingStrategy,
    ) -> str:
        """Generate human-readable justification for the routing decision."""

        model = evaluation["model"]
        metrics = evaluation["metrics"]

        justification = f"Selected {model.name} using {strategy.value} strategy. "

        if strategy == RoutingStrategy.COST_OPTIMIZED:
            justification += f"Cost-effective choice (${metrics['cost']:.4f}) "
        elif strategy == RoutingStrategy.SPEED_OPTIMIZED:
            justification += f"Fast response expected ({metrics['response_time']:.1f}s) "
        elif strategy == RoutingStrategy.QUALITY_OPTIMIZED:
            justification += f"High quality output expected ({metrics['quality']:.2f}) "

        justification += f"with {metrics['success_probability']:.1%} success probability."

        return justification

    def _update_routing_metrics(self, decision: RoutingDecision) -> None:
        """Update routing metrics with new decision."""
        self.routing_metrics.total_routings += 1

        # Update average routing time
        total_time = (
            self.routing_metrics.avg_routing_time * (self.routing_metrics.total_routings - 1)
            + decision.routing_time
        )
        self.routing_metrics.avg_routing_time = total_time / self.routing_metrics.total_routings

        # Update strategy performance (will be updated when results come back)
        if decision.strategy_used not in self.routing_metrics.strategy_performance:
            self.routing_metrics.strategy_performance[decision.strategy_used] = {
                "usage_count": 0,
                "success_rate": 0.0,
                "avg_quality": 0.0,
            }

        self.routing_metrics.strategy_performance[decision.strategy_used]["usage_count"] += 1

        # Update model utilization
        if decision.selected_model_id not in self.routing_metrics.model_utilization:
            self.routing_metrics.model_utilization[decision.selected_model_id] = 0

        self.routing_metrics.model_utilization[decision.selected_model_id] += 1

    async def update_performance_feedback(
        self,
        task_id: str,
        model_id: str,
        result: ProcessingResult,
        task_type: TaskType,
        success: bool,
    ) -> None:
        """Update performance history with feedback from completed task."""

        # Update model performance history
        if model_id not in self.model_performance_history:
            self.model_performance_history[model_id] = ModelPerformanceHistory(model_id=model_id)

        self.model_performance_history[model_id].update_performance(result, task_type)

        # Update load monitoring
        await self.load_monitor.register_request_complete(
            model_id, task_id, result.processing_time, success
        )

        # Update routing metrics
        if success:
            self.routing_metrics.successful_routings += 1

        # Find corresponding routing decision and update strategy performance
        for decision in self.routing_decisions:
            if decision.task_id == task_id and decision.selected_model_id == model_id:
                strategy_perf = self.routing_metrics.strategy_performance[decision.strategy_used]

                # Update success rate
                count = strategy_perf["usage_count"]
                old_success_rate = strategy_perf["success_rate"]
                new_success_rate = (
                    old_success_rate * (count - 1) + (1.0 if success else 0.0)
                ) / count
                strategy_perf["success_rate"] = new_success_rate

                # Update average quality
                old_quality = strategy_perf["avg_quality"]
                new_quality = (old_quality * (count - 1) + result.confidence) / count
                strategy_perf["avg_quality"] = new_quality

                break

    def get_routing_history(self, limit: Optional[int] = None) -> List[RoutingDecision]:
        """Get historical routing decisions."""
        decisions = list(self.routing_decisions)
        return decisions[-limit:] if limit else decisions

    def get_routing_metrics(self) -> RoutingMetrics:
        """Get current routing metrics."""
        return self.routing_metrics

    def get_model_performance_history(self) -> Dict[str, ModelPerformanceHistory]:
        """Get performance history for all models."""
        return self.model_performance_history.copy()

    def get_load_status_all(self) -> Dict[str, ModelLoadStatus]:
        """Get current load status for all models."""
        return self.load_monitor.get_all_load_statuses()

    def configure_routing(self, **config_updates: Any) -> None:
        """Update routing configuration."""
        self.config.update(config_updates)
        logger.info(f"Updated routing configuration: {config_updates}")

    def set_optimization_objective(self, objective: OptimizationObjective) -> None:
        """Change the optimization objective."""
        old_objective = self.optimization_objective
        self.optimization_objective = objective
        logger.info(
            f"Changed optimization objective from {old_objective.value} to {objective.value}"
        )

    def reset_performance_history(self) -> None:
        """Reset all performance history (useful for testing or major changes)."""
        self.model_performance_history.clear()
        self.routing_decisions.clear()
        self.routing_metrics = RoutingMetrics()
        logger.info("Reset all performance history and metrics")
