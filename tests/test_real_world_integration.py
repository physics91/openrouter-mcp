#!/usr/bin/env python3
"""
Real-world integration tests for Collective Intelligence MCP tools.

This module performs actual API calls to OpenRouter to test the collective 
intelligence capabilities in real scenarios with live models.

IMPORTANT: These tests require valid OpenRouter API credentials and will 
consume tokens/credits from your OpenRouter account.
"""

import asyncio
import os
import pytest
import time
from datetime import datetime
from typing import Dict, Any

from src.openrouter_mcp.handlers.collective_intelligence import (
    collective_chat_completion,
    ensemble_reasoning, 
    adaptive_model_selection,
    cross_model_validation,
    collaborative_problem_solving,
    CollectiveChatRequest,
    EnsembleReasoningRequest,
    AdaptiveModelRequest,
    CrossValidationRequest,
    CollaborativeSolvingRequest
)


class TestRealWorldIntegration:
    """Real-world integration tests using actual OpenRouter API calls."""
    
    @pytest.fixture(autouse=True)
    def check_api_key(self):
        """Ensure API key is available before running tests."""
        if not os.getenv("OPENROUTER_API_KEY"):
            pytest.skip("OPENROUTER_API_KEY not found - skipping real API tests")
    
    @pytest.mark.integration
    @pytest.mark.real_api
    async def test_collective_chat_real_api(self):
        """Test collective chat completion with real API calls."""
        print("\n[AI] Testing Collective Chat Completion with real API...")
        
        start_time = time.time()
        
        request = CollectiveChatRequest(
            prompt="What are the main advantages of renewable energy sources?",
            strategy="majority_vote",
            min_models=2,
            max_models=3,
            temperature=0.7
        )
        
        result = await collective_chat_completion(request)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Validate response structure
        assert isinstance(result, dict)
        assert "consensus_response" in result
        assert "agreement_level" in result
        assert "confidence_score" in result
        assert "participating_models" in result
        assert "individual_responses" in result
        
        # Validate content quality
        assert isinstance(result["consensus_response"], str)
        assert len(result["consensus_response"]) > 50  # Should be substantial
        assert 0.0 <= result["confidence_score"] <= 1.0
        assert len(result["participating_models"]) >= 2
        assert len(result["individual_responses"]) >= 2
        
        print(f"[SUCCESS] Collective Chat completed in {processing_time:.2f}s")
        print(f"[INFO] Consensus: {result['consensus_response'][:100]}...")
        print(f"[INFO] Agreement: {result['agreement_level']}")
        print(f"[INFO] Confidence: {result['confidence_score']:.3f}")
        print(f"[INFO] Models used: {len(result['participating_models'])}")
    
    @pytest.mark.integration
    @pytest.mark.real_api
    async def test_ensemble_reasoning_real_api(self):
        """Test ensemble reasoning with real API calls."""
        print("\n[AI] Testing Ensemble Reasoning with real API...")
        
        start_time = time.time()
        
        request = EnsembleReasoningRequest(
            problem="Analyze the potential impacts of remote work on urban planning",
            task_type="analysis",
            decompose=True,
            temperature=0.7
        )
        
        result = await ensemble_reasoning(request)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Validate response structure
        assert isinstance(result, dict)
        assert "final_result" in result
        assert "subtask_results" in result
        assert "model_assignments" in result
        assert "reasoning_quality" in result
        
        # Validate content quality
        assert isinstance(result["final_result"], str)
        assert len(result["final_result"]) > 100  # Should be comprehensive
        assert isinstance(result["subtask_results"], list)
        assert len(result["subtask_results"]) > 0
        assert isinstance(result["model_assignments"], dict)
        
        print(f"[SUCCESS] Ensemble Reasoning completed in {processing_time:.2f}s")
        print(f"[INFO] Final result: {result['final_result'][:100]}...")
        print(f"[INFO] Subtasks: {len(result['subtask_results'])}")
        print(f"[INFO] Strategy: {result['strategy_used']}")
    
    @pytest.mark.integration
    @pytest.mark.real_api
    async def test_adaptive_model_selection_real_api(self):
        """Test adaptive model selection with real API calls."""
        print("\n[AI] Testing Adaptive Model Selection with real API...")
        
        start_time = time.time()
        
        request = AdaptiveModelRequest(
            query="Write a Python function to calculate fibonacci numbers efficiently",
            task_type="code_generation",
            performance_requirements={"accuracy": 0.9, "speed": 0.8}
        )
        
        result = await adaptive_model_selection(request)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Validate response structure
        assert isinstance(result, dict)
        assert "selected_model" in result
        assert "selection_reasoning" in result
        assert "confidence" in result
        assert "alternative_models" in result
        assert "routing_metrics" in result
        
        # Validate content quality
        assert isinstance(result["selected_model"], str)
        assert len(result["selected_model"]) > 0
        assert isinstance(result["selection_reasoning"], str)
        assert len(result["selection_reasoning"]) > 20
        assert 0.0 <= result["confidence"] <= 1.0
        assert isinstance(result["alternative_models"], list)
        
        print(f"[SUCCESS] Adaptive Model Selection completed in {processing_time:.2f}s")
        print(f"[INFO] Selected model: {result['selected_model']}")
        print(f"[INFO] Reasoning: {result['selection_reasoning'][:80]}...")
        print(f"[INFO] Confidence: {result['confidence']:.3f}")
        print(f"[INFO] Alternatives: {len(result['alternative_models'])}")
    
    @pytest.mark.integration
    @pytest.mark.real_api
    async def test_cross_model_validation_real_api(self):
        """Test cross-model validation with real API calls."""
        print("\n[AI] Testing Cross-Model Validation with real API...")
        
        start_time = time.time()
        
        request = CrossValidationRequest(
            content="Python is a high-level programming language known for its simplicity and readability",
            validation_criteria=["factual_accuracy", "technical_correctness"],
            threshold=0.7
        )
        
        result = await cross_model_validation(request)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Validate response structure
        assert isinstance(result, dict)
        assert "validation_result" in result
        assert "validation_score" in result
        assert "validation_issues" in result
        assert "model_validations" in result
        assert "recommendations" in result
        
        # Validate content quality
        assert result["validation_result"] in ["VALID", "INVALID"]
        assert 0.0 <= result["validation_score"] <= 1.0
        assert isinstance(result["validation_issues"], list)
        assert isinstance(result["model_validations"], list)
        assert isinstance(result["recommendations"], list)
        
        print(f"[SUCCESS] Cross-Model Validation completed in {processing_time:.2f}s")
        print(f"[INFO] Validation result: {result['validation_result']}")
        print(f"[INFO] Score: {result['validation_score']:.3f}")
        print(f"[INFO] Issues found: {len(result['validation_issues'])}")
        print(f"[INFO] Recommendations: {len(result['recommendations'])}")
    
    @pytest.mark.integration
    @pytest.mark.real_api
    async def test_collaborative_problem_solving_real_api(self):
        """Test collaborative problem solving with real API calls."""
        print("\n[AI] Testing Collaborative Problem Solving with real API...")
        
        start_time = time.time()
        
        request = CollaborativeSolvingRequest(
            problem="Design a simple recycling program for a small office",
            requirements={"budget": "low", "participation": "voluntary"},
            max_iterations=2
        )
        
        result = await collaborative_problem_solving(request)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Validate response structure
        assert isinstance(result, dict)
        assert "final_solution" in result
        assert "solution_path" in result
        assert "alternative_solutions" in result
        assert "quality_assessment" in result
        assert "component_contributions" in result
        
        # Validate content quality
        assert isinstance(result["final_solution"], str)
        assert len(result["final_solution"]) > 100  # Should be comprehensive
        assert isinstance(result["solution_path"], list)
        assert isinstance(result["alternative_solutions"], list)
        assert isinstance(result["quality_assessment"], dict)
        
        print(f"[SUCCESS] Collaborative Problem Solving completed in {processing_time:.2f}s")
        print(f"[INFO] Final solution: {result['final_solution'][:100]}...")
        print(f"[INFO] Solution steps: {len(result['solution_path'])}")
        print(f"[INFO] Alternatives: {len(result['alternative_solutions'])}")
        print(f"[INFO] Strategy: {result['strategy_used']}")
    
    @pytest.mark.integration
    @pytest.mark.real_api
    @pytest.mark.performance
    async def test_all_tools_performance_benchmark(self):
        """Benchmark performance of all collective intelligence tools."""
        print("\n[AI] Running performance benchmark for all tools...")
        
        total_start_time = time.time()
        performance_results = {}
        
        # Test collective chat
        start_time = time.time()
        try:
            request = CollectiveChatRequest(
                prompt="Briefly explain machine learning",
                min_models=2,
                max_models=3
            )
            await collective_chat_completion(request)
            performance_results["collective_chat"] = time.time() - start_time
            print(f"[PERF] Collective Chat: {performance_results['collective_chat']:.2f}s")
        except Exception as e:
            print(f"[ERROR] Collective Chat failed: {str(e)}")
            performance_results["collective_chat"] = None
        
        # Test ensemble reasoning
        start_time = time.time()
        try:
            request = EnsembleReasoningRequest(
                problem="List benefits of exercise",
                task_type="analysis",
                decompose=False  # Faster for benchmark
            )
            await ensemble_reasoning(request)
            performance_results["ensemble_reasoning"] = time.time() - start_time
            print(f"[PERF] Ensemble Reasoning: {performance_results['ensemble_reasoning']:.2f}s")
        except Exception as e:
            print(f"[ERROR] Ensemble Reasoning failed: {str(e)}")
            performance_results["ensemble_reasoning"] = None
        
        # Test adaptive model selection
        start_time = time.time()
        try:
            request = AdaptiveModelRequest(
                query="Hello world in Python",
                task_type="code_generation"
            )
            await adaptive_model_selection(request)
            performance_results["adaptive_selection"] = time.time() - start_time
            print(f"[PERF] Adaptive Selection: {performance_results['adaptive_selection']:.2f}s")
        except Exception as e:
            print(f"[ERROR] Adaptive Selection failed: {str(e)}")
            performance_results["adaptive_selection"] = None
        
        total_time = time.time() - total_start_time
        
        # Performance assertions
        successful_tests = [k for k, v in performance_results.items() if v is not None]
        assert len(successful_tests) >= 2, "At least 2 tools should complete successfully"
        
        for tool, duration in performance_results.items():
            if duration is not None:
                assert duration < 30.0, f"{tool} took too long: {duration:.2f}s"
        
        print(f"\n[SUCCESS] Performance benchmark completed in {total_time:.2f}s")
        print(f"[INFO] Successful tools: {len(successful_tests)}/3")
        return performance_results
    
    @pytest.mark.integration
    @pytest.mark.real_api
    @pytest.mark.stress
    async def test_concurrent_tool_usage(self):
        """Test concurrent usage of multiple tools."""
        print("\n[AI] Testing concurrent tool usage...")
        
        start_time = time.time()
        
        # Create multiple requests to run concurrently
        tasks = [
            collective_chat_completion(CollectiveChatRequest(
                prompt="What is AI?",
                min_models=2,
                max_models=2
            )),
            adaptive_model_selection(AdaptiveModelRequest(
                query="Simple Python script",
                task_type="code_generation"
            )),
            cross_model_validation(CrossValidationRequest(
                content="Water boils at 100°C at sea level",
                threshold=0.7
            ))
        ]
        
        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Check results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        failed_results = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful_results) >= 2, f"At least 2 concurrent tasks should succeed, got {len(successful_results)}"
        assert processing_time < 45.0, f"Concurrent execution took too long: {processing_time:.2f}s"
        
        print(f"[SUCCESS] Concurrent test completed in {processing_time:.2f}s")
        print(f"[INFO] Successful: {len(successful_results)}/{len(tasks)}")
        if failed_results:
            print(f"[WARNING] Failed tasks: {len(failed_results)}")
            for i, error in enumerate(failed_results):
                print(f"[ERROR] Task {i+1}: {str(error)}")
    
    @pytest.mark.integration 
    @pytest.mark.real_api
    @pytest.mark.quality
    async def test_response_quality_validation(self):
        """Test the quality of responses from collective intelligence tools."""
        print("\n[AI] Testing response quality validation...")
        
        # Test with a well-defined question
        request = CollectiveChatRequest(
            prompt="Explain the water cycle in 3 main steps",
            strategy="majority_vote",
            min_models=2,
            max_models=3
        )
        
        result = await collective_chat_completion(request)
        
        # Quality checks
        response = result["consensus_response"]
        
        # Length check
        assert len(response) > 100, "Response should be substantial"
        assert len(response) < 2000, "Response should be concise"
        
        # Content relevance checks
        water_cycle_terms = ["evaporation", "condensation", "precipitation", "water", "cycle"]
        found_terms = sum(1 for term in water_cycle_terms if term.lower() in response.lower())
        assert found_terms >= 3, f"Response should mention water cycle concepts, found {found_terms} terms"
        
        # Structure checks  
        assert result["confidence_score"] > 0.5, "Confidence should be reasonable"
        assert result["agreement_level"] != "NO_CONSENSUS", "Should reach some consensus"
        
        # Quality metrics validation
        if "quality_metrics" in result:
            quality = result["quality_metrics"]
            assert quality["overall_score"] > 0.4, "Overall quality should be reasonable"
        
        print(f"[SUCCESS] Response quality validation passed")
        print(f"[INFO] Response length: {len(response)} chars")
        print(f"[INFO] Water cycle terms found: {found_terms}")
        print(f"[INFO] Confidence: {result['confidence_score']:.3f}")


if __name__ == "__main__":
    """Run integration tests directly."""
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s", "--tb=short"]))