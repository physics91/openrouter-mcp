#!/usr/bin/env python3
"""
Comprehensive test suite for Collective Intelligence MCP tools.

This script tests the 5 collective intelligence tools through direct function calls
and measures their performance and functionality.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv

# Add the src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.openrouter_mcp.handlers.collective_intelligence import (
    CollectiveChatRequest,
    EnsembleReasoningRequest,
    AdaptiveModelRequest,
    CrossValidationRequest,
    CollaborativeSolvingRequest
)

# Import the underlying functionality directly
from src.openrouter_mcp.collective_intelligence import (
    ConsensusEngine,
    EnsembleReasoner,
    AdaptiveRouter,
    CrossValidator,
    CollaborativeSolver,
    ConsensusConfig,
    ConsensusStrategy,
    TaskContext,
    TaskType,
)
from src.openrouter_mcp.client.openrouter import OpenRouterClient
from src.openrouter_mcp.handlers.collective_intelligence import OpenRouterModelProvider

# Load environment variables
load_dotenv()


class CollectiveIntelligenceTestSuite:
    """Comprehensive test suite for collective intelligence tools."""
    
    def __init__(self):
        self.client = None
        self.model_provider = None
        self.test_results = {}
        self.start_time = None
        
    async def setup(self):
        """Setup test environment."""
        print("[SETUP] Initializing test environment...")
        
        # Check API key
        if not os.getenv("OPENROUTER_API_KEY"):
            raise ValueError("OPENROUTER_API_KEY environment variable not set!")
        
        # Initialize client and model provider
        self.client = OpenRouterClient.from_env()
        self.model_provider = OpenRouterModelProvider(self.client)
        
        print("[SETUP] Test environment initialized successfully")
        
    async def teardown(self):
        """Cleanup test environment."""
        if self.client:
            await self.client.close()
        print("[TEARDOWN] Test environment cleaned up")
    
    def create_task_context(self, content: str, task_type: str = "reasoning") -> TaskContext:
        """Create a TaskContext for testing."""
        try:
            task_type_enum = TaskType(task_type.lower())
        except ValueError:
            task_type_enum = TaskType.REASONING
        
        return TaskContext(
            task_type=task_type_enum,
            content=content,
            requirements={},
            constraints={}
        )
    
    async def test_collective_chat_completion(self) -> Dict[str, Any]:
        """Test collective chat completion functionality."""
        print("\n[TEST 1/5] Testing Collective Chat Completion...")
        test_start = time.time()
        
        try:
            # Setup consensus engine
            config = ConsensusConfig(
                strategy=ConsensusStrategy.MAJORITY_VOTE,
                min_models=2,
                max_models=3,
                timeout_seconds=60.0
            )
            
            consensus_engine = ConsensusEngine(self.model_provider, config)
            
            # Create test task
            task = self.create_task_context(
                "Explain the key benefits of renewable energy in 2-3 sentences.",
                "reasoning"
            )
            
            # Process with consensus
            async with self.client:
                result = await consensus_engine.process(task)
                
                test_time = time.time() - test_start
                
                success = bool(result.consensus_content and len(result.consensus_content) > 50)
                
                return {
                    "test_name": "collective_chat_completion",
                    "success": success,
                    "response_time": test_time,
                    "consensus_response": result.consensus_content[:200] + "..." if len(result.consensus_content) > 200 else result.consensus_content,
                    "agreement_level": result.agreement_level.value,
                    "confidence_score": result.confidence_score,
                    "participating_models": result.participating_models,
                    "strategy_used": result.strategy_used.value,
                    "quality_score": result.quality_metrics.overall_score(),
                    "error": None
                }
                
        except Exception as e:
            test_time = time.time() - test_start
            print(f"[ERROR] Collective chat completion failed: {str(e)}")
            return {
                "test_name": "collective_chat_completion",
                "success": False,
                "response_time": test_time,
                "error": str(e)
            }
    
    async def test_ensemble_reasoning(self) -> Dict[str, Any]:
        """Test ensemble reasoning functionality."""
        print("\n[TEST 2/5] Testing Ensemble Reasoning...")
        test_start = time.time()
        
        try:
            ensemble_reasoner = EnsembleReasoner(self.model_provider)
            
            # Create test task
            task = self.create_task_context(
                "What are the main factors to consider when designing a sustainable city transport system?",
                "analysis"
            )
            
            # Process with ensemble reasoning
            async with self.client:
                result = await ensemble_reasoner.process(task, decompose=True)
                
                test_time = time.time() - test_start
                
                success = bool(result.final_content and len(result.sub_task_results) > 0)
                
                return {
                    "test_name": "ensemble_reasoning",
                    "success": success,
                    "response_time": test_time,
                    "final_result": result.final_content[:200] + "..." if len(result.final_content) > 200 else result.final_content,
                    "subtasks_completed": len(result.sub_task_results),
                    "strategy_used": result.decomposition_strategy.value,
                    "success_rate": result.success_rate,
                    "total_cost": result.total_cost,
                    "quality_score": result.overall_quality.overall_score(),
                    "error": None
                }
                
        except Exception as e:
            test_time = time.time() - test_start
            print(f"[ERROR] Ensemble reasoning failed: {str(e)}")
            return {
                "test_name": "ensemble_reasoning",
                "success": False,
                "response_time": test_time,
                "error": str(e)
            }
    
    async def test_adaptive_model_selection(self) -> Dict[str, Any]:
        """Test adaptive model selection functionality."""
        print("\n[TEST 3/5] Testing Adaptive Model Selection...")
        test_start = time.time()
        
        try:
            adaptive_router = AdaptiveRouter(self.model_provider)
            
            # Create test task
            task = self.create_task_context(
                "Write a Python function to implement quicksort algorithm",
                "code_generation"
            )
            
            # Process with adaptive routing
            async with self.client:
                decision = await adaptive_router.process(task)
                
                test_time = time.time() - test_start
                
                success = bool(decision.selected_model_id and decision.confidence_score > 0)
                
                return {
                    "test_name": "adaptive_model_selection",
                    "success": success,
                    "response_time": test_time,
                    "selected_model": decision.selected_model_id,
                    "selection_reasoning": decision.justification[:150] + "..." if len(decision.justification) > 150 else decision.justification,
                    "confidence": decision.confidence_score,
                    "alternatives_count": len(decision.alternative_models),
                    "strategy_used": decision.strategy_used.value,
                    "expected_performance": decision.expected_performance,
                    "error": None
                }
                
        except Exception as e:
            test_time = time.time() - test_start
            print(f"[ERROR] Adaptive model selection failed: {str(e)}")
            return {
                "test_name": "adaptive_model_selection",
                "success": False,
                "response_time": test_time,
                "error": str(e)
            }
    
    async def test_cross_model_validation(self) -> Dict[str, Any]:
        """Test cross-model validation functionality."""
        print("\n[TEST 4/5] Testing Cross-Model Validation...")
        test_start = time.time()
        
        try:
            from src.openrouter_mcp.collective_intelligence.base import ProcessingResult
            
            cross_validator = CrossValidator(self.model_provider)
            
            # Create dummy result to validate
            content = "Climate change is primarily caused by human activities, especially fossil fuel combustion."
            dummy_result = ProcessingResult(
                task_id="validation_test",
                model_id="test_model",
                content=content,
                confidence=1.0
            )
            
            # Create task context
            task = self.create_task_context(content, "analysis")
            
            # Process with cross-validation
            async with self.client:
                result = await cross_validator.process(dummy_result, task)
                
                test_time = time.time() - test_start
                
                success = result.validation_confidence > 0
                
                return {
                    "test_name": "cross_model_validation",
                    "success": success,
                    "response_time": test_time,
                    "validation_result": "VALID" if result.is_valid else "INVALID",
                    "validation_score": result.validation_confidence,
                    "issues_found": len(result.validation_report.issues),
                    "recommendations_count": len(result.improvement_suggestions),
                    "quality_score": result.quality_metrics.overall_score(),
                    "confidence": result.validation_confidence,
                    "error": None
                }
                
        except Exception as e:
            test_time = time.time() - test_start
            print(f"[ERROR] Cross-model validation failed: {str(e)}")
            return {
                "test_name": "cross_model_validation",
                "success": False,
                "response_time": test_time,
                "error": str(e)
            }
    
    async def test_collaborative_problem_solving(self) -> Dict[str, Any]:
        """Test collaborative problem solving functionality."""
        print("\n[TEST 5/5] Testing Collaborative Problem Solving...")
        test_start = time.time()
        
        try:
            collaborative_solver = CollaborativeSolver(self.model_provider)
            
            # Create test task
            task = self.create_task_context(
                "Develop a strategy to reduce food waste in restaurants and grocery stores.",
                "analysis"
            )
            task.requirements = {"stakeholders": ["restaurants", "grocery_stores", "consumers"]}
            
            # Process with collaborative solving
            async with self.client:
                result = await collaborative_solver.process(task, strategy="iterative")
                
                test_time = time.time() - test_start
                
                success = bool(result.final_content and len(result.final_content) > 100)
                
                return {
                    "test_name": "collaborative_problem_solving",
                    "success": success,
                    "response_time": test_time,
                    "final_solution": result.final_content[:200] + "..." if len(result.final_content) > 200 else result.final_content,
                    "solution_path_length": len(result.solution_path),
                    "alternative_solutions_count": len(result.alternative_solutions),
                    "confidence": result.confidence_score,
                    "quality_score": result.quality_assessment.overall_score(),
                    "strategy_used": result.session.strategy.value,
                    "components_used": result.session.components_used,
                    "error": None
                }
                
        except Exception as e:
            test_time = time.time() - test_start
            print(f"[ERROR] Collaborative problem solving failed: {str(e)}")
            return {
                "test_name": "collaborative_problem_solving",
                "success": False,
                "response_time": test_time,
                "error": str(e)
            }
    
    async def test_openrouter_integration(self) -> Dict[str, Any]:
        """Test basic OpenRouter API integration."""
        print("\n[INTEGRATION] Testing OpenRouter API Integration...")
        test_start = time.time()
        
        try:
            async with self.client:
                # Test basic API call
                models = await self.client.list_models()
                
                # Test a simple chat completion
                response = await self.client.chat_completion(
                    model="openai/gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Say 'API integration test successful'"}],
                    max_tokens=50
                )
                
                test_time = time.time() - test_start
                
                success = bool(models and response and response.get("choices"))
                
                return {
                    "test_name": "openrouter_integration",
                    "success": success,
                    "response_time": test_time,
                    "models_available": len(models) if models else 0,
                    "api_response_received": bool(response),
                    "error": None
                }
                
        except Exception as e:
            test_time = time.time() - test_start
            print(f"[ERROR] OpenRouter integration test failed: {str(e)}")
            return {
                "test_name": "openrouter_integration",
                "success": False,
                "response_time": test_time,
                "error": str(e)
            }
    
    async def run_comprehensive_test_suite(self) -> Dict[str, Any]:
        """Run the complete test suite."""
        print("=" * 70)
        print("[AI] Collective Intelligence MCP Tools - Comprehensive Test Suite")
        print("=" * 70)
        
        self.start_time = time.time()
        
        # Setup
        await self.setup()
        
        # Run all tests
        test_results = []
        
        # Test OpenRouter integration first
        integration_result = await self.test_openrouter_integration()
        test_results.append(integration_result)
        
        if integration_result["success"]:
            print("[SUCCESS] OpenRouter API integration working properly")
            
            # Run collective intelligence tests
            test_results.append(await self.test_collective_chat_completion())
            test_results.append(await self.test_ensemble_reasoning())
            test_results.append(await self.test_adaptive_model_selection())
            test_results.append(await self.test_cross_model_validation())
            test_results.append(await self.test_collaborative_problem_solving())
        else:
            print("[ERROR] OpenRouter API integration failed - skipping collective intelligence tests")
        
        # Cleanup
        await self.teardown()
        
        # Generate summary
        total_time = time.time() - self.start_time
        summary = self.generate_test_summary(test_results, total_time)
        
        return summary
    
    def generate_test_summary(self, test_results: List[Dict[str, Any]], total_time: float) -> Dict[str, Any]:
        """Generate comprehensive test summary."""
        successful_tests = [r for r in test_results if r["success"]]
        failed_tests = [r for r in test_results if not r["success"]]
        
        avg_response_time = sum(r["response_time"] for r in test_results) / len(test_results)
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(test_results),
            "successful_tests": len(successful_tests),
            "failed_tests": len(failed_tests),
            "success_rate": len(successful_tests) / len(test_results) * 100,
            "total_execution_time": total_time,
            "average_response_time": avg_response_time,
            "individual_results": test_results,
            "tools_status": {
                "collective_chat_completion": next((r["success"] for r in test_results if r["test_name"] == "collective_chat_completion"), False),
                "ensemble_reasoning": next((r["success"] for r in test_results if r["test_name"] == "ensemble_reasoning"), False),
                "adaptive_model_selection": next((r["success"] for r in test_results if r["test_name"] == "adaptive_model_selection"), False),
                "cross_model_validation": next((r["success"] for r in test_results if r["test_name"] == "cross_model_validation"), False),
                "collaborative_problem_solving": next((r["success"] for r in test_results if r["test_name"] == "collaborative_problem_solving"), False),
                "openrouter_integration": next((r["success"] for r in test_results if r["test_name"] == "openrouter_integration"), False)
            }
        }
        
        return summary


async def main():
    """Main execution function."""
    test_suite = CollectiveIntelligenceTestSuite()
    
    try:
        summary = await test_suite.run_comprehensive_test_suite()
        
        # Print summary
        print("\n" + "=" * 70)
        print("                           TEST SUMMARY REPORT")
        print("=" * 70)
        print(f"Total Tests Run: {summary['total_tests']}")
        print(f"Successful: {summary['successful_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Total Execution Time: {summary['total_execution_time']:.2f}s")
        print(f"Average Response Time: {summary['average_response_time']:.2f}s")
        
        print("\nTool Status:")
        for tool, status in summary['tools_status'].items():
            status_symbol = "✅" if status else "❌"
            print(f"  {status_symbol} {tool}: {'WORKING' if status else 'FAILED'}")
        
        print("\nDetailed Results:")
        for result in summary['individual_results']:
            status_symbol = "✅" if result["success"] else "❌"
            print(f"  {status_symbol} {result['test_name']}: {result['response_time']:.2f}s")
            if not result["success"] and result.get("error"):
                print(f"     Error: {result['error']}")
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"collective_intelligence_test_results_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        print(f"\nDetailed results saved to: {results_file}")
        
        if summary['success_rate'] >= 80:
            print("\n🎉 OVERALL RESULT: COLLECTIVE INTELLIGENCE TOOLS ARE WORKING PROPERLY!")
        else:
            print("\n⚠️  OVERALL RESULT: SOME TOOLS HAVE ISSUES THAT NEED ATTENTION")
        
        return summary
        
    except Exception as e:
        print(f"\n❌ Test suite execution failed: {str(e)}")
        return {"error": str(e), "success": False}


if __name__ == "__main__":
    asyncio.run(main())