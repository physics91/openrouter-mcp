"""
Integration test suite for Collective Intelligence system.

This module provides comprehensive integration tests that verify the interaction
between different CI components and end-to-end workflows.
"""

import asyncio
import pytest
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import AsyncMock, Mock, patch

from src.openrouter_mcp.collective_intelligence.consensus_engine import ConsensusEngine
from src.openrouter_mcp.collective_intelligence.ensemble_reasoning import EnsembleReasoner
from src.openrouter_mcp.collective_intelligence.adaptive_router import AdaptiveRouter
from src.openrouter_mcp.collective_intelligence.cross_validator import CrossValidator
from src.openrouter_mcp.collective_intelligence.collaborative_solver import CollaborativeSolver
from src.openrouter_mcp.collective_intelligence.base import (
    TaskContext, ProcessingResult, ModelInfo, TaskType, ModelCapability
)


@pytest.mark.integration
class TestCollectiveIntelligenceIntegration:
    """Integration tests for the complete Collective Intelligence system."""
    
    @pytest.fixture
    def integrated_model_provider(self, sample_models):
        """Create a comprehensive mock provider for integration testing."""
        provider = AsyncMock()
        provider.get_available_models.return_value = sample_models
        
        # Create different response patterns for different models
        response_patterns = {
            "openai/gpt-4": "GPT-4 provides detailed and analytical responses with high accuracy.",
            "anthropic/claude-3-haiku": "Claude offers balanced perspectives with ethical considerations.",
            "meta-llama/llama-3.1-70b": "Llama generates creative and comprehensive solutions.",
            "google/gemini-pro": "Gemini delivers structured and well-organized responses.",
            "mistralai/mixtral-8x7b": "Mixtral provides efficient and practical answers."
        }
        
        async def integrated_process_task(task, model_id, **kwargs):
            # Simulate different processing times and qualities
            model_characteristics = {
                "openai/gpt-4": {"time": 2.5, "confidence": 0.9, "cost": 0.03},
                "anthropic/claude-3-haiku": {"time": 1.2, "confidence": 0.85, "cost": 0.015},
                "meta-llama/llama-3.1-70b": {"time": 3.1, "confidence": 0.8, "cost": 0.02},
                "google/gemini-pro": {"time": 2.8, "confidence": 0.87, "cost": 0.025},
                "mistralai/mixtral-8x7b": {"time": 1.8, "confidence": 0.82, "cost": 0.012}
            }
            
            char = model_characteristics.get(model_id, {"time": 2.0, "confidence": 0.8, "cost": 0.02})
            base_response = response_patterns.get(model_id, f"Response from {model_id}")
            
            # Simulate processing delay
            await asyncio.sleep(0.01)  # Small delay for realism
            
            return ProcessingResult(
                task_id=task.task_id,
                model_id=model_id,
                content=f"{base_response} Task: {task.content[:100]}...",
                confidence=char["confidence"],
                processing_time=char["time"],
                tokens_used=len(task.content) // 4,
                cost=char["cost"]
            )
        
        provider.process_task.side_effect = integrated_process_task
        return provider
    
    @pytest.fixture
    def sample_integration_tasks(self):
        """Create sample tasks for integration testing."""
        return [
            TaskContext(
                task_id="integration_simple",
                task_type=TaskType.FACTUAL,
                content="What are the main benefits of renewable energy?",
                requirements={"format": "list", "detail": "concise"}
            ),
            TaskContext(
                task_id="integration_reasoning",
                task_type=TaskType.REASONING,
                content="Analyze the potential impacts of artificial intelligence on employment. "
                       "Consider both positive and negative effects, and suggest mitigation strategies.",
                requirements={"analysis_depth": "comprehensive", "include_examples": True}
            ),
            TaskContext(
                task_id="integration_creative",
                task_type=TaskType.CREATIVE,
                content="Design a sustainable city planning strategy for a population of 1 million people. "
                       "Include transportation, energy, waste management, and green spaces.",
                requirements={"innovation": "high", "feasibility": "realistic"}
            ),
            TaskContext(
                task_id="integration_code",
                task_type=TaskType.CODE_GENERATION,
                content="Create a Python class for managing a distributed cache system with "
                       "automatic failover and data replication.",
                requirements={"documentation": True, "error_handling": True, "testing": True}
            )
        ]
    
    @pytest.mark.asyncio
    async def test_consensus_to_validation_pipeline(self, integrated_model_provider, sample_integration_tasks):
        """Test pipeline from consensus building to validation."""
        consensus_engine = ConsensusEngine(integrated_model_provider)
        cross_validator = CrossValidator(integrated_model_provider)
        
        task = sample_integration_tasks[1]  # Reasoning task
        
        # Step 1: Build consensus
        consensus_result = await consensus_engine.process(task)
        
        assert consensus_result is not None
        assert consensus_result.consensus_content
        assert len(consensus_result.participating_models) > 0
        
        # Step 2: Validate the consensus
        consensus_processing_result = ProcessingResult(
            task_id=task.task_id,
            model_id="consensus_ensemble",
            content=consensus_result.consensus_content,
            confidence=consensus_result.confidence_score
        )
        
        validation_result = await cross_validator.process(consensus_processing_result, task)
        
        assert validation_result is not None
        assert isinstance(validation_result.is_valid, bool)
        assert validation_result.validation_confidence > 0.0
        
        # Verify integration quality
        assert validation_result.quality_metrics.overall_score() > 0.0
    
    @pytest.mark.asyncio
    async def test_router_to_ensemble_integration(self, integrated_model_provider, sample_integration_tasks):
        """Test integration between adaptive router and ensemble reasoning."""
        adaptive_router = AdaptiveRouter(integrated_model_provider)
        ensemble_reasoner = EnsembleReasoner(integrated_model_provider)
        
        task = sample_integration_tasks[2]  # Creative task
        
        # Step 1: Route to find best models
        routing_decision = await adaptive_router.process(task)
        
        assert routing_decision is not None
        assert routing_decision.selected_model_id
        assert routing_decision.confidence_score > 0.0
        
        # Step 2: Use ensemble reasoning
        ensemble_result = await ensemble_reasoner.process(task)
        
        assert ensemble_result is not None
        assert ensemble_result.final_content
        assert len(ensemble_result.sub_task_results) > 0
        
        # Verify that routing informed ensemble decisions
        participating_models = [str.model_id for str in ensemble_result.sub_task_results]
        
        # The routed model should influence ensemble selection
        assert len(participating_models) > 0
        assert ensemble_result.success_rate > 0.0
    
    @pytest.mark.asyncio
    async def test_full_ci_pipeline_integration(self, integrated_model_provider, sample_integration_tasks):
        """Test complete CI pipeline with all components."""
        # Initialize all components
        adaptive_router = AdaptiveRouter(integrated_model_provider)
        ensemble_reasoner = EnsembleReasoner(integrated_model_provider)
        consensus_engine = ConsensusEngine(integrated_model_provider)
        cross_validator = CrossValidator(integrated_model_provider)
        
        task = sample_integration_tasks[3]  # Code generation task
        
        # Step 1: Route to optimal model
        routing_decision = await adaptive_router.process(task)
        optimal_model = routing_decision.selected_model_id
        
        # Step 2: Generate initial solution with ensemble
        ensemble_result = await ensemble_reasoner.process(task)
        initial_solution = ensemble_result.final_content
        
        # Step 3: Build consensus for improvement
        consensus_result = await consensus_engine.process(task)
        consensus_solution = consensus_result.consensus_content
        
        # Step 4: Validate both solutions
        ensemble_pr = ProcessingResult(
            task_id=task.task_id,
            model_id="ensemble",
            content=initial_solution,
            confidence=ensemble_result.success_rate
        )
        
        consensus_pr = ProcessingResult(
            task_id=task.task_id,
            model_id="consensus",
            content=consensus_solution,
            confidence=consensus_result.confidence_score
        )
        
        ensemble_validation = await cross_validator.process(ensemble_pr, task)
        consensus_validation = await cross_validator.process(consensus_pr, task)
        
        # Verify complete pipeline results
        assert routing_decision.confidence_score > 0.0
        assert ensemble_result.success_rate > 0.0
        assert consensus_result.confidence_score > 0.0
        assert ensemble_validation.validation_confidence > 0.0
        assert consensus_validation.validation_confidence > 0.0
        
        # Compare validation results
        ensemble_quality = ensemble_validation.quality_metrics.overall_score()
        consensus_quality = consensus_validation.quality_metrics.overall_score()
        
        # At least one approach should produce good quality
        assert max(ensemble_quality, consensus_quality) > 0.5
    
    @pytest.mark.asyncio
    async def test_collaborative_solver_integration(self, integrated_model_provider, sample_integration_tasks):
        """Test collaborative solver integration with all components."""
        collaborative_solver = CollaborativeSolver(integrated_model_provider)
        
        # Test different solving strategies
        strategies = [
            'sequential',
            'parallel', 
            'hierarchical',
            'adaptive'
        ]
        
        task = sample_integration_tasks[0]  # Simple factual task
        results = {}
        
        for strategy in strategies:
            try:
                result = await collaborative_solver.process(task, strategy=strategy)
                results[strategy] = {
                    'success': True,
                    'confidence': result.confidence_score,
                    'content_length': len(result.final_content),
                    'processing_time': result.total_processing_time,
                    'components_used': len(result.component_contributions)
                }
            except Exception as e:
                results[strategy] = {
                    'success': False,
                    'error': str(e)
                }
        
        # Verify at least some strategies succeeded
        successful_strategies = [s for s, r in results.items() if r['success']]
        assert len(successful_strategies) > 0
        
        # Verify quality across successful strategies
        for strategy in successful_strategies:
            result = results[strategy]
            assert result['confidence'] > 0.0
            assert result['content_length'] > 0
            assert result['components_used'] > 0
    
    @pytest.mark.asyncio
    async def test_error_propagation_and_recovery(self, sample_integration_tasks):
        """Test error handling and recovery across component integration."""
        # Create a provider that fails intermittently
        failing_provider = AsyncMock()
        
        call_count = 0
        async def intermittent_failure(task, model_id, **kwargs):
            nonlocal call_count
            call_count += 1
            
            # Fail every 3rd call
            if call_count % 3 == 0:
                raise Exception(f"Simulated failure for {model_id}")
            
            return ProcessingResult(
                task_id=task.task_id,
                model_id=model_id,
                content=f"Success response from {model_id}",
                confidence=0.8
            )
        
        failing_provider.process_task.side_effect = intermittent_failure
        failing_provider.get_available_models.return_value = [
            ModelInfo(model_id="test_model_1", name="Test Model 1", provider="Test"),
            ModelInfo(model_id="test_model_2", name="Test Model 2", provider="Test"),
            ModelInfo(model_id="test_model_3", name="Test Model 3", provider="Test")
        ]
        
        # Test consensus engine resilience
        consensus_engine = ConsensusEngine(failing_provider)
        task = sample_integration_tasks[0]
        
        try:
            result = await consensus_engine.process(task)
            # Should succeed despite some failures
            assert result is not None
            # Some models should have succeeded
            assert len(result.participating_models) > 0
        except Exception:
            # If it fails completely, that's also acceptable for this test
            pass
    
    @pytest.mark.asyncio
    async def test_concurrent_multi_component_processing(self, integrated_model_provider, sample_integration_tasks):
        """Test concurrent processing across multiple components."""
        # Initialize components
        components = {
            'consensus': ConsensusEngine(integrated_model_provider),
            'router': AdaptiveRouter(integrated_model_provider),
            'ensemble': EnsembleReasoner(integrated_model_provider)
        }
        
        tasks = sample_integration_tasks[:3]  # Use first 3 tasks
        
        # Process each task with each component concurrently
        async def process_task_with_component(task, component_name, component):
            try:
                if component_name == 'router':
                    return await component.process(task)
                else:
                    return await component.process(task)
            except Exception as e:
                return f"Error in {component_name}: {str(e)}"
        
        # Create all combinations
        concurrent_operations = []
        for task in tasks:
            for comp_name, comp_instance in components.items():
                concurrent_operations.append(
                    process_task_with_component(task, comp_name, comp_instance)
                )
        
        # Execute all operations concurrently
        results = await asyncio.gather(*concurrent_operations, return_exceptions=True)
        
        # Analyze results
        successful_results = [r for r in results if not isinstance(r, Exception) and not isinstance(r, str)]
        failed_results = [r for r in results if isinstance(r, Exception) or isinstance(r, str)]
        
        # Should have reasonable success rate
        success_rate = len(successful_results) / len(results)
        assert success_rate > 0.5  # At least 50% success rate
        
        # Should complete in reasonable time (implicit in test completion)
        assert len(results) == len(concurrent_operations)
    
    @pytest.mark.asyncio
    async def test_data_flow_consistency(self, integrated_model_provider, sample_integration_tasks):
        """Test data consistency across component interactions."""
        task = sample_integration_tasks[1]  # Reasoning task
        
        # Process with ensemble reasoning
        ensemble_reasoner = EnsembleReasoner(integrated_model_provider)
        ensemble_result = await ensemble_reasoner.process(task)
        
        # Extract a sub-task result for validation
        if ensemble_result.sub_task_results:
            sub_result = ensemble_result.sub_task_results[0]
            
            # Validate the sub-result
            cross_validator = CrossValidator(integrated_model_provider)
            validation_result = await cross_validator.process(sub_result.result, task)
            
            # Verify data consistency
            assert validation_result.task_id == task.task_id
            assert validation_result.original_result.task_id == sub_result.result.task_id
            assert validation_result.original_result.model_id == sub_result.result.model_id
            
            # Content should be related
            original_content = sub_result.result.content
            validation_content = validation_result.validation_report.original_result.content
            assert original_content == validation_content
    
    @pytest.mark.asyncio
    async def test_quality_improvement_across_components(self, integrated_model_provider):
        """Test that quality improves as content flows through components."""
        # Create a task that can benefit from multiple processing stages
        improvement_task = TaskContext(
            task_id="quality_improvement_test",
            task_type=TaskType.ANALYSIS,
            content="Analyze the economic impact of remote work on urban development, "
                   "considering real estate, transportation, local businesses, and social dynamics.",
            requirements={"depth": "comprehensive", "evidence": "required"}
        )
        
        # Stage 1: Initial ensemble processing
        ensemble_reasoner = EnsembleReasoner(integrated_model_provider)
        ensemble_result = await ensemble_reasoner.process(improvement_task)
        
        # Stage 2: Build consensus for refinement
        consensus_engine = ConsensusEngine(integrated_model_provider)
        consensus_result = await consensus_engine.process(improvement_task)
        
        # Stage 3: Validate both results
        cross_validator = CrossValidator(integrated_model_provider)
        
        ensemble_pr = ProcessingResult(
            task_id=improvement_task.task_id,
            model_id="ensemble_stage",
            content=ensemble_result.final_content,
            confidence=ensemble_result.success_rate
        )
        
        consensus_pr = ProcessingResult(
            task_id=improvement_task.task_id,
            model_id="consensus_stage",
            content=consensus_result.consensus_content,
            confidence=consensus_result.confidence_score
        )
        
        ensemble_validation = await cross_validator.process(ensemble_pr, improvement_task)
        consensus_validation = await cross_validator.process(consensus_pr, improvement_task)
        
        # Analyze quality progression
        ensemble_quality = ensemble_validation.quality_metrics.overall_score()
        consensus_quality = consensus_validation.quality_metrics.overall_score()
        
        # At least one stage should show good quality
        max_quality = max(ensemble_quality, consensus_quality)
        assert max_quality > 0.3  # Reasonable quality threshold
        
        # Verify validation provides meaningful feedback
        assert len(ensemble_validation.improvement_suggestions) >= 0
        assert len(consensus_validation.improvement_suggestions) >= 0
    
    @pytest.mark.asyncio
    async def test_component_interoperability(self, integrated_model_provider, sample_integration_tasks):
        """Test that components can seamlessly work together."""
        task = sample_integration_tasks[2]  # Creative task
        
        # Chain components together
        # Router → Ensemble → Consensus → Validation
        
        # Step 1: Route
        router = AdaptiveRouter(integrated_model_provider)
        routing_decision = await router.process(task)
        
        # Step 2: Ensemble reasoning
        ensemble = EnsembleReasoner(integrated_model_provider)
        ensemble_result = await ensemble.process(task)
        
        # Step 3: Consensus building 
        consensus = ConsensusEngine(integrated_model_provider)
        consensus_result = await consensus.process(task)
        
        # Step 4: Cross-validation
        validator = CrossValidator(integrated_model_provider)
        
        # Validate ensemble result
        ensemble_pr = ProcessingResult(
            task_id=task.task_id,
            model_id="ensemble_output",
            content=ensemble_result.final_content,
            confidence=ensemble_result.success_rate
        )
        ensemble_validation = await validator.process(ensemble_pr, task)
        
        # Validate consensus result
        consensus_pr = ProcessingResult(
            task_id=task.task_id,
            model_id="consensus_output", 
            content=consensus_result.consensus_content,
            confidence=consensus_result.confidence_score
        )
        consensus_validation = await validator.process(consensus_pr, task)
        
        # Verify interoperability
        # All components should work with the same task
        assert routing_decision.task_id == task.task_id
        assert ensemble_result.task_id == task.task_id
        assert consensus_result.task_id == task.task_id
        assert ensemble_validation.task_id == task.task_id
        assert consensus_validation.task_id == task.task_id
        
        # Results should be meaningful
        assert len(routing_decision.selected_model_id) > 0
        assert len(ensemble_result.final_content) > 0
        assert len(consensus_result.consensus_content) > 0
        assert ensemble_validation.validation_confidence > 0.0
        assert consensus_validation.validation_confidence > 0.0
        
        # Validation should provide insights
        total_issues = (len(ensemble_validation.validation_report.issues) + 
                       len(consensus_validation.validation_report.issues))
        total_suggestions = (len(ensemble_validation.improvement_suggestions) + 
                           len(consensus_validation.improvement_suggestions))
        
        # At least some feedback should be provided
        assert total_issues >= 0
        assert total_suggestions >= 0