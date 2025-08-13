#!/usr/bin/env python3
"""
Simple test script for Collective Intelligence MCP tools.
Tests basic functionality with proper error handling.
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

# Load environment variables
load_dotenv()

# Configure output encoding for Windows
if os.name == 'nt':
    import locale
    os.system('chcp 65001 > nul')  # Set Windows console to UTF-8


class SimpleCollectiveTest:
    """Simple test suite for collective intelligence tools."""
    
    def __init__(self):
        self.results = {}
        
    async def test_openrouter_basic(self) -> Dict[str, Any]:
        """Test basic OpenRouter API connectivity."""
        print("\n[TEST] Testing OpenRouter API Basic Connectivity...")
        
        try:
            from src.openrouter_mcp.client.openrouter import OpenRouterClient
            
            # Create client
            client = OpenRouterClient.from_env()
            
            async with client:
                # Test simple API call
                try:
                    response = await client.chat_completion(
                        model="openai/gpt-3.5-turbo",
                        messages=[{"role": "user", "content": "Hello, please respond with exactly: API_TEST_SUCCESS"}],
                        max_tokens=20,
                        temperature=0
                    )
                    
                    success = bool(response and response.get("choices"))
                    content = ""
                    if success:
                        content = response["choices"][0]["message"]["content"]
                    
                    return {
                        "test": "openrouter_basic",
                        "success": success,
                        "response_content": content,
                        "has_choices": bool(response and response.get("choices")),
                        "error": None
                    }
                    
                except Exception as api_error:
                    return {
                        "test": "openrouter_basic",
                        "success": False,
                        "error": f"API call failed: {str(api_error)}"
                    }
                    
        except Exception as setup_error:
            return {
                "test": "openrouter_basic",
                "success": False,
                "error": f"Setup failed: {str(setup_error)}"
            }
    
    async def test_model_provider_creation(self) -> Dict[str, Any]:
        """Test OpenRouterModelProvider creation."""
        print("\n[TEST] Testing Model Provider Creation...")
        
        try:
            from src.openrouter_mcp.client.openrouter import OpenRouterClient
            from src.openrouter_mcp.handlers.collective_intelligence import OpenRouterModelProvider
            
            client = OpenRouterClient.from_env()
            model_provider = OpenRouterModelProvider(client)
            
            # Test model provider methods
            success = hasattr(model_provider, 'process_task') and hasattr(model_provider, 'get_available_models')
            
            return {
                "test": "model_provider_creation",
                "success": success,
                "has_process_task": hasattr(model_provider, 'process_task'),
                "has_get_available_models": hasattr(model_provider, 'get_available_models'),
                "error": None
            }
            
        except Exception as e:
            return {
                "test": "model_provider_creation",
                "success": False,
                "error": str(e)
            }
    
    async def test_task_context_creation(self) -> Dict[str, Any]:
        """Test TaskContext creation."""
        print("\n[TEST] Testing Task Context Creation...")
        
        try:
            from src.openrouter_mcp.collective_intelligence.base import TaskContext, TaskType
            
            # Create task context
            task = TaskContext(
                task_type=TaskType.REASONING,
                content="Test content",
                requirements={},
                constraints={}
            )
            
            success = bool(task and task.content == "Test content")
            
            return {
                "test": "task_context_creation",
                "success": success,
                "task_type": task.task_type.value if task else None,
                "content_matches": task.content == "Test content" if task else False,
                "error": None
            }
            
        except Exception as e:
            return {
                "test": "task_context_creation",
                "success": False,
                "error": str(e)
            }
    
    async def test_consensus_engine_init(self) -> Dict[str, Any]:
        """Test ConsensusEngine initialization."""
        print("\n[TEST] Testing Consensus Engine Initialization...")
        
        try:
            from src.openrouter_mcp.client.openrouter import OpenRouterClient
            from src.openrouter_mcp.handlers.collective_intelligence import OpenRouterModelProvider
            from src.openrouter_mcp.collective_intelligence import (
                ConsensusEngine, ConsensusConfig, ConsensusStrategy
            )
            
            client = OpenRouterClient.from_env()
            model_provider = OpenRouterModelProvider(client)
            
            # Create config
            config = ConsensusConfig(
                strategy=ConsensusStrategy.MAJORITY_VOTE,
                min_models=2,
                max_models=3,
                timeout_seconds=30.0
            )
            
            # Create consensus engine
            consensus_engine = ConsensusEngine(model_provider, config)
            
            success = bool(consensus_engine and hasattr(consensus_engine, 'process'))
            
            return {
                "test": "consensus_engine_init",
                "success": success,
                "has_process_method": hasattr(consensus_engine, 'process') if consensus_engine else False,
                "config_strategy": config.strategy.value,
                "error": None
            }
            
        except Exception as e:
            return {
                "test": "consensus_engine_init",
                "success": False,
                "error": str(e)
            }
    
    async def test_collective_intelligence_imports(self) -> Dict[str, Any]:
        """Test that all collective intelligence modules can be imported."""
        print("\n[TEST] Testing Collective Intelligence Imports...")
        
        try:
            # Test imports
            from src.openrouter_mcp.collective_intelligence import (
                ConsensusEngine,
                EnsembleReasoner,
                AdaptiveRouter,
                CrossValidator,
                CollaborativeSolver
            )
            
            modules_imported = {
                "ConsensusEngine": ConsensusEngine is not None,
                "EnsembleReasoner": EnsembleReasoner is not None,
                "AdaptiveRouter": AdaptiveRouter is not None,
                "CrossValidator": CrossValidator is not None,
                "CollaborativeSolver": CollaborativeSolver is not None
            }
            
            success = all(modules_imported.values())
            
            return {
                "test": "collective_intelligence_imports",
                "success": success,
                "modules_imported": modules_imported,
                "error": None
            }
            
        except Exception as e:
            return {
                "test": "collective_intelligence_imports",
                "success": False,
                "error": str(e)
            }
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all simple tests."""
        print("=" * 60)
        print("[AI] Collective Intelligence - Simple Test Suite")
        print("=" * 60)
        
        # Check API key
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("[ERROR] OPENROUTER_API_KEY environment variable not set!")
            return {"error": "No API key", "tests": []}
        
        print(f"[INFO] OpenRouter API key found (length: {len(api_key)})")
        
        # Run tests
        tests = [
            await self.test_collective_intelligence_imports(),
            await self.test_task_context_creation(),
            await self.test_model_provider_creation(),
            await self.test_consensus_engine_init(),
            await self.test_openrouter_basic()
        ]
        
        # Calculate summary
        successful = sum(1 for t in tests if t["success"])
        total = len(tests)
        success_rate = (successful / total) * 100 if total > 0 else 0
        
        # Print results
        print("\n" + "=" * 60)
        print("                    TEST RESULTS SUMMARY")
        print("=" * 60)
        
        for test in tests:
            status = "PASS" if test["success"] else "FAIL"
            print(f"[{status}] {test['test']}")
            if not test["success"] and test.get("error"):
                print(f"      Error: {test['error']}")
        
        print(f"\nSummary: {successful}/{total} tests passed ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            print("\nStatus: COLLECTIVE INTELLIGENCE INFRASTRUCTURE IS READY!")
        elif success_rate >= 50:
            print("\nStatus: PARTIAL SUCCESS - Some components need attention")
        else:
            print("\nStatus: MAJOR ISSUES - Infrastructure needs fixing")
        
        # Create summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total,
            "successful_tests": successful,
            "success_rate": success_rate,
            "tests": tests,
            "api_key_present": bool(api_key),
            "overall_status": "READY" if success_rate >= 80 else "NEEDS_ATTENTION"
        }
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"simple_test_results_{timestamp}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\nDetailed results saved to: {results_file}")
        
        return summary


async def main():
    """Main execution function."""
    test_suite = SimpleCollectiveTest()
    
    try:
        summary = await test_suite.run_all_tests()
        
        # Determine next steps
        if summary.get("overall_status") == "READY":
            print("\nNext Step: Ready to test individual collective intelligence tools")
        else:
            print("\nNext Step: Fix infrastructure issues before testing tools")
        
        return summary
        
    except Exception as e:
        print(f"\nTest suite execution failed: {str(e)}")
        return {"error": str(e), "success": False}


if __name__ == "__main__":
    asyncio.run(main())