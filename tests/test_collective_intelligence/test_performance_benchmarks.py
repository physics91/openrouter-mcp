"""
Performance benchmarks and stress tests for Collective Intelligence system.

This module provides comprehensive performance testing including load testing,
scalability analysis, and benchmarking of all CI components.
"""

import asyncio
import time
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import AsyncMock, Mock
import pytest

from src.openrouter_mcp.collective_intelligence.consensus_engine import ConsensusEngine
from src.openrouter_mcp.collective_intelligence.ensemble_reasoning import EnsembleReasoner
from src.openrouter_mcp.collective_intelligence.adaptive_router import AdaptiveRouter
from src.openrouter_mcp.collective_intelligence.cross_validator import CrossValidator
from src.openrouter_mcp.collective_intelligence.collaborative_solver import CollaborativeSolver
from src.openrouter_mcp.collective_intelligence.base import (
    TaskContext, ProcessingResult, ModelInfo, TaskType, ModelCapability
)


class PerformanceBenchmarkSuite:
    """Comprehensive performance benchmark suite for CI components."""
    
    def __init__(self):
        self.benchmark_results: Dict[str, Any] = {}
        self.test_scenarios = self._create_test_scenarios()
    
    def _create_test_scenarios(self) -> List[TaskContext]:
        """Create various test scenarios for benchmarking."""
        scenarios = []
        
        # Simple tasks
        for i in range(5):
            scenarios.append(TaskContext(
                task_id=f"simple_task_{i}",
                task_type=TaskType.FACTUAL,
                content=f"What is the capital of country {i}?",
                requirements={}
            ))
        
        # Medium complexity tasks
        for i in range(5):
            scenarios.append(TaskContext(
                task_id=f"medium_task_{i}",
                task_type=TaskType.REASONING,
                content=f"Analyze the economic impact of renewable energy adoption in developing countries. "
                       f"Consider factors such as cost, infrastructure, job creation, and environmental benefits. "
                       f"Scenario {i}: Focus on {['solar', 'wind', 'hydro', 'geothermal', 'biomass'][i]} energy.",
                requirements={"detail_level": "comprehensive", "citations": True}
            ))
        
        # Complex tasks
        for i in range(3):
            scenarios.append(TaskContext(
                task_id=f"complex_task_{i}",
                task_type=TaskType.CODE_GENERATION,
                content=f"Design and implement a distributed microservices architecture for an e-commerce platform. "
                       f"Include user authentication, product catalog, shopping cart, payment processing, "
                       f"order management, inventory tracking, and real-time analytics. "
                       f"Variant {i}: Emphasize {'scalability' if i==0 else 'security' if i==1 else 'performance'}. "
                       f"Provide complete code implementation with error handling, logging, monitoring, "
                       f"database design, API documentation, testing strategies, and deployment scripts.",
                requirements={
                    "architecture": "microservices",
                    "scalability": "high",
                    "security": "enterprise",
                    "testing": "comprehensive",
                    "documentation": "complete",
                    "deployment": "containerized"
                }
            ))
        
        return scenarios
    
    async def run_component_benchmark(
        self, 
        component_name: str, 
        component_instance: Any,
        test_scenarios: List[TaskContext],
        iterations: int = 3
    ) -> Dict[str, Any]:
        """Run benchmark for a specific component."""
        
        results = {
            'component': component_name,
            'total_tests': len(test_scenarios) * iterations,
            'successful_tests': 0,
            'failed_tests': 0,
            'response_times': [],
            'throughput': 0.0,
            'memory_usage': [],
            'error_rate': 0.0,
            'scenarios_performance': {}
        }
        
        start_time = time.time()
        
        for scenario in test_scenarios:
            scenario_results = {
                'response_times': [],
                'success_count': 0,
                'failure_count': 0
            }
            
            for iteration in range(iterations):
                try:
                    iteration_start = time.time()
                    
                    # Execute component based on type
                    if hasattr(component_instance, 'process'):
                        if component_name == 'cross_validator':
                            # Cross validator needs a result to validate
                            dummy_result = ProcessingResult(
                                task_id=scenario.task_id,
                                model_id="test_model",
                                content="Test content for validation",
                                confidence=0.8
                            )
                            await component_instance.process(dummy_result, scenario)
                        else:
                            await component_instance.process(scenario)
                    
                    iteration_time = time.time() - iteration_start
                    
                    scenario_results['response_times'].append(iteration_time)
                    scenario_results['success_count'] += 1
                    results['successful_tests'] += 1
                    results['response_times'].append(iteration_time)
                    
                except Exception as e:
                    scenario_results['failure_count'] += 1
                    results['failed_tests'] += 1
                    print(f"Benchmark failed for {component_name} on {scenario.task_id}: {str(e)}")
            
            results['scenarios_performance'][scenario.task_id] = scenario_results
        
        total_time = time.time() - start_time
        
        # Calculate metrics
        if results['response_times']:
            results['avg_response_time'] = statistics.mean(results['response_times'])
            results['median_response_time'] = statistics.median(results['response_times'])
            results['min_response_time'] = min(results['response_times'])
            results['max_response_time'] = max(results['response_times'])
            results['response_time_std'] = statistics.stdev(results['response_times']) if len(results['response_times']) > 1 else 0.0
        
        results['throughput'] = results['successful_tests'] / max(total_time, 0.001)
        results['error_rate'] = results['failed_tests'] / max(results['total_tests'], 1)
        results['total_benchmark_time'] = total_time
        
        return results


