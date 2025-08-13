"""
Comprehensive test suite for the Consensus Engine.

This module provides thorough testing of the multi-model consensus functionality
including unit tests, integration tests, and edge case scenarios.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import List
from unittest.mock import AsyncMock, patch

from src.openrouter_mcp.collective_intelligence.consensus_engine import (
    ConsensusEngine, ConsensusConfig, ConsensusStrategy, ConsensusResult,
    AgreementLevel, ModelResponse
)
from src.openrouter_mcp.collective_intelligence.base import (
    TaskContext, ProcessingResult, ModelInfo, TaskType, QualityMetrics
)


class TestConsensusEngine:
    """Test suite for the ConsensusEngine class."""

    @pytest.mark.unit
    def test_consensus_engine_initialization(self, mock_model_provider, consensus_config):
        """Test that ConsensusEngine initializes correctly."""
        engine = ConsensusEngine(mock_model_provider, consensus_config)
        
        assert engine.model_provider == mock_model_provider
        assert engine.config == consensus_config
        assert isinstance(engine.consensus_history, list)
        assert len(engine.consensus_history) == 0
        assert isinstance(engine.model_reliability, dict)
        assert len(engine.model_reliability) == 0

    @pytest.mark.unit
    def test_consensus_engine_default_config(self, mock_model_provider):
        """Test ConsensusEngine with default configuration."""
        engine = ConsensusEngine(mock_model_provider)
        
        assert engine.config.strategy == ConsensusStrategy.MAJORITY_VOTE
        assert engine.config.min_models == 3
        assert engine.config.max_models == 5
        assert engine.config.confidence_threshold == 0.7

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_select_models_basic(self, mock_model_provider, sample_task, consensus_config):
        """Test basic model selection functionality."""
        engine = ConsensusEngine(mock_model_provider, consensus_config)
        
        selected_models = await engine._select_models(sample_task)
        
        assert isinstance(selected_models, list)
        assert len(selected_models) >= consensus_config.min_models
        assert len(selected_models) <= consensus_config.max_models
        assert all(isinstance(model_id, str) for model_id in selected_models)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_select_models_respects_exclusions(self, mock_model_provider, sample_task):
        """Test that model selection respects exclusion list."""
        config = ConsensusConfig(
            exclude_models={"openai/gpt-4", "anthropic/claude-3-haiku"}
        )
        engine = ConsensusEngine(mock_model_provider, config)
        
        selected_models = await engine._select_models(sample_task)
        
        assert "openai/gpt-4" not in selected_models
        assert "anthropic/claude-3-haiku" not in selected_models

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_model_responses_success(self, mock_model_provider, sample_task, consensus_config):
        """Test successful retrieval of model responses."""
        engine = ConsensusEngine(mock_model_provider, consensus_config)
        model_ids = ["openai/gpt-4", "anthropic/claude-3-haiku", "meta-llama/llama-3.1-70b"]
        
        responses = await engine._get_model_responses(sample_task, model_ids)
        
        assert isinstance(responses, list)
        assert len(responses) == len(model_ids)
        assert all(isinstance(response, ModelResponse) for response in responses)
        
        # Check that all requested models are represented
        response_model_ids = {response.model_id for response in responses}
        assert response_model_ids == set(model_ids)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_model_responses_timeout_handling(self, sample_task):
        """Test handling of model timeouts."""
        # Create a provider that times out
        slow_provider = AsyncMock()
        
        async def slow_process_task(task, model_id, **kwargs):
            await asyncio.sleep(0.2)  # Longer than timeout
            return ProcessingResult(
                task_id=task.task_id,
                model_id=model_id,
                content="Slow response",
                confidence=0.8
            )
        
        slow_provider.process_task.side_effect = slow_process_task
        
        config = ConsensusConfig(timeout_seconds=0.1)
        engine = ConsensusEngine(slow_provider, config)
        
        # Should handle timeout gracefully
        with pytest.raises(ValueError, match="Insufficient responses"):
            await engine._get_model_responses(sample_task, ["slow_model"])

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_majority_vote_consensus(self, mock_model_provider, sample_task, sample_processing_results):
        """Test majority vote consensus building."""
        engine = ConsensusEngine(mock_model_provider)
        
        # Create model responses
        model_responses = [
            ModelResponse(
                model_id=result.model_id,
                result=result,
                weight=1.0,
                reliability_score=1.0
            )
            for result in sample_processing_results[:3]
        ]
        
        consensus = engine._majority_vote_consensus(sample_task, model_responses)
        
        assert isinstance(consensus, ConsensusResult)
        assert consensus.task_id == sample_task.task_id
        assert consensus.strategy_used == ConsensusStrategy.MAJORITY_VOTE
        assert isinstance(consensus.agreement_level, AgreementLevel)
        assert 0.0 <= consensus.confidence_score <= 1.0
        assert len(consensus.participating_models) == 3
        assert len(consensus.model_responses) == 3
        assert isinstance(consensus.quality_metrics, QualityMetrics)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_weighted_average_consensus(self, mock_model_provider, sample_task, sample_processing_results):
        """Test weighted average consensus building."""
        config = ConsensusConfig(strategy=ConsensusStrategy.WEIGHTED_AVERAGE)
        engine = ConsensusEngine(mock_model_provider, config)
        
        # Create model responses with different weights
        model_responses = [
            ModelResponse(
                model_id=result.model_id,
                result=result,
                weight=1.5 if i == 0 else 1.0,  # First model has higher weight
                reliability_score=1.0
            )
            for i, result in enumerate(sample_processing_results[:3])
        ]
        
        consensus = engine._weighted_average_consensus(sample_task, model_responses)
        
        assert isinstance(consensus, ConsensusResult)
        assert consensus.strategy_used == ConsensusStrategy.WEIGHTED_AVERAGE
        assert 0.0 <= consensus.confidence_score <= 1.0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_confidence_threshold_consensus(self, mock_model_provider, sample_task, sample_processing_results):
        """Test confidence threshold consensus building."""
        config = ConsensusConfig(
            strategy=ConsensusStrategy.CONFIDENCE_THRESHOLD,
            confidence_threshold=0.8
        )
        engine = ConsensusEngine(mock_model_provider, config)
        
        # Create model responses with varying confidence levels
        model_responses = []
        for i, result in enumerate(sample_processing_results[:3]):
            result.confidence = 0.9 if i == 0 else 0.7  # Only first model meets threshold
            model_responses.append(
                ModelResponse(
                    model_id=result.model_id,
                    result=result,
                    weight=1.0,
                    reliability_score=1.0
                )
            )
        
        consensus = engine._confidence_threshold_consensus(sample_task, model_responses)
        
        assert isinstance(consensus, ConsensusResult)
        assert consensus.strategy_used == ConsensusStrategy.CONFIDENCE_THRESHOLD

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_consensus_process(self, mock_model_provider, sample_task, consensus_config):
        """Test the complete consensus building process end-to-end."""
        engine = ConsensusEngine(mock_model_provider, consensus_config)
        
        result = await engine.process(sample_task)
        
        assert isinstance(result, ConsensusResult)
        assert result.task_id == sample_task.task_id
        assert result.processing_time > 0
        assert len(result.participating_models) >= consensus_config.min_models
        assert len(result.model_responses) >= consensus_config.min_models
        assert isinstance(result.consensus_content, str)
        assert len(result.consensus_content) > 0
        
        # Check that consensus was added to history
        assert len(engine.consensus_history) == 1
        assert engine.consensus_history[0] == result

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_model_reliability_updates(self, mock_model_provider, sample_task, consensus_config):
        """Test that model reliability scores are updated after consensus."""
        engine = ConsensusEngine(mock_model_provider, consensus_config)
        
        # Initially no reliability scores
        assert len(engine.model_reliability) == 0
        
        # Process a task
        await engine.process(sample_task)
        
        # Check that reliability scores were created
        assert len(engine.model_reliability) > 0
        for model_id, score in engine.model_reliability.items():
            assert 0.0 <= score <= 1.0

    @pytest.mark.unit
    def test_calculate_agreement_level(self, mock_model_provider):
        """Test agreement level calculation."""
        engine = ConsensusEngine(mock_model_provider)
        
        assert engine._calculate_agreement_level(1.0) == AgreementLevel.UNANIMOUS
        assert engine._calculate_agreement_level(0.9) == AgreementLevel.HIGH_CONSENSUS
        assert engine._calculate_agreement_level(0.7) == AgreementLevel.MODERATE_CONSENSUS
        assert engine._calculate_agreement_level(0.5) == AgreementLevel.LOW_CONSENSUS
        assert engine._calculate_agreement_level(0.3) == AgreementLevel.NO_CONSENSUS

    @pytest.mark.unit
    def test_group_similar_responses(self, mock_model_provider, sample_processing_results):
        """Test response grouping logic."""
        engine = ConsensusEngine(mock_model_provider)
        
        model_responses = [
            ModelResponse(
                model_id=result.model_id,
                result=result,
                weight=1.0,
                reliability_score=1.0
            )
            for result in sample_processing_results[:3]
        ]
        
        groups = engine._group_similar_responses(model_responses)
        
        assert isinstance(groups, list)
        assert len(groups) >= 1
        assert all(isinstance(group, list) for group in groups)
        assert all(all(isinstance(response, ModelResponse) for response in group) for group in groups)

    @pytest.mark.unit
    def test_calculate_consensus_confidence(self, mock_model_provider, sample_processing_results):
        """Test consensus confidence calculation."""
        engine = ConsensusEngine(mock_model_provider)
        
        consensus_group = [
            ModelResponse(
                model_id=result.model_id,
                result=result,
                weight=1.0,
                reliability_score=1.0
            )
            for result in sample_processing_results[:2]
        ]
        
        all_responses = [
            ModelResponse(
                model_id=result.model_id,
                result=result,
                weight=1.0,
                reliability_score=1.0
            )
            for result in sample_processing_results
        ]
        
        confidence = engine._calculate_consensus_confidence(consensus_group, all_responses)
        
        assert 0.0 <= confidence <= 1.0

    @pytest.mark.unit
    def test_calculate_quality_metrics(self, mock_model_provider, sample_processing_results):
        """Test quality metrics calculation."""
        engine = ConsensusEngine(mock_model_provider)
        
        consensus_group = [
            ModelResponse(
                model_id=result.model_id,
                result=result,
                weight=1.0,
                reliability_score=1.0
            )
            for result in sample_processing_results[:2]
        ]
        
        all_responses = [
            ModelResponse(
                model_id=result.model_id,
                result=result,
                weight=1.0,
                reliability_score=1.0
            )
            for result in sample_processing_results
        ]
        
        metrics = engine._calculate_quality_metrics(consensus_group, all_responses)
        
        assert isinstance(metrics, QualityMetrics)
        assert 0.0 <= metrics.accuracy <= 1.0
        assert 0.0 <= metrics.consistency <= 1.0
        assert 0.0 <= metrics.completeness <= 1.0
        assert 0.0 <= metrics.relevance <= 1.0
        assert 0.0 <= metrics.confidence <= 1.0
        assert 0.0 <= metrics.coherence <= 1.0
        assert 0.0 <= metrics.overall_score() <= 1.0

    @pytest.mark.unit
    def test_model_relevance_calculation(self, mock_model_provider, sample_models, sample_task):
        """Test model relevance calculation for task assignment."""
        engine = ConsensusEngine(mock_model_provider)
        
        for model in sample_models:
            relevance = engine._calculate_model_relevance(model, sample_task)
            assert 0.0 <= relevance <= 1.0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_consensus_with_different_strategies(self, mock_model_provider, sample_task):
        """Test consensus building with different strategies."""
        strategies = [
            ConsensusStrategy.MAJORITY_VOTE,
            ConsensusStrategy.WEIGHTED_AVERAGE,
            ConsensusStrategy.CONFIDENCE_THRESHOLD
        ]
        
        results = []
        for strategy in strategies:
            config = ConsensusConfig(strategy=strategy)
            engine = ConsensusEngine(mock_model_provider, config)
            result = await engine.process(sample_task)
            results.append(result)
            
            assert result.strategy_used == strategy
        
        # All strategies should produce valid results
        assert len(results) == len(strategies)
        assert all(isinstance(result, ConsensusResult) for result in results)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_handling_insufficient_models(self, failing_model_provider, sample_task):
        """Test error handling when insufficient models are available."""
        config = ConsensusConfig(min_models=3)
        engine = ConsensusEngine(failing_model_provider, config)
        
        with pytest.raises(ValueError, match="Insufficient responses"):
            await engine.process(sample_task)

    @pytest.mark.asyncio
    @pytest.mark.integration 
    async def test_consensus_history_tracking(self, mock_model_provider, sample_task, consensus_config):
        """Test that consensus history is properly tracked."""
        engine = ConsensusEngine(mock_model_provider, consensus_config)
        
        # Process multiple tasks
        task1 = sample_task
        task2 = TaskContext(
            task_id="test_task_002",
            task_type=TaskType.CREATIVE,
            content="Write a creative story about AI."
        )
        
        result1 = await engine.process(task1)
        result2 = await engine.process(task2)
        
        history = engine.get_consensus_history()
        assert len(history) == 2
        assert history[0] == result1
        assert history[1] == result2
        
        # Test limited history retrieval
        limited_history = engine.get_consensus_history(limit=1)
        assert len(limited_history) == 1
        assert limited_history[0] == result2

    @pytest.mark.unit
    def test_model_reliability_scores_access(self, mock_model_provider, consensus_config):
        """Test access to model reliability scores."""
        engine = ConsensusEngine(mock_model_provider, consensus_config)
        
        # Set some test reliability scores
        test_scores = {
            "model1": 0.85,
            "model2": 0.92,
            "model3": 0.78
        }
        engine.model_reliability = test_scores
        
        retrieved_scores = engine.get_model_reliability_scores()
        assert retrieved_scores == test_scores
        
        # Ensure it's a copy, not the original
        retrieved_scores["model4"] = 0.50
        assert "model4" not in engine.model_reliability

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_consensus_requests(self, mock_model_provider, consensus_config):
        """Test handling of concurrent consensus requests."""
        engine = ConsensusEngine(mock_model_provider, consensus_config)
        
        # Create multiple tasks
        tasks = [
            TaskContext(
                task_id=f"concurrent_task_{i}",
                task_type=TaskType.REASONING,
                content=f"Task {i} content"
            )
            for i in range(3)
        ]
        
        # Process all tasks concurrently
        results = await asyncio.gather(
            *[engine.process(task) for task in tasks],
            return_exceptions=True
        )
        
        # All should succeed
        assert len(results) == 3
        assert all(isinstance(result, ConsensusResult) for result in results)
        assert len(set(result.task_id for result in results)) == 3  # All unique

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_consensus_performance_benchmark(self, performance_mock_provider, sample_task):
        """Test consensus performance with many models."""
        config = ConsensusConfig(min_models=5, max_models=8)
        engine = ConsensusEngine(performance_mock_provider, config)
        
        start_time = datetime.now()
        result = await engine.process(sample_task)
        end_time = datetime.now()
        
        processing_time = (end_time - start_time).total_seconds()
        
        # Should complete within reasonable time
        assert processing_time < 5.0  # 5 seconds max
        assert len(result.participating_models) >= 5
        assert isinstance(result, ConsensusResult)

    @pytest.mark.unit
    def test_consensus_config_validation(self):
        """Test validation of consensus configuration."""
        # Valid config
        config = ConsensusConfig(min_models=2, max_models=5)
        assert config.min_models <= config.max_models
        
        # Test various strategies
        for strategy in ConsensusStrategy:
            config = ConsensusConfig(strategy=strategy)
            assert config.strategy == strategy

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_empty_model_response_handling(self, mock_model_provider, sample_task):
        """Test handling of empty model responses."""
        # Mock provider that returns empty responses
        empty_provider = AsyncMock()
        empty_provider.get_available_models.return_value = []
        
        engine = ConsensusEngine(empty_provider)
        
        with pytest.raises(Exception):  # Should handle gracefully
            await engine.process(sample_task)

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_single_model_consensus(self, mock_model_provider, sample_task):
        """Test consensus building with only one available model."""
        config = ConsensusConfig(min_models=1, max_models=1)
        engine = ConsensusEngine(mock_model_provider, config)
        
        result = await engine.process(sample_task)
        
        assert isinstance(result, ConsensusResult)
        assert len(result.participating_models) == 1
        assert result.agreement_level == AgreementLevel.UNANIMOUS  # Single model = unanimous

    @pytest.mark.unit
    def test_quality_metrics_edge_cases(self, mock_model_provider):
        """Test quality metrics calculation with edge cases."""
        engine = ConsensusEngine(mock_model_provider)
        
        # Empty group
        metrics = engine._calculate_quality_metrics([], [])
        assert isinstance(metrics, QualityMetrics)
        assert metrics.overall_score() == 0.0
        
        # Single response
        single_response = [
            ModelResponse(
                model_id="test_model",
                result=ProcessingResult(
                    task_id="test",
                    model_id="test_model", 
                    content="test",
                    confidence=0.8
                ),
                weight=1.0,
                reliability_score=1.0
            )
        ]
        
        metrics = engine._calculate_quality_metrics(single_response, single_response)
        assert isinstance(metrics, QualityMetrics)
        assert 0.0 <= metrics.overall_score() <= 1.0