"""
Adaptive Model Router

This module implements intelligent, real-time model selection based on task characteristics,
model performance history, current load, and optimization objectives. The router learns
from past decisions to continuously improve model selection accuracy.
"""

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import statistics

from .base import (
    CollectiveIntelligenceComponent,
    TaskContext,
    ProcessingResult,
    ModelProvider,
    ModelInfo,
    TaskType,
    ModelCapability,
    PerformanceMetrics
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
    
    def update_performance(self, result: ProcessingResult, task_type: TaskType):
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
                'response_time': 0.0,
                'quality': 0.0,
                'cost': 0.0,
                'count': 0
            }
        
        perf = self.task_type_performance[task_type]
        count = perf['count']
        perf['response_time'] = (perf['response_time'] * count + result.processing_time) / (count + 1)
        perf['quality'] = (perf['quality'] * count + result.confidence) / (count + 1)
        perf['cost'] = (perf['cost'] * count + result.cost) / (count + 1)
        perf['count'] += 1
        
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
    
    def __init__(self):
        self.model_loads: Dict[str, ModelLoadStatus] = {}
        self.request_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
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
        self, 
        model_id: str, 
        task_id: str, 
        processing_time: float,
        success: bool
    ) -> None:
        """Register the completion of a request."""
        async with self.monitor_lock:
            if model_id in self.model_loads:
                load_status = self.model_loads[model_id]
                load_status.active_requests = max(0, load_status.active_requests - 1)
                
                # Update queue time estimate
                self.request_history[model_id].append({
                    'timestamp': datetime.now(),
                    'processing_time': processing_time,
                    'success': success
                })
                
                # Calculate average queue time from recent history
                recent_times = [r['processing_time'] for r in self.request_history[model_id]]
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
    
    def __init__(self):
        self.prediction_cache: Dict[str, Dict[str, float]] = {}
        self.cache_ttl = timedelta(minutes=10)
    
    def predict_performance(
        self,
        model_info: ModelInfo,
        task: TaskContext,
        performance_history: ModelPerformanceHistory
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
                response_time = task_perf['response_time']
                quality = task_perf['quality']
                cost = task_perf['cost']
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
            'response_time': response_time,
            'quality': quality,
            'cost': cost,
            'success_probability': performance_history.success_rate
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
            TaskType.FACTUAL: 1.0
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
            TaskType.FACTUAL: [ModelCapability.ACCURACY]
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
        optimization_objective: OptimizationObjective = OptimizationObjective.BALANCE_ALL
    ):
        super().__init__(model_provider)
        self.default_strategy = default_strategy
        self.optimization_objective = optimization_objective
        
        # Components
        self.load_monitor = ModelLoadMonitor()
        self.performance_predictor = PerformancePredictor()
        
        # Performance tracking
        self.model_performance_history: Dict[str, ModelPerformanceHistory] = {}
        self.routing_decisions: List[RoutingDecision] = []
        self.routing_metrics = RoutingMetrics()
        
        # Configuration
        self.config = {
            'max_concurrent_evaluations': 10,
            'decision_timeout': 5.0,
            'min_confidence_threshold': 0.6,
            'exploration_rate': 0.1,  # Rate of trying less optimal models for learning
            'performance_history_weight': 0.7,
            'load_balancing_weight': 0.3
        }
    
    async def process(self, task: TaskContext, **kwargs) -> RoutingDecision:
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
            strategy = kwargs.get('strategy', self.default_strategy)
            
            # Get available models
            available_models = await self.model_provider.get_available_models()
            
            if not available_models:
                raise ValueError("No models available for routing")
            
            # Evaluate all models for this task
            model_evaluations = await self._evaluate_models(task, available_models, strategy)
            
            # Select best model
            selected_model_id, confidence, alternatives = self._select_best_model(
                model_evaluations, strategy
            )
            
            # Create routing decision
            routing_time = time.time() - start_time
            decision = RoutingDecision(
                task_id=task.task_id,
                selected_model_id=selected_model_id,
                strategy_used=strategy,
                confidence_score=confidence,
                expected_performance=model_evaluations[selected_model_id]['metrics'],
                alternative_models=alternatives,
                justification=self._generate_justification(
                    selected_model_id, model_evaluations[selected_model_id], strategy
                ),
                routing_time=routing_time,
                metadata={
                    'total_candidates': len(available_models),
                    'evaluation_time': routing_time,
                    'optimization_objective': self.optimization_objective.value
                }
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
        strategy: RoutingStrategy
    ) -> Dict[str, Dict[str, Any]]:
        """Evaluate all available models for the given task."""
        
        evaluations = {}
        
        # Evaluate models concurrently
        evaluation_tasks = [
            self._evaluate_single_model(task, model, strategy)
            for model in available_models
        ]
        
        results = await asyncio.gather(*evaluation_tasks, return_exceptions=True)
        
        for model, result in zip(available_models, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to evaluate model {model.model_id}: {str(result)}")
                continue
            
            evaluations[model.model_id] = result
        
        if not evaluations:
            raise ValueError("No models could be evaluated")
        
        return evaluations
    
    async def _evaluate_single_model(
        self,
        task: TaskContext,
        model: ModelInfo,
        strategy: RoutingStrategy
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
        
        # Calculate strategy-specific score
        strategy_score = self._calculate_strategy_score(
            model, predicted_metrics, load_status, strategy
        )
        
        # Apply exploration factor
        if self._should_explore(model.model_id):
            exploration_bonus = 0.1
            strategy_score += exploration_bonus
        
        return {
            'model': model,
            'metrics': predicted_metrics,
            'load_status': load_status,
            'performance_history': performance_history,
            'strategy_score': strategy_score,
            'final_score': strategy_score * load_status.availability_score
        }
    
    def _calculate_strategy_score(
        self,
        model: ModelInfo,
        predicted_metrics: Dict[str, float],
        load_status: ModelLoadStatus,
        strategy: RoutingStrategy
    ) -> float:
        """Calculate score based on the routing strategy."""
        
        if strategy == RoutingStrategy.PERFORMANCE_BASED:
            # Prioritize models with best historical performance
            return predicted_metrics['quality'] * predicted_metrics['success_probability']
        
        elif strategy == RoutingStrategy.COST_OPTIMIZED:
            # Minimize cost while maintaining reasonable quality
            cost_score = 1.0 / max(predicted_metrics['cost'], 0.001)
            quality_threshold = 0.7
            quality_penalty = max(0, quality_threshold - predicted_metrics['quality'])
            return cost_score - quality_penalty * 2.0
        
        elif strategy == RoutingStrategy.SPEED_OPTIMIZED:
            # Minimize response time
            time_score = 1.0 / max(predicted_metrics['response_time'], 0.1)
            return time_score * predicted_metrics['success_probability']
        
        elif strategy == RoutingStrategy.QUALITY_OPTIMIZED:
            # Maximize output quality regardless of cost/time
            return predicted_metrics['quality'] * predicted_metrics['success_probability']
        
        elif strategy == RoutingStrategy.LOAD_BALANCED:
            # Distribute load evenly across models
            load_factor = 1.0 / max(load_status.active_requests + 1, 1)
            base_score = predicted_metrics['quality'] * predicted_metrics['success_probability']
            return base_score * load_factor
        
        else:  # ADAPTIVE
            # Balance multiple factors based on optimization objective
            return self._calculate_adaptive_score(predicted_metrics, load_status)
    
    def _calculate_adaptive_score(
        self,
        predicted_metrics: Dict[str, float],
        load_status: ModelLoadStatus
    ) -> float:
        """Calculate adaptive score based on optimization objective."""
        
        quality = predicted_metrics['quality']
        speed = 1.0 / max(predicted_metrics['response_time'], 0.1)
        cost_efficiency = 1.0 / max(predicted_metrics['cost'], 0.001)
        success_prob = predicted_metrics['success_probability']
        availability = load_status.availability_score
        
        if self.optimization_objective == OptimizationObjective.MINIMIZE_COST:
            weights = {'quality': 0.3, 'speed': 0.2, 'cost': 0.4, 'success': 0.1}
        elif self.optimization_objective == OptimizationObjective.MINIMIZE_TIME:
            weights = {'quality': 0.3, 'speed': 0.5, 'cost': 0.1, 'success': 0.1}
        elif self.optimization_objective == OptimizationObjective.MAXIMIZE_QUALITY:
            weights = {'quality': 0.6, 'speed': 0.1, 'cost': 0.1, 'success': 0.2}
        elif self.optimization_objective == OptimizationObjective.MAXIMIZE_THROUGHPUT:
            weights = {'quality': 0.2, 'speed': 0.4, 'cost': 0.2, 'success': 0.2}
        else:  # BALANCE_ALL
            weights = {'quality': 0.3, 'speed': 0.25, 'cost': 0.25, 'success': 0.2}
        
        score = (
            quality * weights['quality'] +
            speed * weights['speed'] +
            cost_efficiency * weights['cost'] +
            success_prob * weights['success']
        ) * availability
        
        return score
    
    def _select_best_model(
        self,
        evaluations: Dict[str, Dict[str, Any]],
        strategy: RoutingStrategy
    ) -> Tuple[str, float, List[Tuple[str, float]]]:
        """Select the best model from evaluations."""
        
        # Sort by final score
        sorted_models = sorted(
            evaluations.items(),
            key=lambda x: x[1]['final_score'],
            reverse=True
        )
        
        if not sorted_models:
            raise ValueError("No valid model evaluations")
        
        # Best model
        best_model_id, best_eval = sorted_models[0]
        confidence = min(1.0, best_eval['final_score'])
        
        # Alternative models (top 3)
        alternatives = [
            (model_id, eval_data['final_score'])
            for model_id, eval_data in sorted_models[1:4]
        ]
        
        return best_model_id, confidence, alternatives
    
    def _should_explore(self, model_id: str) -> bool:
        """Determine if we should explore this model for learning."""
        # Simple exploration strategy based on usage frequency
        recent_usage = sum(
            1 for decision in self.routing_decisions[-100:]
            if decision.selected_model_id == model_id
        )
        
        # Explore models that haven't been used much recently
        exploration_threshold = self.config['exploration_rate'] * 100
        return recent_usage < exploration_threshold
    
    def _generate_justification(
        self,
        selected_model_id: str,
        evaluation: Dict[str, Any],
        strategy: RoutingStrategy
    ) -> str:
        """Generate human-readable justification for the routing decision."""
        
        model = evaluation['model']
        metrics = evaluation['metrics']
        
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
            self.routing_metrics.avg_routing_time * (self.routing_metrics.total_routings - 1) +
            decision.routing_time
        )
        self.routing_metrics.avg_routing_time = total_time / self.routing_metrics.total_routings
        
        # Update strategy performance (will be updated when results come back)
        if decision.strategy_used not in self.routing_metrics.strategy_performance:
            self.routing_metrics.strategy_performance[decision.strategy_used] = {
                'usage_count': 0,
                'success_rate': 0.0,
                'avg_quality': 0.0
            }
        
        self.routing_metrics.strategy_performance[decision.strategy_used]['usage_count'] += 1
        
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
        success: bool
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
                count = strategy_perf['usage_count']
                old_success_rate = strategy_perf['success_rate']
                new_success_rate = (old_success_rate * (count - 1) + (1.0 if success else 0.0)) / count
                strategy_perf['success_rate'] = new_success_rate
                
                # Update average quality
                old_quality = strategy_perf['avg_quality']
                new_quality = (old_quality * (count - 1) + result.confidence) / count
                strategy_perf['avg_quality'] = new_quality
                
                break
    
    def get_routing_history(self, limit: Optional[int] = None) -> List[RoutingDecision]:
        """Get historical routing decisions."""
        if limit:
            return self.routing_decisions[-limit:]
        return self.routing_decisions.copy()
    
    def get_routing_metrics(self) -> RoutingMetrics:
        """Get current routing metrics."""
        return self.routing_metrics
    
    def get_model_performance_history(self) -> Dict[str, ModelPerformanceHistory]:
        """Get performance history for all models."""
        return self.model_performance_history.copy()
    
    def get_load_status_all(self) -> Dict[str, ModelLoadStatus]:
        """Get current load status for all models."""
        return self.load_monitor.get_all_load_statuses()
    
    def configure_routing(self, **config_updates) -> None:
        """Update routing configuration."""
        self.config.update(config_updates)
        logger.info(f"Updated routing configuration: {config_updates}")
    
    def set_optimization_objective(self, objective: OptimizationObjective) -> None:
        """Change the optimization objective."""
        old_objective = self.optimization_objective
        self.optimization_objective = objective
        logger.info(f"Changed optimization objective from {old_objective.value} to {objective.value}")
    
    def reset_performance_history(self) -> None:
        """Reset all performance history (useful for testing or major changes)."""
        self.model_performance_history.clear()
        self.routing_decisions.clear()
        self.routing_metrics = RoutingMetrics()
        logger.info("Reset all performance history and metrics")