@pytest.mark.performance
class TestPerformanceBenchmarks:
    """Performance benchmark tests for all CI components."""
    
    @pytest.fixture
    def benchmark_suite(self):
        """Create benchmark suite for testing."""
        return PerformanceBenchmarkSuite()
    
    @pytest.fixture
    def performance_provider(self, performance_test_models):
        """Create high-performance mock provider for benchmarking."""
        provider = AsyncMock()
        provider.get_available_models.return_value = performance_test_models
        
        async def fast_process_task(task, model_id, **kwargs):
            # Simulate fast processing with minimal delay
            await asyncio.sleep(0.001)  # 1ms processing time
            return ProcessingResult(
                task_id=task.task_id,
                model_id=model_id,
                content=f"Fast response from {model_id} for task {task.task_id}",
                confidence=0.85,
                processing_time=0.001,
                tokens_used=100,
                cost=0.001
            )
        
        provider.process_task.side_effect = fast_process_task
        return provider
    
    @pytest.mark.asyncio
    async def test_consensus_engine_performance(self, performance_provider, benchmark_suite):
        """Benchmark ConsensusEngine performance."""
        engine = ConsensusEngine(performance_provider)
        
        results = await benchmark_suite.run_component_benchmark(
            'consensus_engine',
            engine,
            benchmark_suite.test_scenarios[:5],  # Test with first 5 scenarios
            iterations=2
        )
        
        # Performance assertions
        assert results['error_rate'] < 0.1  # Less than 10% error rate
        assert results['avg_response_time'] < 5.0  # Average response under 5 seconds
        assert results['throughput'] > 0.1  # At least 0.1 operations per second
        assert results['successful_tests'] > 0
        
        benchmark_suite.benchmark_results['consensus_engine'] = results
    
    @pytest.mark.asyncio
    async def test_ensemble_reasoning_performance(self, performance_provider, benchmark_suite):
        """Benchmark EnsembleReasoner performance."""
        reasoner = EnsembleReasoner(performance_provider)
        
        results = await benchmark_suite.run_component_benchmark(
            'ensemble_reasoning',
            reasoner,
            benchmark_suite.test_scenarios[:5],
            iterations=2
        )
        
        # Performance assertions
        assert results['error_rate'] < 0.1
        assert results['avg_response_time'] < 10.0  # Ensemble might be slower
        assert results['throughput'] > 0.05
        assert results['successful_tests'] > 0
        
        benchmark_suite.benchmark_results['ensemble_reasoning'] = results
    
    @pytest.mark.asyncio
    async def test_adaptive_router_performance(self, performance_provider, benchmark_suite):
        """Benchmark AdaptiveRouter performance."""
        router = AdaptiveRouter(performance_provider)
        
        results = await benchmark_suite.run_component_benchmark(
            'adaptive_router',
            router,
            benchmark_suite.test_scenarios[:5],
            iterations=2
        )
        
        # Performance assertions - router should be fast
        assert results['error_rate'] < 0.05  # Very low error rate expected
        assert results['avg_response_time'] < 2.0  # Should be very fast
        assert results['throughput'] > 0.5  # High throughput expected
        assert results['successful_tests'] > 0
        
        benchmark_suite.benchmark_results['adaptive_router'] = results
    
    @pytest.mark.asyncio
    async def test_cross_validator_performance(self, performance_provider, benchmark_suite):
        """Benchmark CrossValidator performance."""
        validator = CrossValidator(performance_provider)
        
        results = await benchmark_suite.run_component_benchmark(
            'cross_validator',
            validator,
            benchmark_suite.test_scenarios[:5],
            iterations=2
        )
        
        # Performance assertions
        assert results['error_rate'] < 0.2  # Validation might have higher error tolerance
        assert results['avg_response_time'] < 8.0
        assert results['throughput'] > 0.1
        assert results['successful_tests'] > 0
        
        benchmark_suite.benchmark_results['cross_validator'] = results
    
    @pytest.mark.asyncio
    async def test_collaborative_solver_performance(self, performance_provider, benchmark_suite):
        """Benchmark CollaborativeSolver performance."""
        solver = CollaborativeSolver(performance_provider)
        
        # Use simpler test scenarios for collaborative solver
        simple_scenarios = benchmark_suite.test_scenarios[:3]
        
        results = await benchmark_suite.run_component_benchmark(
            'collaborative_solver',
            solver,
            simple_scenarios,
            iterations=1  # Single iteration due to complexity
        )
        
        # Performance assertions - more lenient due to complexity
        assert results['error_rate'] < 0.3
        assert results['avg_response_time'] < 20.0  # Can be slower due to orchestration
        assert results['throughput'] > 0.01
        
        benchmark_suite.benchmark_results['collaborative_solver'] = results
    
    @pytest.mark.asyncio
    async def test_scalability_concurrent_requests(self, performance_provider):
        """Test scalability with concurrent requests."""
        engine = ConsensusEngine(performance_provider)
        
        # Create multiple tasks for concurrent processing
        concurrent_tasks = [
            TaskContext(
                task_id=f"concurrent_task_{i}",
                task_type=TaskType.REASONING,
                content=f"Concurrent reasoning task {i}"
            )
            for i in range(20)  # 20 concurrent tasks
        ]
        
        start_time = time.time()
        
        # Process all tasks concurrently
        results = await asyncio.gather(
            *[engine.process(task) for task in concurrent_tasks],
            return_exceptions=True
        )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        failed_results = [r for r in results if isinstance(r, Exception)]
        
        success_rate = len(successful_results) / len(concurrent_tasks)
        throughput = len(successful_results) / total_time
        
        # Scalability assertions
        assert success_rate > 0.8  # At least 80% success rate
        assert throughput > 1.0  # At least 1 request per second
        assert total_time < 30.0  # Complete within 30 seconds
        assert len(failed_results) < 5  # Fewer than 5 failures
    
    @pytest.mark.asyncio
    async def test_memory_efficiency(self, performance_provider):
        """Test memory efficiency during extended operations."""
        router = AdaptiveRouter(performance_provider)
        
        # Process many tasks to test memory usage
        tasks_processed = 0
        max_tasks = 100
        
        start_time = time.time()
        
        for i in range(max_tasks):
            task = TaskContext(
                task_id=f"memory_test_{i}",
                task_type=TaskType.FACTUAL,
                content=f"Memory efficiency test task {i}"
            )
            
            try:
                await router.process(task)
                tasks_processed += 1
                
                # Check processing time doesn't degrade significantly
                current_time = time.time()
                if current_time - start_time > 60:  # 1 minute timeout
                    break
                    
            except Exception as e:
                print(f"Memory test failed at task {i}: {str(e)}")
                break
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Memory efficiency assertions
        assert tasks_processed >= 50  # Process at least 50 tasks
        assert total_time < 60  # Complete within time limit
        assert total_time / max(tasks_processed, 1) < 0.5  # Less than 0.5s per task average
    
    @pytest.mark.asyncio
    async def test_stress_test_high_load(self, performance_provider):
        """Stress test with high load and complex scenarios."""
        solver = CollaborativeSolver(performance_provider)
        
        # Create stress test scenarios
        stress_scenarios = []
        for i in range(10):
            stress_scenarios.append(TaskContext(
                task_id=f"stress_task_{i}",
                task_type=TaskType.REASONING,
                content=f"Complex stress test scenario {i}: " + "A" * 1000,  # Long content
                requirements={"complexity": "high", "detail": "comprehensive"}
            ))
        
        start_time = time.time()
        stress_results = []
        
        # Process scenarios with some concurrency
        batch_size = 3
        for i in range(0, len(stress_scenarios), batch_size):
            batch = stress_scenarios[i:i+batch_size]
            batch_results = await asyncio.gather(
                *[solver.process(scenario) for scenario in batch],
                return_exceptions=True
            )
            stress_results.extend(batch_results)
            
            # Small delay between batches to prevent overwhelming
            await asyncio.sleep(0.1)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze stress test results
        successful_stress = [r for r in stress_results if not isinstance(r, Exception)]
        failed_stress = [r for r in stress_results if isinstance(r, Exception)]
        
        stress_success_rate = len(successful_stress) / len(stress_scenarios)
        
        # Stress test assertions
        assert stress_success_rate > 0.5  # At least 50% success under stress
        assert total_time < 120  # Complete within 2 minutes
        assert len(failed_stress) < len(stress_scenarios) * 0.7  # Less than 70% failures
    
    @pytest.mark.asyncio
    async def test_performance_degradation(self, performance_provider):
        """Test for performance degradation over time."""
        engine = ConsensusEngine(performance_provider)
        
        response_times = []
        test_rounds = 10
        tasks_per_round = 5
        
        for round_num in range(test_rounds):
            round_start = time.time()
            
            # Process tasks in this round
            round_tasks = [
                TaskContext(
                    task_id=f"degradation_test_r{round_num}_t{i}",
                    task_type=TaskType.REASONING,
                    content=f"Performance degradation test round {round_num}, task {i}"
                )
                for i in range(tasks_per_round)
            ]
            
            round_results = await asyncio.gather(
                *[engine.process(task) for task in round_tasks],
                return_exceptions=True
            )
            
            round_time = time.time() - round_start
            successful_in_round = len([r for r in round_results if not isinstance(r, Exception)])
            
            if successful_in_round > 0:
                avg_time_per_task = round_time / successful_in_round
                response_times.append(avg_time_per_task)
        
        # Check for performance degradation
        if len(response_times) >= 3:
            early_performance = statistics.mean(response_times[:3])
            late_performance = statistics.mean(response_times[-3:])
            
            # Performance shouldn't degrade more than 50%
            degradation_ratio = late_performance / max(early_performance, 0.001)
            assert degradation_ratio < 2.0  # Less than 2x slower
    
    @pytest.mark.asyncio
    async def test_component_comparison_benchmark(self, performance_provider, benchmark_suite):
        """Compare performance across all components."""
        components = {
            'consensus_engine': ConsensusEngine(performance_provider),
            'adaptive_router': AdaptiveRouter(performance_provider),
            'ensemble_reasoning': EnsembleReasoner(performance_provider)
        }
        
        # Common test scenario for fair comparison
        common_scenario = TaskContext(
            task_id="comparison_test",
            task_type=TaskType.REASONING,
            content="Compare the performance of different AI reasoning approaches."
        )
        
        comparison_results = {}
        
        for component_name, component_instance in components.items():
            try:
                start_time = time.time()
                
                if component_name == 'adaptive_router':
                    # Router returns routing decision, not processing result
                    result = await component_instance.process(common_scenario)
                else:
                    result = await component_instance.process(common_scenario)
                
                execution_time = time.time() - start_time
                
                comparison_results[component_name] = {
                    'execution_time': execution_time,
                    'success': True,
                    'result_type': type(result).__name__
                }
                
            except Exception as e:
                comparison_results[component_name] = {
                    'execution_time': float('inf'),
                    'success': False,
                    'error': str(e)
                }
        
        # Ensure at least one component succeeded
        successful_components = [name for name, result in comparison_results.items() if result['success']]
        assert len(successful_components) > 0
        
        # Router should be fastest (if successful)
        if 'adaptive_router' in successful_components:
            router_time = comparison_results['adaptive_router']['execution_time']
            assert router_time < 5.0  # Router should be fast
    
    def test_benchmark_suite_configuration(self, benchmark_suite):
        """Test benchmark suite configuration and test scenarios."""
        assert isinstance(benchmark_suite.test_scenarios, list)
        assert len(benchmark_suite.test_scenarios) > 0
        
        # Check scenario distribution
        simple_tasks = [s for s in benchmark_suite.test_scenarios if s.task_type == TaskType.FACTUAL]
        medium_tasks = [s for s in benchmark_suite.test_scenarios if s.task_type == TaskType.REASONING]
        complex_tasks = [s for s in benchmark_suite.test_scenarios if s.task_type == TaskType.CODE_GENERATION]
        
        assert len(simple_tasks) > 0
        assert len(medium_tasks) > 0
        assert len(complex_tasks) > 0
        
        # Check content variation
        content_lengths = [len(s.content) for s in benchmark_suite.test_scenarios]
        assert min(content_lengths) < 100  # Some simple tasks
        assert max(content_lengths) > 500  # Some complex tasks
    
    @pytest.mark.asyncio
    async def test_benchmark_result_analysis(self, performance_provider, benchmark_suite):
        """Test benchmark result analysis and reporting."""
        router = AdaptiveRouter(performance_provider)
        
        # Run a small benchmark
        results = await benchmark_suite.run_component_benchmark(
            'test_router',
            router,
            benchmark_suite.test_scenarios[:3],
            iterations=2
        )
        
        # Validate result structure
        required_fields = [
            'component', 'total_tests', 'successful_tests', 'failed_tests',
            'response_times', 'throughput', 'error_rate', 'scenarios_performance'
        ]
        
        for field in required_fields:
            assert field in results
        
        # Validate calculated metrics
        if results['response_times']:
            assert 'avg_response_time' in results
            assert 'median_response_time' in results
            assert 'min_response_time' in results
            assert 'max_response_time' in results
            assert results['min_response_time'] <= results['avg_response_time']
            assert results['avg_response_time'] <= results['max_response_time']
        
        assert 0.0 <= results['error_rate'] <= 1.0
        assert results['throughput'] >= 0.0
        assert results['total_tests'] == results['successful_tests'] + results['failed_tests']