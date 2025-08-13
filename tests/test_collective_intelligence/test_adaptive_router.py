"""
Comprehensive test suite for the Adaptive Model Router.

This module provides thorough testing of the intelligent model routing functionality
including performance prediction, load balancing, and adaptive optimization.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import List
from unittest.mock import AsyncMock, Mock, patch
import time

from src.openrouter_mcp.collective_intelligence.adaptive_router import (
    AdaptiveRouter, ModelLoadMonitor, PerformancePredictor,
    RoutingStrategy, OptimizationObjective, ModelPerformanceHistory,
    ModelLoadStatus, RoutingDecision, RoutingMetrics
)
from src.openrouter_mcp.collective_intelligence.base import (
    TaskContext, ProcessingResult, ModelInfo, TaskType, ModelCapability
)


class TestModelLoadMonitor:
    """Test suite for the ModelLoadMonitor class."""

    @pytest.mark.unit
    def test_load_monitor_initialization(self):
        """Test that ModelLoadMonitor initializes correctly."""
        monitor = ModelLoadMonitor()
        
        assert isinstance(monitor.model_loads, dict)
        assert len(monitor.model_loads) == 0
        assert isinstance(monitor.request_history, dict)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_register_request_start(self):
        """Test registering the start of a request."""
        monitor = ModelLoadMonitor()
        model_id = "test_model"
        task_id = "test_task"
        
        await monitor.register_request_start(model_id, task_id)
        
        assert model_id in monitor.model_loads
        load_status = monitor.model_loads[model_id]
        assert load_status.model_id == model_id
        assert load_status.active_requests == 1
        assert load_status.last_request_time is not None
        assert load_status.availability_score < 1.0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_register_request_complete(self):
        """Test registering the completion of a request."""
        monitor = ModelLoadMonitor()
        model_id = "test_model"
        task_id = "test_task"
        
        # Start and then complete a request
        await monitor.register_request_start(model_id, task_id)
        initial_requests = monitor.model_loads[model_id].active_requests
        
        await monitor.register_request_complete(model_id, task_id, 2.5, True)
        
        load_status = monitor.model_loads[model_id]
        assert load_status.active_requests == initial_requests - 1
        assert load_status.avg_queue_time > 0
        assert model_id in monitor.request_history
        assert len(monitor.request_history[model_id]) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_multiple_concurrent_requests(self):
        """Test handling multiple concurrent requests."""
        monitor = ModelLoadMonitor()
        model_id = "test_model"
        
        # Start multiple requests
        for i in range(5):
            await monitor.register_request_start(model_id, f"task_{i}")
        
        load_status = monitor.model_loads[model_id]
        assert load_status.active_requests == 5
        assert load_status.availability_score <= 0.5  # Should decrease with load
        
        # Complete some requests
        for i in range(3):
            await monitor.register_request_complete(model_id, f"task_{i}", 1.0 + i, True)
        
        assert load_status.active_requests == 2

    @pytest.mark.unit
    def test_get_load_status_existing_model(self):
        """Test getting load status for an existing model."""
        monitor = ModelLoadMonitor()
        model_id = "test_model"
        
        # Manually add a load status
        test_status = ModelLoadStatus(model_id=model_id, active_requests=3)
        monitor.model_loads[model_id] = test_status
        
        retrieved_status = monitor.get_load_status(model_id)
        assert retrieved_status == test_status

    @pytest.mark.unit
    def test_get_load_status_new_model(self):
        """Test getting load status for a new model."""
        monitor = ModelLoadMonitor()
        model_id = "new_model"
        
        load_status = monitor.get_load_status(model_id)
        assert load_status.model_id == model_id
        assert load_status.active_requests == 0
        assert load_status.availability_score == 1.0

    @pytest.mark.unit
    def test_get_all_load_statuses(self):
        """Test getting all load statuses."""
        monitor = ModelLoadMonitor()
        
        # Add some test statuses
        models = ["model_1", "model_2", "model_3"]
        for model_id in models:
            monitor.model_loads[model_id] = ModelLoadStatus(model_id=model_id, active_requests=1)
        
        all_statuses = monitor.get_all_load_statuses()
        assert len(all_statuses) == 3
        assert all(model_id in all_statuses for model_id in models)


class TestModelPerformanceHistory:
    """Test suite for the ModelPerformanceHistory class."""

    @pytest.mark.unit
    def test_performance_history_initialization(self):
        """Test that ModelPerformanceHistory initializes correctly."""
        model_id = "test_model"
        history = ModelPerformanceHistory(model_id=model_id)
        
        assert history.model_id == model_id
        assert history.task_completions == 0
        assert history.success_rate == 1.0
        assert len(history.recent_response_times) == 0
        assert len(history.recent_quality_scores) == 0
        assert len(history.recent_costs) == 0
        assert len(history.task_type_performance) == 0

    @pytest.mark.unit
    def test_update_performance_first_result(self):
        """Test updating performance with the first result."""
        history = ModelPerformanceHistory(model_id="test_model")
        
        result = ProcessingResult(
            task_id="test_task",
            model_id="test_model",
            content="Test result",
            confidence=0.85,
            processing_time=2.3,
            cost=0.015
        )
        
        history.update_performance(result, TaskType.REASONING)
        
        assert history.task_completions == 1
        assert history.avg_response_time == 2.3
        assert history.avg_quality_score == 0.85
        assert history.avg_cost == 0.015
        assert TaskType.REASONING in history.task_type_performance
        
        reasoning_perf = history.task_type_performance[TaskType.REASONING]
        assert reasoning_perf['response_time'] == 2.3
        assert reasoning_perf['quality'] == 0.85
        assert reasoning_perf['cost'] == 0.015
        assert reasoning_perf['count'] == 1

    @pytest.mark.unit
    def test_update_performance_multiple_results(self):
        """Test updating performance with multiple results."""
        history = ModelPerformanceHistory(model_id="test_model")
        
        results = [
            ProcessingResult(
                task_id=f"task_{i}",
                model_id="test_model",
                content=f"Result {i}",
                confidence=0.8 + i * 0.02,
                processing_time=2.0 + i * 0.1,
                cost=0.01 + i * 0.001
            )
            for i in range(5)
        ]
        
        for result in results:
            history.update_performance(result, TaskType.REASONING)
        
        assert history.task_completions == 5
        assert len(history.recent_response_times) == 5
        assert len(history.recent_quality_scores) == 5
        assert len(history.recent_costs) == 5
        
        # Check averages are calculated correctly
        expected_avg_time = sum(r.processing_time for r in results) / len(results)
        expected_avg_quality = sum(r.confidence for r in results) / len(results)
        expected_avg_cost = sum(r.cost for r in results) / len(results)
        
        assert abs(history.avg_response_time - expected_avg_time) < 0.001
        assert abs(history.avg_quality_score - expected_avg_quality) < 0.001
        assert abs(history.avg_cost - expected_avg_cost) < 0.001

    @pytest.mark.unit
    def test_update_performance_different_task_types(self):
        """Test updating performance for different task types."""
        history = ModelPerformanceHistory(model_id="test_model")
        
        # Add results for different task types
        reasoning_result = ProcessingResult(
            task_id="reasoning_task",
            model_id="test_model",
            content="Reasoning result",
            confidence=0.9,
            processing_time=3.0,
            cost=0.02
        )
        
        creative_result = ProcessingResult(
            task_id="creative_task",
            model_id="test_model",
            content="Creative result",
            confidence=0.85,
            processing_time=2.5,
            cost=0.018
        )
        
        history.update_performance(reasoning_result, TaskType.REASONING)
        history.update_performance(creative_result, TaskType.CREATIVE)
        
        assert len(history.task_type_performance) == 2
        assert TaskType.REASONING in history.task_type_performance
        assert TaskType.CREATIVE in history.task_type_performance
        
        reasoning_perf = history.task_type_performance[TaskType.REASONING]
        creative_perf = history.task_type_performance[TaskType.CREATIVE]
        
        assert reasoning_perf['quality'] == 0.9
        assert creative_perf['quality'] == 0.85


class TestPerformancePredictor:
    """Test suite for the PerformancePredictor class."""

    @pytest.mark.unit
    def test_performance_predictor_initialization(self):
        """Test that PerformancePredictor initializes correctly."""
        predictor = PerformancePredictor()
        
        assert isinstance(predictor.prediction_cache, dict)
        assert len(predictor.prediction_cache) == 0

    @pytest.mark.unit
    def test_predict_performance_new_model(self, sample_models, sample_task):
        """Test performance prediction for a model with no history."""
        predictor = PerformancePredictor()
        model = sample_models[0]  # GPT-4
        history = ModelPerformanceHistory(model_id=model.model_id)
        
        predictions = predictor.predict_performance(model, sample_task, history)
        
        assert isinstance(predictions, dict)
        assert 'response_time' in predictions
        assert 'quality' in predictions
        assert 'cost' in predictions
        assert 'success_probability' in predictions
        
        assert predictions['response_time'] > 0
        assert 0 <= predictions['quality'] <= 1
        assert predictions['cost'] >= 0
        assert 0 <= predictions['success_probability'] <= 1

    @pytest.mark.unit
    def test_predict_performance_with_history(self, sample_models, sample_task):
        """Test performance prediction for a model with historical data."""
        predictor = PerformancePredictor()
        model = sample_models[0]
        
        # Create history with task completions
        history = ModelPerformanceHistory(model_id=model.model_id)
        history.task_completions = 10
        history.avg_response_time = 2.5
        history.avg_quality_score = 0.88
        history.avg_cost = 0.012
        history.success_rate = 0.95
        
        # Add task-specific performance
        history.task_type_performance[TaskType.REASONING] = {
            'response_time': 2.8,
            'quality': 0.9,
            'cost': 0.014,
            'count': 5
        }
        
        predictions = predictor.predict_performance(model, sample_task, history)
        
        # Should use task-specific performance when available
        assert abs(predictions['response_time'] - 2.8) < 0.5  # Allow for complexity adjustment
        assert predictions['quality'] >= 0.8  # Should be high due to good history
        assert predictions['success_probability'] == 0.95

    @pytest.mark.unit
    def test_estimate_tokens(self):
        """Test token estimation function."""
        predictor = PerformancePredictor()
        
        short_text = "Hello world"
        long_text = "This is a much longer text with many more words that should result in more tokens"
        
        short_tokens = predictor._estimate_tokens(short_text)
        long_tokens = predictor._estimate_tokens(long_text)
        
        assert short_tokens > 0
        assert long_tokens > short_tokens
        assert isinstance(short_tokens, int)
        assert isinstance(long_tokens, int)

    @pytest.mark.unit
    def test_calculate_complexity_factor(self, sample_task):
        """Test complexity factor calculation."""
        predictor = PerformancePredictor()
        
        # Simple task
        simple_task = TaskContext(
            task_id="simple",
            task_type=TaskType.FACTUAL,
            content="What is 2+2?"
        )
        
        # Complex task
        complex_task = TaskContext(
            task_id="complex",
            task_type=TaskType.REASONING,
            content="A" * 2000,  # Long content
            requirements={"detail": "high", "examples": True, "analysis": "deep"}
        )
        
        simple_factor = predictor._calculate_complexity_factor(simple_task)
        complex_factor = predictor._calculate_complexity_factor(complex_task)
        
        assert simple_factor >= 1.0
        assert complex_factor > simple_factor

    @pytest.mark.unit
    def test_calculate_capability_match(self, sample_models):
        """Test capability matching calculation."""
        predictor = PerformancePredictor()
        model = sample_models[0]  # GPT-4 with strong reasoning
        
        reasoning_task = TaskContext(
            task_id="reasoning",
            task_type=TaskType.REASONING,
            content="Analyze this complex problem"
        )
        
        code_task = TaskContext(
            task_id="code",
            task_type=TaskType.CODE_GENERATION,
            content="Write a Python function"
        )
        
        reasoning_match = predictor._calculate_capability_match(model, reasoning_task)
        code_match = predictor._calculate_capability_match(model, code_task)
        
        assert 0.0 <= reasoning_match <= 1.0
        assert 0.0 <= code_match <= 1.0
        # GPT-4 should be better at reasoning than code in this test setup
        assert reasoning_match >= code_match

    @pytest.mark.unit
    def test_prediction_caching(self, sample_models, sample_task):
        """Test that predictions are cached correctly."""
        predictor = PerformancePredictor()
        model = sample_models[0]
        history = ModelPerformanceHistory(model_id=model.model_id)
        
        # First prediction
        predictions1 = predictor.predict_performance(model, sample_task, history)
        cache_size_after_first = len(predictor.prediction_cache)
        
        # Second prediction (should use cache)
        predictions2 = predictor.predict_performance(model, sample_task, history)
        cache_size_after_second = len(predictor.prediction_cache)
        
        assert cache_size_after_first == 1
        assert cache_size_after_second == 1  # No new cache entry
        assert predictions1 == predictions2  # Same predictions


class TestAdaptiveRouter:
    """Test suite for the AdaptiveRouter class."""

    @pytest.mark.unit
    def test_adaptive_router_initialization(self, mock_model_provider):
        """Test that AdaptiveRouter initializes correctly."""
        router = AdaptiveRouter(mock_model_provider)
        
        assert router.model_provider == mock_model_provider
        assert router.default_strategy == RoutingStrategy.ADAPTIVE
        assert router.optimization_objective == OptimizationObjective.BALANCE_ALL
        assert isinstance(router.load_monitor, ModelLoadMonitor)
        assert isinstance(router.performance_predictor, PerformancePredictor)
        assert isinstance(router.model_performance_history, dict)
        assert isinstance(router.routing_decisions, list)
        assert isinstance(router.routing_metrics, RoutingMetrics)

    @pytest.mark.unit
    def test_router_with_custom_settings(self, mock_model_provider):
        """Test router initialization with custom settings."""
        router = AdaptiveRouter(
            mock_model_provider,
            default_strategy=RoutingStrategy.COST_OPTIMIZED,
            optimization_objective=OptimizationObjective.MINIMIZE_COST
        )
        
        assert router.default_strategy == RoutingStrategy.COST_OPTIMIZED
        assert router.optimization_objective == OptimizationObjective.MINIMIZE_COST

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_routing_process(self, mock_model_provider, sample_task):
        """Test the complete routing process end-to-end."""
        router = AdaptiveRouter(mock_model_provider)
        
        decision = await router.process(sample_task)
        
        assert isinstance(decision, RoutingDecision)
        assert decision.task_id == sample_task.task_id
        assert decision.selected_model_id in [model.model_id for model in await mock_model_provider.get_available_models()]
        assert isinstance(decision.strategy_used, RoutingStrategy)
        assert 0.0 <= decision.confidence_score <= 1.0
        assert isinstance(decision.expected_performance, dict)
        assert isinstance(decision.alternative_models, list)
        assert isinstance(decision.justification, str)
        assert decision.routing_time > 0.0
        
        # Check that decision is stored
        assert len(router.routing_decisions) == 1
        assert router.routing_decisions[0] == decision

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_evaluate_models(self, mock_model_provider, sample_task, sample_models):
        """Test model evaluation process."""
        router = AdaptiveRouter(mock_model_provider)
        
        evaluations = await router._evaluate_models(sample_task, sample_models, RoutingStrategy.ADAPTIVE)
        
        assert isinstance(evaluations, dict)
        assert len(evaluations) <= len(sample_models)  # Some might fail evaluation
        
        for model_id, evaluation in evaluations.items():
            assert 'model' in evaluation
            assert 'metrics' in evaluation
            assert 'load_status' in evaluation
            assert 'performance_history' in evaluation
            assert 'strategy_score' in evaluation
            assert 'final_score' in evaluation
            
            assert evaluation['strategy_score'] >= 0.0
            assert evaluation['final_score'] >= 0.0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_evaluate_single_model(self, mock_model_provider, sample_task, sample_models):
        """Test evaluation of a single model."""
        router = AdaptiveRouter(mock_model_provider)
        model = sample_models[0]
        
        evaluation = await router._evaluate_single_model(sample_task, model, RoutingStrategy.QUALITY_OPTIMIZED)
        
        assert isinstance(evaluation, dict)
        assert evaluation['model'] == model
        assert 'metrics' in evaluation
        assert 'load_status' in evaluation
        assert 'performance_history' in evaluation
        assert 'strategy_score' in evaluation
        assert 'final_score' in evaluation

    @pytest.mark.unit
    def test_calculate_strategy_score_performance_based(self, mock_model_provider, sample_models):
        """Test strategy score calculation for performance-based routing."""
        router = AdaptiveRouter(mock_model_provider)
        model = sample_models[0]
        
        predicted_metrics = {
            'quality': 0.9,
            'response_time': 2.0,
            'cost': 0.01,
            'success_probability': 0.95
        }
        
        load_status = ModelLoadStatus(model_id=model.model_id, active_requests=1)
        
        score = router._calculate_strategy_score(
            model, predicted_metrics, load_status, RoutingStrategy.PERFORMANCE_BASED
        )
        
        assert isinstance(score, float)
        assert score > 0.0
        # Should be high due to good quality and success probability
        assert score > 0.8

    @pytest.mark.unit
    def test_calculate_strategy_score_cost_optimized(self, mock_model_provider, sample_models):
        """Test strategy score calculation for cost-optimized routing."""
        router = AdaptiveRouter(mock_model_provider)
        model = sample_models[0]
        
        low_cost_metrics = {
            'quality': 0.75,
            'response_time': 3.0,
            'cost': 0.001,  # Very low cost
            'success_probability': 0.9
        }
        
        high_cost_metrics = {
            'quality': 0.95,
            'response_time': 1.0,
            'cost': 0.1,  # High cost
            'success_probability': 0.95
        }
        
        load_status = ModelLoadStatus(model_id=model.model_id)
        
        low_cost_score = router._calculate_strategy_score(
            model, low_cost_metrics, load_status, RoutingStrategy.COST_OPTIMIZED
        )
        
        high_cost_score = router._calculate_strategy_score(
            model, high_cost_metrics, load_status, RoutingStrategy.COST_OPTIMIZED
        )
        
        # Low cost should score higher than high cost
        assert low_cost_score > high_cost_score

    @pytest.mark.unit
    def test_calculate_strategy_score_speed_optimized(self, mock_model_provider, sample_models):
        """Test strategy score calculation for speed-optimized routing."""
        router = AdaptiveRouter(mock_model_provider)
        model = sample_models[0]
        
        fast_metrics = {
            'quality': 0.8,
            'response_time': 0.5,  # Very fast
            'cost': 0.02,
            'success_probability': 0.9
        }
        
        slow_metrics = {
            'quality': 0.95,
            'response_time': 10.0,  # Very slow
            'cost': 0.005,
            'success_probability': 0.95
        }
        
        load_status = ModelLoadStatus(model_id=model.model_id)
        
        fast_score = router._calculate_strategy_score(
            model, fast_metrics, load_status, RoutingStrategy.SPEED_OPTIMIZED
        )
        
        slow_score = router._calculate_strategy_score(
            model, slow_metrics, load_status, RoutingStrategy.SPEED_OPTIMIZED
        )
        
        # Fast response should score higher than slow response
        assert fast_score > slow_score

    @pytest.mark.unit
    def test_calculate_strategy_score_load_balanced(self, mock_model_provider, sample_models):
        """Test strategy score calculation for load-balanced routing."""
        router = AdaptiveRouter(mock_model_provider)
        model = sample_models[0]
        
        predicted_metrics = {
            'quality': 0.85,
            'response_time': 2.0,
            'cost': 0.01,
            'success_probability': 0.9
        }
        
        low_load = ModelLoadStatus(model_id=model.model_id, active_requests=0)
        high_load = ModelLoadStatus(model_id=model.model_id, active_requests=5)
        
        low_load_score = router._calculate_strategy_score(
            model, predicted_metrics, low_load, RoutingStrategy.LOAD_BALANCED
        )
        
        high_load_score = router._calculate_strategy_score(
            model, predicted_metrics, high_load, RoutingStrategy.LOAD_BALANCED
        )
        
        # Low load should score higher than high load
        assert low_load_score > high_load_score

    @pytest.mark.unit
    def test_calculate_adaptive_score(self, mock_model_provider):
        """Test adaptive score calculation with different optimization objectives."""
        router = AdaptiveRouter(mock_model_provider)
        
        predicted_metrics = {
            'quality': 0.9,
            'response_time': 2.0,
            'cost': 0.01,
            'success_probability': 0.95
        }
        
        load_status = ModelLoadStatus(model_id="test_model", availability_score=0.9)
        
        # Test different optimization objectives
        objectives = [
            OptimizationObjective.MINIMIZE_COST,
            OptimizationObjective.MINIMIZE_TIME,
            OptimizationObjective.MAXIMIZE_QUALITY,
            OptimizationObjective.MAXIMIZE_THROUGHPUT,
            OptimizationObjective.BALANCE_ALL
        ]
        
        scores = []
        for objective in objectives:
            router.optimization_objective = objective
            score = router._calculate_adaptive_score(predicted_metrics, load_status)
            scores.append(score)
            assert isinstance(score, float)
            assert score > 0.0
        
        # All scores should be positive but different
        assert len(set(scores)) > 1  # Not all the same

    @pytest.mark.unit
    def test_select_best_model(self, mock_model_provider, sample_models):
        """Test best model selection from evaluations."""
        router = AdaptiveRouter(mock_model_provider)
        
        # Create mock evaluations
        evaluations = {}
        for i, model in enumerate(sample_models[:3]):
            evaluations[model.model_id] = {
                'model': model,
                'metrics': {'quality': 0.8 + i * 0.05},
                'final_score': 0.7 + i * 0.1  # Increasing scores
            }
        
        best_model_id, confidence, alternatives = router._select_best_model(
            evaluations, RoutingStrategy.ADAPTIVE
        )
        
        # Should select the model with highest score
        assert best_model_id == sample_models[2].model_id  # Highest score
        assert 0.0 <= confidence <= 1.0
        assert isinstance(alternatives, list)
        assert len(alternatives) <= 2  # Up to 2 alternatives

    @pytest.mark.unit
    def test_should_explore(self, mock_model_provider):
        """Test exploration decision logic."""
        router = AdaptiveRouter(mock_model_provider)
        
        # Add many decisions for one model, few for another
        frequent_model = "frequent_model"
        rare_model = "rare_model"
        
        for i in range(50):
            router.routing_decisions.append(
                RoutingDecision(
                    task_id=f"task_{i}",
                    selected_model_id=frequent_model,
                    strategy_used=RoutingStrategy.ADAPTIVE,
                    confidence_score=0.8,
                    expected_performance={},
                    alternative_models=[],
                    justification="Test",
                    routing_time=0.1
                )
            )
        
        # Should explore rare model more than frequent model
        frequent_explore = router._should_explore(frequent_model)
        rare_explore = router._should_explore(rare_model)
        
        assert isinstance(frequent_explore, bool)
        assert isinstance(rare_explore, bool)
        # Rare model should be more likely to be explored
        assert not frequent_explore or rare_explore

    @pytest.mark.unit
    def test_generate_justification(self, mock_model_provider, sample_models):
        """Test justification generation."""
        router = AdaptiveRouter(mock_model_provider)
        model = sample_models[0]
        
        evaluation = {
            'model': model,
            'metrics': {
                'quality': 0.9,
                'response_time': 2.0,
                'cost': 0.01,
                'success_probability': 0.95
            }
        }
        
        strategies = [
            RoutingStrategy.COST_OPTIMIZED,
            RoutingStrategy.SPEED_OPTIMIZED,
            RoutingStrategy.QUALITY_OPTIMIZED,
            RoutingStrategy.ADAPTIVE
        ]
        
        for strategy in strategies:
            justification = router._generate_justification(model.model_id, evaluation, strategy)
            
            assert isinstance(justification, str)
            assert len(justification) > 0
            assert model.name in justification
            assert strategy.value in justification

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_update_performance_feedback(self, mock_model_provider, sample_task):
        """Test updating performance feedback after task completion."""
        router = AdaptiveRouter(mock_model_provider)
        model_id = "test_model"
        
        # First, make a routing decision
        decision = await router.process(sample_task)
        
        # Then simulate task completion
        result = ProcessingResult(
            task_id=sample_task.task_id,
            model_id=decision.selected_model_id,
            content="Test result",
            confidence=0.9,
            processing_time=2.5,
            cost=0.012
        )
        
        initial_successful = router.routing_metrics.successful_routings
        
        await router.update_performance_feedback(
            sample_task.task_id,
            decision.selected_model_id,
            result,
            sample_task.task_type,
            True
        )
        
        # Check that metrics were updated
        assert router.routing_metrics.successful_routings == initial_successful + 1
        assert decision.selected_model_id in router.model_performance_history
        
        performance_history = router.model_performance_history[decision.selected_model_id]
        assert performance_history.task_completions > 0

    @pytest.mark.unit
    def test_get_routing_history(self, mock_model_provider):
        """Test getting routing history."""
        router = AdaptiveRouter(mock_model_provider)
        
        # Add some test decisions
        test_decisions = [
            RoutingDecision(
                task_id=f"task_{i}",
                selected_model_id=f"model_{i}",
                strategy_used=RoutingStrategy.ADAPTIVE,
                confidence_score=0.8,
                expected_performance={},
                alternative_models=[],
                justification=f"Decision {i}",
                routing_time=0.1
            )
            for i in range(10)
        ]
        
        router.routing_decisions = test_decisions
        
        # Test getting full history
        full_history = router.get_routing_history()
        assert len(full_history) == 10
        assert full_history == test_decisions
        
        # Test getting limited history
        limited_history = router.get_routing_history(limit=5)
        assert len(limited_history) == 5
        assert limited_history == test_decisions[-5:]

    @pytest.mark.unit
    def test_get_routing_metrics(self, mock_model_provider):
        """Test getting routing metrics."""
        router = AdaptiveRouter(mock_model_provider)
        
        # Modify some metrics
        router.routing_metrics.total_routings = 100
        router.routing_metrics.successful_routings = 85
        
        metrics = router.get_routing_metrics()
        
        assert isinstance(metrics, RoutingMetrics)
        assert metrics.total_routings == 100
        assert metrics.successful_routings == 85
        assert abs(metrics.success_rate() - 0.85) < 0.01

    @pytest.mark.unit
    def test_configure_routing(self, mock_model_provider):
        """Test updating routing configuration."""
        router = AdaptiveRouter(mock_model_provider)
        
        initial_timeout = router.config['decision_timeout']
        
        router.configure_routing(
            decision_timeout=10.0,
            exploration_rate=0.2
        )
        
        assert router.config['decision_timeout'] == 10.0
        assert router.config['exploration_rate'] == 0.2
        assert router.config['decision_timeout'] != initial_timeout

    @pytest.mark.unit
    def test_set_optimization_objective(self, mock_model_provider):
        """Test changing optimization objective."""
        router = AdaptiveRouter(mock_model_provider)
        
        initial_objective = router.optimization_objective
        new_objective = OptimizationObjective.MINIMIZE_COST
        
        router.set_optimization_objective(new_objective)
        
        assert router.optimization_objective == new_objective
        assert router.optimization_objective != initial_objective

    @pytest.mark.unit
    def test_reset_performance_history(self, mock_model_provider):
        """Test resetting performance history."""
        router = AdaptiveRouter(mock_model_provider)
        
        # Add some test data
        router.model_performance_history["test_model"] = ModelPerformanceHistory("test_model")
        router.routing_decisions.append(
            RoutingDecision(
                task_id="test",
                selected_model_id="test_model",
                strategy_used=RoutingStrategy.ADAPTIVE,
                confidence_score=0.8,
                expected_performance={},
                alternative_models=[],
                justification="Test",
                routing_time=0.1
            )
        )
        router.routing_metrics.total_routings = 5
        
        router.reset_performance_history()
        
        assert len(router.model_performance_history) == 0
        assert len(router.routing_decisions) == 0
        assert router.routing_metrics.total_routings == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_routing_with_different_strategies(self, mock_model_provider, sample_task):
        """Test routing with different strategies."""
        router = AdaptiveRouter(mock_model_provider)
        
        strategies = [
            RoutingStrategy.PERFORMANCE_BASED,
            RoutingStrategy.COST_OPTIMIZED,
            RoutingStrategy.SPEED_OPTIMIZED,
            RoutingStrategy.QUALITY_OPTIMIZED,
            RoutingStrategy.LOAD_BALANCED,
            RoutingStrategy.ADAPTIVE
        ]
        
        decisions = []
        for strategy in strategies:
            decision = await router.process(sample_task, strategy=strategy)
            decisions.append(decision)
            assert decision.strategy_used == strategy
        
        # All decisions should be valid
        assert len(decisions) == len(strategies)
        assert all(isinstance(d, RoutingDecision) for d in decisions)

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_routing_performance_many_models(self, performance_mock_provider, sample_task):
        """Test routing performance with many available models."""
        router = AdaptiveRouter(performance_mock_provider)
        
        start_time = time.time()
        decision = await router.process(sample_task)
        end_time = time.time()
        
        routing_time = end_time - start_time
        
        # Should complete routing quickly even with many models
        assert routing_time < 2.0  # 2 seconds max
        assert isinstance(decision, RoutingDecision)
        assert decision.routing_time < 1.0

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_routing_no_available_models(self, mock_model_provider, sample_task):
        """Test routing when no models are available."""
        # Mock provider that returns no models
        mock_model_provider.get_available_models.return_value = []
        
        router = AdaptiveRouter(mock_model_provider)
        
        with pytest.raises(ValueError, match="No models available"):
            await router.process(sample_task)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_routing_requests(self, mock_model_provider):
        """Test handling concurrent routing requests."""
        router = AdaptiveRouter(mock_model_provider)
        
        # Create multiple tasks
        tasks = [
            TaskContext(
                task_id=f"concurrent_task_{i}",
                task_type=TaskType.REASONING,
                content=f"Concurrent task {i} content"
            )
            for i in range(5)
        ]
        
        # Route all tasks concurrently
        decisions = await asyncio.gather(
            *[router.process(task) for task in tasks],
            return_exceptions=True
        )
        
        # All should succeed
        assert len(decisions) == 5
        assert all(isinstance(d, RoutingDecision) for d in decisions)
        assert len(set(d.task_id for d in decisions)) == 5  # All unique

    @pytest.mark.unit
    def test_routing_metrics_success_rate(self):
        """Test routing metrics success rate calculation."""
        metrics = RoutingMetrics()
        
        # No routings yet
        assert metrics.success_rate() == 0.0
        
        # Add some routings
        metrics.total_routings = 10
        metrics.successful_routings = 8
        
        assert abs(metrics.success_rate() - 0.8) < 0.01