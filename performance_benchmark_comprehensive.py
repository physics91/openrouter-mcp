#!/usr/bin/env python3
"""
Comprehensive Performance Benchmark for MCP Collective Intelligence Tools

This module provides comprehensive performance testing for the 3 working MCP tools:
1. ensemble_reasoning
2. adaptive_model_selection  
3. cross_model_validation

Tests include:
- Response time analysis under different loads
- Throughput testing
- Concurrent request handling
- Memory and CPU usage monitoring
- Quality vs speed trade-offs
- Tool comparison analysis
"""

import asyncio
import time
import json
import psutil
import statistics
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import logging
import sys
import tracemalloc
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import MCP tools for testing
sys.path.append(str(Path(__file__).parent / "src"))

from openrouter_mcp.collective_intelligence.ensemble_reasoning import EnsembleReasoner
from openrouter_mcp.collective_intelligence.adaptive_router import AdaptiveRouter
from openrouter_mcp.collective_intelligence.cross_validator import CrossValidator
from openrouter_mcp.collective_intelligence.base import (
    TaskContext, TaskType, ModelProvider, ModelInfo, ModelCapability
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    tool_name: str
    load_level: int
    response_times: List[float] = field(default_factory=list)
    throughput: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    avg_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    test_duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MockModelInfo:
    """Mock model info for testing."""
    model_id: str
    name: str
    capabilities: Dict[ModelCapability, float]
    availability: float = 0.95
    accuracy_score: float = 0.85
    cost_per_token: float = 0.001
    response_time_avg: float = 1.5


class MockModelProvider(ModelProvider):
    """Mock model provider for testing without API calls."""
    
    def __init__(self):
        self.models = self._create_mock_models()
        self.call_count = 0
        self.error_rate = 0.05  # 5% error rate for realistic testing
    
    def _create_mock_models(self) -> List[MockModelInfo]:
        """Create mock models with different capabilities."""
        return [
            MockModelInfo(
                model_id="mock-gpt-4",
                name="Mock GPT-4",
                capabilities={
                    ModelCapability.REASONING: 0.95,
                    ModelCapability.CREATIVITY: 0.90,
                    ModelCapability.ACCURACY: 0.92,
                    ModelCapability.CODE: 0.88
                },
                response_time_avg=2.1
            ),
            MockModelInfo(
                model_id="mock-claude-3",
                name="Mock Claude-3",
                capabilities={
                    ModelCapability.REASONING: 0.93,
                    ModelCapability.ACCURACY: 0.95,
                    ModelCapability.CREATIVITY: 0.87,
                    ModelCapability.CODE: 0.85
                },
                response_time_avg=1.8
            ),
            MockModelInfo(
                model_id="mock-gemini-pro",
                name="Mock Gemini Pro",
                capabilities={
                    ModelCapability.REASONING: 0.89,
                    ModelCapability.MATH: 0.94,
                    ModelCapability.ACCURACY: 0.88,
                    ModelCapability.CODE: 0.90
                },
                response_time_avg=1.5
            ),
            MockModelInfo(
                model_id="mock-fast-model",
                name="Mock Fast Model",
                capabilities={
                    ModelCapability.REASONING: 0.75,
                    ModelCapability.CREATIVITY: 0.80,
                    ModelCapability.ACCURACY: 0.78,
                },
                response_time_avg=0.8,
                cost_per_token=0.0005
            ),
            MockModelInfo(
                model_id="mock-premium-model",
                name="Mock Premium Model",
                capabilities={
                    ModelCapability.REASONING: 0.98,
                    ModelCapability.CREATIVITY: 0.96,
                    ModelCapability.ACCURACY: 0.97,
                    ModelCapability.CODE: 0.95,
                    ModelCapability.MATH: 0.93
                },
                response_time_avg=3.2,
                cost_per_token=0.005
            )
        ]
    
    async def get_available_models(self) -> List[ModelInfo]:
        """Return mock models."""
        # Simulate API call delay
        await asyncio.sleep(0.1)
        return self.models
    
    async def process_task(self, task: TaskContext, model_id: str) -> Any:
        """Mock task processing with realistic delays and occasional failures."""
        self.call_count += 1
        
        # Find the model
        model = next((m for m in self.models if m.model_id == model_id), None)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        # Simulate processing time
        processing_time = model.response_time_avg + (hash(task.content) % 100) / 100.0
        await asyncio.sleep(processing_time)
        
        # Simulate occasional failures
        import random
        if random.random() < self.error_rate:
            raise Exception(f"Mock error in {model_id}")
        
        # Create mock result
        from openrouter_mcp.collective_intelligence.base import ProcessingResult
        return ProcessingResult(
            task_id=task.task_id,
            model_id=model_id,
            content=f"Mock response from {model.name} for: {task.content[:50]}...",
            confidence=0.8 + (hash(task.content) % 20) / 100.0,
            processing_time=processing_time,
            metadata={
                "mock": True,
                "model_name": model.name,
                "task_type": task.task_type.value
            }
        )


class ResourceMonitor:
    """Monitor system resources during testing."""
    
    def __init__(self):
        self.monitoring = False
        self.cpu_samples = []
        self.memory_samples = []
        self.monitor_thread = None
    
    def start_monitoring(self):
        """Start resource monitoring."""
        self.monitoring = True
        self.cpu_samples = []
        self.memory_samples = []
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> Tuple[float, float]:
        """Stop monitoring and return average CPU and memory usage."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        
        avg_cpu = statistics.mean(self.cpu_samples) if self.cpu_samples else 0.0
        avg_memory = statistics.mean(self.memory_samples) if self.memory_samples else 0.0
        
        return avg_cpu, avg_memory
    
    def _monitor_loop(self):
        """Monitor system resources in a loop."""
        process = psutil.Process()
        
        while self.monitoring:
            try:
                # Get CPU percentage for current process
                cpu_percent = process.cpu_percent()
                self.cpu_samples.append(cpu_percent)
                
                # Get memory usage in MB
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                self.memory_samples.append(memory_mb)
                
                time.sleep(0.1)  # Sample every 100ms
                
            except Exception as e:
                logger.warning(f"Error monitoring resources: {e}")


class PerformanceBenchmark:
    """Main performance benchmark class."""
    
    def __init__(self):
        self.mock_provider = MockModelProvider()
        self.resource_monitor = ResourceMonitor()
        self.results: List[PerformanceMetrics] = []
        
        # Initialize tools with mock provider
        self.tools = {
            "ensemble_reasoning": EnsembleReasoner(self.mock_provider),
            "adaptive_model_selection": AdaptiveRouter(self.mock_provider),
            "cross_model_validation": CrossValidator(self.mock_provider)
        }
        
        # Test scenarios
        self.test_scenarios = [
            {
                "name": "Simple Question",
                "content": "What is the capital of France?",
                "task_type": TaskType.FACTUAL,
                "expected_complexity": "low"
            },
            {
                "name": "Complex Reasoning",
                "content": "Analyze the economic implications of renewable energy adoption on traditional energy sectors, considering both short-term disruptions and long-term benefits. Provide a balanced assessment.",
                "task_type": TaskType.REASONING,
                "expected_complexity": "high"
            },
            {
                "name": "Code Generation",
                "content": "Create a Python function that implements a binary search algorithm with error handling, documentation, and unit tests. Optimize for both readability and performance.",
                "task_type": TaskType.CODE_GENERATION,
                "expected_complexity": "medium"
            },
            {
                "name": "Creative Task",
                "content": "Write a short story about artificial intelligence discovering emotions, incorporating themes of consciousness, empathy, and the nature of humanity.",
                "task_type": TaskType.CREATIVE,
                "expected_complexity": "medium"
            },
            {
                "name": "Analysis Task",
                "content": "Compare the effectiveness of different machine learning algorithms for time series forecasting, including LSTM, ARIMA, and Prophet. Consider accuracy, computational efficiency, and interpretability.",
                "task_type": TaskType.ANALYSIS,
                "expected_complexity": "high"
            }
        ]
    
    async def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """Run comprehensive performance benchmark."""
        logger.info("Starting comprehensive performance benchmark")
        
        benchmark_start = datetime.now()
        all_results = {}
        
        # Test each tool with different load levels
        load_levels = [1, 5, 10]
        
        for tool_name, tool in self.tools.items():
            logger.info(f"\nTesting tool: {tool_name}")
            tool_results = {}
            
            for load_level in load_levels:
                logger.info(f"  Testing with {load_level} concurrent requests")
                
                # Run benchmark for this tool and load level
                metrics = await self._benchmark_tool_with_load(tool_name, tool, load_level)
                tool_results[f"load_{load_level}"] = metrics
                self.results.append(metrics)
                
                # Small delay between tests
                await asyncio.sleep(1.0)
            
            all_results[tool_name] = tool_results
        
        benchmark_end = datetime.now()
        total_duration = (benchmark_end - benchmark_start).total_seconds()
        
        # Generate comprehensive report
        report = self._generate_comprehensive_report(all_results, total_duration)
        
        # Save results
        await self._save_results(all_results, report)
        
        logger.info(f"Comprehensive benchmark completed in {total_duration:.2f} seconds")
        return report
    
    async def _benchmark_tool_with_load(
        self, 
        tool_name: str, 
        tool: Any, 
        load_level: int
    ) -> PerformanceMetrics:
        """Benchmark a specific tool with a given load level."""
        
        # Start resource monitoring
        self.resource_monitor.start_monitoring()
        
        # Start memory tracking
        tracemalloc.start()
        
        test_start = time.time()
        response_times = []
        successful_requests = 0
        failed_requests = 0
        
        try:
            # Create tasks for concurrent execution
            tasks = []
            for i in range(load_level):
                # Use different scenarios for variety
                scenario = self.test_scenarios[i % len(self.test_scenarios)]
                task_context = TaskContext(
                    task_id=f"{tool_name}_load_{load_level}_req_{i}",
                    task_type=scenario["task_type"],
                    content=scenario["content"],
                    metadata={"scenario": scenario["name"], "load_test": True}
                )
                
                # Create the actual async task
                async_task = self._execute_single_request(tool, task_context)
                tasks.append(async_task)
            
            # Execute all tasks concurrently
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    failed_requests += 1
                    logger.warning(f"Request failed: {result}")
                else:
                    successful_requests += 1
                    response_times.append(result)
            
            test_duration = end_time - start_time
            
        except Exception as e:
            logger.error(f"Benchmark failed for {tool_name} with load {load_level}: {e}")
            test_duration = time.time() - test_start
            failed_requests = load_level
        
        finally:
            # Stop monitoring
            avg_cpu, avg_memory = self.resource_monitor.stop_monitoring()
            
            # Get memory usage
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            memory_usage_mb = peak / (1024 * 1024)
        
        # Calculate metrics
        total_requests = successful_requests + failed_requests
        success_rate = successful_requests / total_requests if total_requests > 0 else 0.0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0.0
        throughput = successful_requests / test_duration if test_duration > 0 else 0.0
        
        # Response time statistics
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max_response_time
            p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else max_response_time
        else:
            avg_response_time = min_response_time = max_response_time = p95_response_time = p99_response_time = 0.0
        
        return PerformanceMetrics(
            tool_name=tool_name,
            load_level=load_level,
            response_times=response_times,
            throughput=throughput,
            success_rate=success_rate,
            error_rate=error_rate,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            memory_usage_mb=max(memory_usage_mb, avg_memory),
            cpu_usage_percent=avg_cpu,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            test_duration=test_duration
        )
    
    async def _execute_single_request(self, tool: Any, task_context: TaskContext) -> float:
        """Execute a single request and return response time."""
        start_time = time.time()
        
        try:
            # All tools have a process method
            result = await tool.process(task_context)
            
            return time.time() - start_time
            
        except Exception as e:
            logger.debug(f"Request failed: {e}")
            raise
    
    def _generate_comprehensive_report(
        self, 
        all_results: Dict[str, Any], 
        total_duration: float
    ) -> Dict[str, Any]:
        """Generate comprehensive performance analysis report."""
        
        report = {
            "benchmark_summary": {
                "timestamp": datetime.now().isoformat(),
                "total_duration_seconds": total_duration,
                "tools_tested": list(all_results.keys()),
                "load_levels_tested": [1, 5, 10],
                "scenarios_tested": len(self.test_scenarios),
                "total_test_runs": len(self.results)
            },
            "performance_analysis": {},
            "comparison_analysis": {},
            "recommendations": {},
            "detailed_metrics": {}
        }
        
        # Analyze each tool's performance
        for tool_name, tool_results in all_results.items():
            tool_analysis = self._analyze_tool_performance(tool_name, tool_results)
            report["performance_analysis"][tool_name] = tool_analysis
        
        # Cross-tool comparison
        report["comparison_analysis"] = self._generate_comparison_analysis(all_results)
        
        # Performance recommendations
        report["recommendations"] = self._generate_recommendations(all_results)
        
        # Store detailed metrics
        report["detailed_metrics"] = self._format_detailed_metrics(all_results)
        
        return report
    
    def _analyze_tool_performance(self, tool_name: str, tool_results: Dict[str, PerformanceMetrics]) -> Dict[str, Any]:
        """Analyze performance characteristics of a single tool."""
        
        analysis = {
            "scalability": {},
            "reliability": {},
            "efficiency": {},
            "resource_usage": {}
        }
        
        load_levels = [1, 5, 10]
        
        # Scalability analysis
        throughputs = [tool_results[f"load_{load}"].throughput for load in load_levels]
        response_times = [tool_results[f"load_{load}"].avg_response_time for load in load_levels]
        
        # Calculate scalability score (how well throughput scales with load)
        scalability_score = self._calculate_scalability_score(load_levels, throughputs)
        
        analysis["scalability"] = {
            "score": scalability_score,
            "throughput_trend": self._calculate_trend(load_levels, throughputs),
            "response_time_trend": self._calculate_trend(load_levels, response_times),
            "max_throughput": max(throughputs),
            "throughput_degradation": (throughputs[0] - throughputs[-1]) / throughputs[0] if throughputs[0] > 0 else 0
        }
        
        # Reliability analysis
        success_rates = [tool_results[f"load_{load}"].success_rate for load in load_levels]
        error_rates = [tool_results[f"load_{load}"].error_rate for load in load_levels]
        
        analysis["reliability"] = {
            "avg_success_rate": statistics.mean(success_rates),
            "min_success_rate": min(success_rates),
            "error_rate_trend": self._calculate_trend(load_levels, error_rates),
            "stability_score": 1.0 - statistics.stdev(success_rates) if len(success_rates) > 1 else 1.0
        }
        
        # Efficiency analysis (response time consistency)
        p95_times = [tool_results[f"load_{load}"].p95_response_time for load in load_levels]
        p99_times = [tool_results[f"load_{load}"].p99_response_time for load in load_levels]
        
        analysis["efficiency"] = {
            "avg_response_time": statistics.mean(response_times),
            "response_time_consistency": 1.0 - (statistics.stdev(response_times) / statistics.mean(response_times)) if statistics.mean(response_times) > 0 else 1.0,
            "p95_response_time": statistics.mean(p95_times),
            "p99_response_time": statistics.mean(p99_times),
            "latency_score": self._calculate_latency_score(response_times, p95_times)
        }
        
        # Resource usage analysis
        memory_usage = [tool_results[f"load_{load}"].memory_usage_mb for load in load_levels]
        cpu_usage = [tool_results[f"load_{load}"].cpu_usage_percent for load in load_levels]
        
        analysis["resource_usage"] = {
            "avg_memory_mb": statistics.mean(memory_usage),
            "max_memory_mb": max(memory_usage),
            "memory_growth_rate": self._calculate_trend(load_levels, memory_usage),
            "avg_cpu_percent": statistics.mean(cpu_usage),
            "max_cpu_percent": max(cpu_usage),
            "cpu_efficiency": min(cpu_usage) / max(cpu_usage) if max(cpu_usage) > 0 else 1.0
        }
        
        return analysis
    
    def _generate_comparison_analysis(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate cross-tool comparison analysis."""
        
        comparison = {
            "performance_ranking": {},
            "use_case_recommendations": {},
            "trade_off_analysis": {}
        }
        
        tools = list(all_results.keys())
        load_levels = [1, 5, 10]
        
        # Performance ranking by different criteria
        criteria = ["throughput", "avg_response_time", "success_rate", "memory_usage_mb"]
        
        for criterion in criteria:
            rankings = []
            
            for load in load_levels:
                load_rankings = []
                
                for tool in tools:
                    metrics = all_results[tool][f"load_{load}"]
                    value = getattr(metrics, criterion, 0)
                    
                    # For response time and memory usage, lower is better
                    if criterion in ["avg_response_time", "memory_usage_mb"]:
                        score = 1.0 / (1.0 + value) if value > 0 else 1.0
                    else:
                        score = value
                    
                    load_rankings.append((tool, score, value))
                
                # Sort by score (higher is better)
                load_rankings.sort(key=lambda x: x[1], reverse=True)
                rankings.append(load_rankings)
            
            comparison["performance_ranking"][criterion] = rankings
        
        # Use case recommendations
        comparison["use_case_recommendations"] = {
            "high_throughput": self._recommend_for_throughput(all_results),
            "low_latency": self._recommend_for_latency(all_results),
            "resource_efficient": self._recommend_for_efficiency(all_results),
            "most_reliable": self._recommend_for_reliability(all_results)
        }
        
        # Trade-off analysis
        comparison["trade_off_analysis"] = self._analyze_trade_offs(all_results)
        
        return comparison
    
    def _generate_recommendations(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate actionable recommendations based on performance analysis."""
        
        recommendations = {
            "best_overall_tool": None,
            "tool_specific_recommendations": {},
            "architecture_recommendations": [],
            "optimization_opportunities": []
        }
        
        # Calculate overall scores for each tool
        overall_scores = {}
        
        for tool_name, tool_results in all_results.items():
            # Weight different factors
            weights = {
                "throughput": 0.25,
                "latency": 0.25,
                "reliability": 0.25,
                "resource_efficiency": 0.25
            }
            
            throughput_score = statistics.mean([tool_results[f"load_{load}"].throughput for load in [1, 5, 10]])
            latency_score = 1.0 / (1.0 + statistics.mean([tool_results[f"load_{load}"].avg_response_time for load in [1, 5, 10]]))
            reliability_score = statistics.mean([tool_results[f"load_{load}"].success_rate for load in [1, 5, 10]])
            efficiency_score = 1.0 / (1.0 + statistics.mean([tool_results[f"load_{load}"].memory_usage_mb for load in [1, 5, 10]]))
            
            overall_score = (
                throughput_score * weights["throughput"] +
                latency_score * weights["latency"] +
                reliability_score * weights["reliability"] +
                efficiency_score * weights["resource_efficiency"]
            )
            
            overall_scores[tool_name] = overall_score
        
        # Find best overall tool
        best_tool = max(overall_scores.items(), key=lambda x: x[1])
        recommendations["best_overall_tool"] = {
            "tool": best_tool[0],
            "score": best_tool[1],
            "reasoning": f"{best_tool[0]} achieved the highest weighted score across all performance criteria"
        }
        
        # Tool-specific recommendations
        for tool_name, tool_results in all_results.items():
            tool_recs = []
            
            # Analyze performance characteristics
            load_10_metrics = tool_results["load_10"]
            load_1_metrics = tool_results["load_1"]
            
            if load_10_metrics.success_rate < 0.9:
                tool_recs.append("Consider implementing circuit breaker pattern for better failure handling under load")
            
            if load_10_metrics.avg_response_time > load_1_metrics.avg_response_time * 3:
                tool_recs.append("Response time degrades significantly under load - consider request queuing or load balancing")
            
            if load_10_metrics.memory_usage_mb > 500:
                tool_recs.append("High memory usage detected - implement memory optimization strategies")
            
            if load_10_metrics.throughput < load_1_metrics.throughput * 0.5:
                tool_recs.append("Throughput doesn't scale well - investigate bottlenecks and consider asynchronous processing")
            
            recommendations["tool_specific_recommendations"][tool_name] = tool_recs
        
        # Architecture recommendations
        arch_recs = []
        
        if any(all_results[tool]["load_10"].error_rate > 0.1 for tool in all_results):
            arch_recs.append("Implement retry mechanisms with exponential backoff for better resilience")
        
        if any(all_results[tool]["load_10"].avg_response_time > 5.0 for tool in all_results):
            arch_recs.append("Consider implementing request timeouts and graceful degradation")
        
        arch_recs.append("Implement comprehensive monitoring and alerting for production deployment")
        arch_recs.append("Consider using connection pooling and caching for better performance")
        
        recommendations["architecture_recommendations"] = arch_recs
        
        return recommendations
    
    def _calculate_scalability_score(self, loads: List[int], throughputs: List[float]) -> float:
        """Calculate scalability score based on how well throughput scales with load."""
        if len(loads) < 2 or max(throughputs) == 0:
            return 0.0
        
        # Ideal scalability would be linear
        ideal_throughputs = [throughputs[0] * load / loads[0] for load in loads]
        
        # Calculate how close actual throughputs are to ideal
        differences = [abs(actual - ideal) / ideal for actual, ideal in zip(throughputs, ideal_throughputs) if ideal > 0]
        
        if not differences:
            return 1.0
        
        avg_difference = statistics.mean(differences)
        return max(0.0, 1.0 - avg_difference)
    
    def _calculate_trend(self, x_values: List, y_values: List) -> str:
        """Calculate trend direction (increasing, decreasing, stable)."""
        if len(y_values) < 2:
            return "stable"
        
        # Simple linear regression slope
        n = len(x_values)
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(y_values)
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"
    
    def _calculate_latency_score(self, avg_times: List[float], p95_times: List[float]) -> float:
        """Calculate latency score based on consistency."""
        if not avg_times or not p95_times:
            return 0.0
        
        # Good latency has low average and low variance
        avg_latency = statistics.mean(avg_times)
        avg_p95 = statistics.mean(p95_times)
        
        # Score based on absolute latency and consistency
        latency_score = 1.0 / (1.0 + avg_latency)
        consistency_score = avg_latency / avg_p95 if avg_p95 > 0 else 1.0
        
        return (latency_score + consistency_score) / 2
    
    def _recommend_for_throughput(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend best tool for high throughput scenarios."""
        max_throughput = 0
        best_tool = None
        
        for tool_name, tool_results in all_results.items():
            tool_max = max(tool_results[f"load_{load}"].throughput for load in [1, 5, 10])
            if tool_max > max_throughput:
                max_throughput = tool_max
                best_tool = tool_name
        
        return {
            "tool": best_tool,
            "max_throughput": max_throughput,
            "use_case": "Batch processing, high-volume API services"
        }
    
    def _recommend_for_latency(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend best tool for low latency scenarios."""
        min_latency = float('inf')
        best_tool = None
        
        for tool_name, tool_results in all_results.items():
            tool_min = min(tool_results[f"load_{load}"].avg_response_time for load in [1, 5, 10])
            if tool_min < min_latency:
                min_latency = tool_min
                best_tool = tool_name
        
        return {
            "tool": best_tool,
            "avg_response_time": min_latency,
            "use_case": "Real-time applications, interactive systems"
        }
    
    def _recommend_for_efficiency(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend best tool for resource efficiency."""
        best_efficiency = 0
        best_tool = None
        
        for tool_name, tool_results in all_results.items():
            # Efficiency = throughput / memory_usage
            efficiency = sum(
                tool_results[f"load_{load}"].throughput / max(tool_results[f"load_{load}"].memory_usage_mb, 1.0)
                for load in [1, 5, 10]
            ) / 3
            
            if efficiency > best_efficiency:
                best_efficiency = efficiency
                best_tool = tool_name
        
        return {
            "tool": best_tool,
            "efficiency_score": best_efficiency,
            "use_case": "Resource-constrained environments, cost optimization"
        }
    
    def _recommend_for_reliability(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend best tool for reliability."""
        best_reliability = 0
        best_tool = None
        
        for tool_name, tool_results in all_results.items():
            avg_success_rate = statistics.mean(
                tool_results[f"load_{load}"].success_rate for load in [1, 5, 10]
            )
            
            if avg_success_rate > best_reliability:
                best_reliability = avg_success_rate
                best_tool = tool_name
        
        return {
            "tool": best_tool,
            "avg_success_rate": best_reliability,
            "use_case": "Mission-critical applications, production systems"
        }
    
    def _analyze_trade_offs(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trade-offs between different performance aspects."""
        trade_offs = {}
        
        for tool_name, tool_results in all_results.items():
            load_10 = tool_results["load_10"]
            
            # Throughput vs Latency
            throughput_latency_ratio = load_10.throughput * load_10.avg_response_time
            
            # Quality vs Speed (using success rate as quality proxy)
            quality_speed_ratio = load_10.success_rate / max(load_10.avg_response_time, 0.001)
            
            # Resource vs Performance
            resource_performance_ratio = (load_10.throughput * load_10.success_rate) / max(load_10.memory_usage_mb, 1.0)
            
            trade_offs[tool_name] = {
                "throughput_vs_latency": throughput_latency_ratio,
                "quality_vs_speed": quality_speed_ratio,
                "resource_vs_performance": resource_performance_ratio
            }
        
        return trade_offs
    
    def _format_detailed_metrics(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Format detailed metrics for the report."""
        detailed = {}
        
        for tool_name, tool_results in all_results.items():
            tool_detailed = {}
            
            for load_key, metrics in tool_results.items():
                tool_detailed[load_key] = {
                    "response_times": {
                        "avg": metrics.avg_response_time,
                        "min": metrics.min_response_time,
                        "max": metrics.max_response_time,
                        "p95": metrics.p95_response_time,
                        "p99": metrics.p99_response_time
                    },
                    "throughput": metrics.throughput,
                    "reliability": {
                        "success_rate": metrics.success_rate,
                        "error_rate": metrics.error_rate,
                        "successful_requests": metrics.successful_requests,
                        "failed_requests": metrics.failed_requests,
                        "total_requests": metrics.total_requests
                    },
                    "resources": {
                        "memory_usage_mb": metrics.memory_usage_mb,
                        "cpu_usage_percent": metrics.cpu_usage_percent
                    },
                    "test_info": {
                        "load_level": metrics.load_level,
                        "test_duration": metrics.test_duration,
                        "timestamp": metrics.timestamp.isoformat()
                    }
                }
            
            detailed[tool_name] = tool_detailed
        
        return detailed
    
    async def _save_results(self, all_results: Dict[str, Any], report: Dict[str, Any]):
        """Save benchmark results and report to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save raw results
        results_file = f"performance_benchmark_results_{timestamp}.json"
        with open(results_file, 'w') as f:
            # Convert metrics to dictionaries for JSON serialization
            serializable_results = {}
            for tool_name, tool_data in all_results.items():
                serializable_results[tool_name] = {}
                for load_key, metrics in tool_data.items():
                    serializable_results[tool_name][load_key] = {
                        "tool_name": metrics.tool_name,
                        "load_level": metrics.load_level,
                        "response_times": metrics.response_times,
                        "throughput": metrics.throughput,
                        "success_rate": metrics.success_rate,
                        "error_rate": metrics.error_rate,
                        "avg_response_time": metrics.avg_response_time,
                        "min_response_time": metrics.min_response_time,
                        "max_response_time": metrics.max_response_time,
                        "p95_response_time": metrics.p95_response_time,
                        "p99_response_time": metrics.p99_response_time,
                        "memory_usage_mb": metrics.memory_usage_mb,
                        "cpu_usage_percent": metrics.cpu_usage_percent,
                        "total_requests": metrics.total_requests,
                        "successful_requests": metrics.successful_requests,
                        "failed_requests": metrics.failed_requests,
                        "test_duration": metrics.test_duration,
                        "timestamp": metrics.timestamp.isoformat()
                    }
            
            json.dump(serializable_results, f, indent=2)
        
        # Save comprehensive report
        report_file = f"performance_benchmark_report_{timestamp}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Generate markdown report
        markdown_file = f"performance_benchmark_report_{timestamp}.md"
        markdown_content = self._generate_markdown_report(report)
        with open(markdown_file, 'w') as f:
            f.write(markdown_content)
        
        logger.info(f"Results saved to: {results_file}")
        logger.info(f"Report saved to: {report_file}")
        logger.info(f"Markdown report saved to: {markdown_file}")
    
    def _generate_markdown_report(self, report: Dict[str, Any]) -> str:
        """Generate a markdown version of the performance report."""
        md = ["# MCP Collective Intelligence Tools - Performance Benchmark Report"]
        md.append("")
        md.append(f"**Generated:** {report['benchmark_summary']['timestamp']}")
        md.append(f"**Total Duration:** {report['benchmark_summary']['total_duration_seconds']:.2f} seconds")
        md.append("")
        
        # Executive Summary
        md.append("## Executive Summary")
        md.append("")
        best_tool = report['recommendations']['best_overall_tool']
        md.append(f"**Best Overall Tool:** {best_tool['tool']} (Score: {best_tool['score']:.3f})")
        md.append(f"**Reasoning:** {best_tool['reasoning']}")
        md.append("")
        
        # Performance Summary Table
        md.append("## Performance Summary")
        md.append("")
        md.append("| Tool | Load 1 | Load 5 | Load 10 | Avg Success Rate | Avg Response Time |")
        md.append("|------|--------|--------|---------|------------------|-------------------|")
        
        for tool_name in report['detailed_metrics']:
            load_1 = report['detailed_metrics'][tool_name]['load_1']
            load_5 = report['detailed_metrics'][tool_name]['load_5']
            load_10 = report['detailed_metrics'][tool_name]['load_10']
            
            avg_success = (load_1['reliability']['success_rate'] + 
                          load_5['reliability']['success_rate'] + 
                          load_10['reliability']['success_rate']) / 3
            
            avg_response = (load_1['response_times']['avg'] + 
                           load_5['response_times']['avg'] + 
                           load_10['response_times']['avg']) / 3
            
            md.append(f"| {tool_name} | {load_1['throughput']:.2f} | {load_5['throughput']:.2f} | {load_10['throughput']:.2f} | {avg_success:.1%} | {avg_response:.2f}s |")
        
        md.append("")
        
        # Detailed Analysis
        md.append("## Detailed Performance Analysis")
        md.append("")
        
        for tool_name, analysis in report['performance_analysis'].items():
            md.append(f"### {tool_name}")
            md.append("")
            
            md.append("**Scalability:**")
            md.append(f"- Score: {analysis['scalability']['score']:.3f}")
            md.append(f"- Max Throughput: {analysis['scalability']['max_throughput']:.2f} req/s")
            md.append(f"- Throughput Trend: {analysis['scalability']['throughput_trend']}")
            md.append("")
            
            md.append("**Reliability:**")
            md.append(f"- Average Success Rate: {analysis['reliability']['avg_success_rate']:.1%}")
            md.append(f"- Minimum Success Rate: {analysis['reliability']['min_success_rate']:.1%}")
            md.append(f"- Stability Score: {analysis['reliability']['stability_score']:.3f}")
            md.append("")
            
            md.append("**Resource Usage:**")
            md.append(f"- Average Memory: {analysis['resource_usage']['avg_memory_mb']:.1f} MB")
            md.append(f"- Maximum Memory: {analysis['resource_usage']['max_memory_mb']:.1f} MB")
            md.append(f"- Average CPU: {analysis['resource_usage']['avg_cpu_percent']:.1f}%")
            md.append("")
        
        # Recommendations
        md.append("## Recommendations")
        md.append("")
        
        md.append("### Use Case Recommendations")
        use_cases = report['comparison_analysis']['use_case_recommendations']
        
        md.append(f"**High Throughput:** {use_cases['high_throughput']['tool']} ({use_cases['high_throughput']['max_throughput']:.2f} req/s)")
        md.append(f"**Low Latency:** {use_cases['low_latency']['tool']} ({use_cases['low_latency']['avg_response_time']:.2f}s)")
        md.append(f"**Resource Efficient:** {use_cases['resource_efficient']['tool']} (Score: {use_cases['resource_efficient']['efficiency_score']:.3f})")
        md.append(f"**Most Reliable:** {use_cases['most_reliable']['tool']} ({use_cases['most_reliable']['avg_success_rate']:.1%})")
        md.append("")
        
        md.append("### Architecture Recommendations")
        for rec in report['recommendations']['architecture_recommendations']:
            md.append(f"- {rec}")
        md.append("")
        
        # Tool-specific recommendations
        md.append("### Tool-Specific Recommendations")
        for tool_name, recs in report['recommendations']['tool_specific_recommendations'].items():
            if recs:
                md.append(f"**{tool_name}:**")
                for rec in recs:
                    md.append(f"- {rec}")
                md.append("")
        
        return "\n".join(md)


async def main():
    """Main function to run the comprehensive performance benchmark."""
    print("Starting MCP Collective Intelligence Tools Performance Benchmark")
    print("=" * 70)
    
    benchmark = PerformanceBenchmark()
    
    try:
        # Run comprehensive benchmark
        report = await benchmark.run_comprehensive_benchmark()
        
        # Print summary
        print("\nBenchmark Summary:")
        print("-" * 50)
        
        best_tool = report['recommendations']['best_overall_tool']
        print(f"Best Overall Tool: {best_tool['tool']} (Score: {best_tool['score']:.3f})")
        
        print("\nUse Case Recommendations:")
        use_cases = report['comparison_analysis']['use_case_recommendations']
        print(f"  High Throughput: {use_cases['high_throughput']['tool']}")
        print(f"  Low Latency: {use_cases['low_latency']['tool']}")
        print(f"  Resource Efficient: {use_cases['resource_efficient']['tool']}")
        print(f"  Most Reliable: {use_cases['most_reliable']['tool']}")
        
        print(f"\nTotal Test Duration: {report['benchmark_summary']['total_duration_seconds']:.2f} seconds")
        print(f"Tools Tested: {', '.join(report['benchmark_summary']['tools_tested'])}")
        print(f"Load Levels: {report['benchmark_summary']['load_levels_tested']}")
        
        print("\nDetailed reports have been saved to JSON and Markdown files.")
        print("Check the generated files for comprehensive analysis and recommendations.")
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())