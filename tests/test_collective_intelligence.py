#!/usr/bin/env python3
"""
Test script for Collective Intelligence MCP tools.

This script demonstrates how to use the collective intelligence capabilities
through the MCP protocol.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

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

# Load environment variables
load_dotenv()

async def test_collective_chat():
    """Test collective chat completion."""
    print("Testing Collective Chat Completion...")
    
    try:
        request = CollectiveChatRequest(
            prompt="Explain the benefits and risks of artificial intelligence in healthcare",
            strategy="majority_vote",
            min_models=2,
            max_models=3,
            temperature=0.7
        )
        
        result = await collective_chat_completion(request)
        
        print(f"[SUCCESS] Consensus Response: {result['consensus_response'][:200]}...")
        print(f"[SUCCESS] Agreement Level: {result['agreement_level']}")
        print(f"[SUCCESS] Confidence Score: {result['confidence_score']:.3f}")
        print(f"[SUCCESS] Participating Models: {len(result['participating_models'])}")
        print()
        
    except Exception as e:
        print(f"[ERROR] Collective Chat failed: {str(e)}")
        print()

async def test_ensemble_reasoning():
    """Test ensemble reasoning."""
    print("Testing Ensemble Reasoning...")
    
    try:
        request = EnsembleReasoningRequest(
            problem="Design a sustainable transportation system for a medium-sized city",
            task_type="analysis",
            decompose=True,
            temperature=0.7
        )
        
        result = await ensemble_reasoning(request)
        
        print(f"[SUCCESS] Final Result: {result['final_result'][:200]}...")
        print(f"[SUCCESS] Subtasks Completed: {len(result['subtask_results'])}")
        print(f"[SUCCESS] Processing Time: {result['processing_time']:.2f}s")
        print(f"[SUCCESS] Strategy Used: {result['strategy_used']}")
        print()
        
    except Exception as e:
        print(f"[ERROR] Ensemble Reasoning failed: {str(e)}")
        print()

async def test_adaptive_model_selection():
    """Test adaptive model selection."""
    print("Testing Adaptive Model Selection...")
    
    try:
        request = AdaptiveModelRequest(
            query="Write a Python function to implement binary search",
            task_type="code_generation",
            performance_requirements={"accuracy": 0.9, "speed": 0.7}
        )
        
        result = await adaptive_model_selection(request)
        
        print(f"[SUCCESS] Selected Model: {result['selected_model']}")
        print(f"[SUCCESS] Selection Reasoning: {result['selection_reasoning'][:150]}...")
        print(f"[SUCCESS] Confidence: {result['confidence']:.3f}")
        print(f"[SUCCESS] Alternatives: {len(result['alternative_models'])}")
        print()
        
    except Exception as e:
        print(f"[ERROR] Adaptive Model Selection failed: {str(e)}")
        print()

async def test_cross_model_validation():
    """Test cross-model validation."""
    print("Testing Cross-Model Validation...")
    
    try:
        request = CrossValidationRequest(
            content="Climate change is primarily caused by human activities, particularly the burning of fossil fuels.",
            validation_criteria=["factual_accuracy", "scientific_consensus"],
            threshold=0.7
        )
        
        result = await cross_model_validation(request)
        
        print(f"[SUCCESS] Validation Result: {result['validation_result']}")
        print(f"[SUCCESS] Validation Score: {result['validation_score']:.3f}")
        print(f"[SUCCESS] Issues Found: {len(result.get('validation_issues', []))}")
        print(f"[SUCCESS] Recommendations: {len(result.get('recommendations', []))}")
        print()
        
    except Exception as e:
        print(f"[ERROR] Cross-Model Validation failed: {str(e)}")
        print()

async def test_collaborative_problem_solving():
    """Test collaborative problem solving."""
    print("Testing Collaborative Problem Solving...")
    
    try:
        request = CollaborativeSolvingRequest(
            problem="Develop a comprehensive strategy to reduce plastic waste in urban environments",
            requirements={"stakeholders": ["residents", "businesses", "government"]},
            max_iterations=2
        )
        
        result = await collaborative_problem_solving(request)
        
        print(f"[SUCCESS] Final Solution: {result['final_solution'][:200]}...")
        print(f"[SUCCESS] Solution Steps: {len(result['solution_path'])}")
        print(f"[SUCCESS] Alternative Solutions: {len(result['alternative_solutions'])}")
        print(f"[SUCCESS] Processing Time: {result['processing_time']:.2f}s")
        print()
        
    except Exception as e:
        print(f"[ERROR] Collaborative Problem Solving failed: {str(e)}")
        print()

async def main():
    """Run all tests."""
    print("[AI] Collective Intelligence MCP Tools Test Suite")
    print("=" * 50)
    print()
    
    # Check if API key is set
    if not os.getenv("OPENROUTER_API_KEY"):
        print("[ERROR] OPENROUTER_API_KEY environment variable not set!")
        print("Please set your OpenRouter API key in .env file or environment")
        return
    
    print("[SUCCESS] OpenRouter API key found")
    print()
    
    # Run tests
    await test_collective_chat()
    await test_ensemble_reasoning()
    await test_adaptive_model_selection()
    await test_cross_model_validation()
    await test_collaborative_problem_solving()
    
    print("[SUCCESS] All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())