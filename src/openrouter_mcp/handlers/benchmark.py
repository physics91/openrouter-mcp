"""
Benchmark handler for comparing multiple AI models.

This module provides functionality to benchmark and compare multiple AI models
by sending the same prompt to each model and analyzing their responses.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from ..client.openrouter import OpenRouterClient
from ..models.cache import ModelCache

logger = logging.getLogger(__name__)


class BenchmarkError(Exception):
    """Custom exception for benchmark-related errors."""
    
    def __init__(self, message: str, model_id: Optional[str] = None, error_code: Optional[str] = None):
        self.model_id = model_id
        self.error_code = error_code
        super().__init__(message)


class ResponseQualityAnalyzer:
    """Advanced response quality analysis with multiple metrics."""
    
    def __init__(self):
        # Common patterns for detecting code examples
        self.code_patterns = [
            r'```[\w]*\n.*?\n```',  # Code blocks
            r'`[^`\n]+`',  # Inline code
            r'def\s+\w+\s*\(',  # Function definitions
            r'class\s+\w+\s*\(',  # Class definitions
            r'import\s+\w+',  # Import statements
        ]
    
    def analyze_response(self, prompt: str, response: str) -> Dict[str, Any]:
        """Perform comprehensive response quality analysis."""
        if not response or not response.strip():
            return {
                "quality_score": 0.0,
                "response_length": 0,
                "contains_code_example": False,
                "language_coherence_score": 0.0,
                "completeness_score": 0.0,
                "relevance_score": 0.0
            }
        
        response_length = len(response)
        
        # Check for code examples
        contains_code_example = any(
            re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            for pattern in self.code_patterns
        )
        
        # Calculate various quality metrics
        completeness_score = self._calculate_completeness(prompt, response)
        relevance_score = self._calculate_relevance(prompt, response)
        coherence_score = self._calculate_coherence(response)
        
        # Overall quality score (weighted combination)
        quality_score = (
            completeness_score * 0.4 +
            relevance_score * 0.4 +
            coherence_score * 0.2
        )
        
        return {
            "quality_score": min(quality_score, 1.0),
            "response_length": response_length,
            "contains_code_example": contains_code_example,
            "language_coherence_score": coherence_score,
            "completeness_score": completeness_score,
            "relevance_score": relevance_score
        }
    
    def _calculate_completeness(self, prompt: str, response: str) -> float:
        """Calculate how complete the response appears to be."""
        # Simple heuristic: longer responses that end with proper punctuation
        response = response.strip()
        
        if len(response) < 10:
            return 0.1
        
        # Check if response ends properly
        ends_properly = response.endswith(('.', '!', '?', '```'))
        length_factor = min(len(response) / 300, 1.0)  # Normalize to 300 chars
        
        base_score = length_factor * 0.7
        if ends_properly:
            base_score += 0.3
        
        return min(base_score, 1.0)
    
    def _calculate_relevance(self, prompt: str, response: str) -> float:
        """Calculate how relevant the response is to the prompt."""
        prompt_words = set(prompt.lower().split())
        response_words = set(response.lower().split())
        
        # Remove common stopwords for better matching
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        prompt_words = prompt_words - stopwords
        response_words = response_words - stopwords
        
        if not prompt_words:
            return 0.5  # Default score if no meaningful words in prompt
        
        # Calculate word overlap
        overlap = len(prompt_words.intersection(response_words))
        relevance_score = overlap / len(prompt_words)
        
        # Bonus for addressing the main topic
        if len(prompt_words) > 0:
            main_words = list(prompt_words)[:3]  # Consider first 3 meaningful words
            main_word_matches = sum(1 for word in main_words if word in response.lower())
            relevance_score += (main_word_matches / len(main_words)) * 0.3
        
        return min(relevance_score, 1.0)
    
    def _calculate_coherence(self, response: str) -> float:
        """Calculate language coherence score."""
        sentences = [s.strip() for s in response.split('.') if s.strip()]
        
        if len(sentences) < 2:
            return 0.7 if len(response) > 20 else 0.3
        
        # Check for proper sentence structure
        coherence_score = 0.5  # Base score
        
        # Bonus for multiple sentences
        coherence_score += min(len(sentences) / 10, 0.3)
        
        # Penalty for very short sentences (might indicate poor quality)
        avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)
        if avg_sentence_length > 20:
            coherence_score += 0.2
        
        return min(coherence_score, 1.0)


@dataclass
class BenchmarkResult:
    """Result from benchmarking a single model."""
    
    model_id: str
    prompt: str
    response: Optional[str]
    response_time_ms: float
    tokens_used: int
    cost: float
    timestamp: datetime
    error: Optional[str] = None
    # Enhanced metrics for detailed analysis
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    input_cost_per_1k_tokens: Optional[float] = None
    output_cost_per_1k_tokens: Optional[float] = None
    quality_score: Optional[float] = None
    response_length: Optional[int] = None
    contains_code_example: Optional[bool] = None
    language_coherence_score: Optional[float] = None
    throughput_tokens_per_second: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkResult":
        """Create from dictionary."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class BenchmarkMetrics:
    """Aggregated metrics for a set of benchmark results."""
    
    avg_response_time_ms: float
    avg_tokens_used: float
    avg_cost: float
    total_cost: float
    success_rate: float
    sample_count: int
    # Enhanced metrics
    avg_quality_score: Optional[float] = None
    avg_throughput: Optional[float] = None
    avg_prompt_tokens: Optional[float] = None
    avg_completion_tokens: Optional[float] = None
    cost_per_quality_point: Optional[float] = None
    
    @classmethod
    def from_results(cls, results: List[BenchmarkResult]) -> "BenchmarkMetrics":
        """Calculate metrics from benchmark results."""
        if not results:
            return cls(0, 0, 0, 0, 0, 0)
        
        successful_results = [r for r in results if r.error is None]
        success_rate = len(successful_results) / len(results) if results else 0
        
        if not successful_results:
            return cls(0, 0, 0, 0, success_rate, len(results))
        
        avg_response_time = sum(r.response_time_ms for r in successful_results) / len(successful_results)
        avg_tokens = sum(r.tokens_used for r in successful_results) / len(successful_results)
        avg_cost = sum(r.cost for r in successful_results) / len(successful_results)
        total_cost = sum(r.cost for r in results)
        
        # Calculate enhanced metrics
        quality_scores = [r.quality_score for r in successful_results if r.quality_score is not None]
        avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else None
        
        throughputs = [r.throughput_tokens_per_second for r in successful_results if r.throughput_tokens_per_second is not None]
        avg_throughput = sum(throughputs) / len(throughputs) if throughputs else None
        
        prompt_tokens = [r.prompt_tokens for r in successful_results if r.prompt_tokens is not None]
        avg_prompt_tokens = sum(prompt_tokens) / len(prompt_tokens) if prompt_tokens else None
        
        completion_tokens = [r.completion_tokens for r in successful_results if r.completion_tokens is not None]
        avg_completion_tokens = sum(completion_tokens) / len(completion_tokens) if completion_tokens else None
        
        cost_per_quality_point = avg_cost / avg_quality_score if avg_quality_score and avg_quality_score > 0 else None
        
        return cls(
            avg_response_time_ms=avg_response_time,
            avg_tokens_used=avg_tokens,
            avg_cost=avg_cost,
            total_cost=total_cost,
            success_rate=success_rate,
            sample_count=len(results),
            avg_quality_score=avg_quality_score,
            avg_throughput=avg_throughput,
            avg_prompt_tokens=avg_prompt_tokens,
            avg_completion_tokens=avg_completion_tokens,
            cost_per_quality_point=cost_per_quality_point
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ModelComparison:
    """Comparison results for multiple models."""
    
    def __init__(
        self,
        prompt: str,
        models: List[str],
        results: Dict[str, List[BenchmarkResult]],
        timestamp: datetime
    ):
        self.prompt = prompt
        self.models = models
        self.results = results
        self.timestamp = timestamp
    
    def get_metrics(self) -> Dict[str, BenchmarkMetrics]:
        """Get metrics for each model."""
        return {
            model: BenchmarkMetrics.from_results(results)
            for model, results in self.results.items()
        }
    
    def get_rankings(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get model rankings by different criteria."""
        metrics = self.get_metrics()
        
        # Rank by speed (faster is better)
        speed_ranking = sorted(
            [
                {
                    "model": model,
                    "metric": m.avg_response_time_ms,
                    "unit": "ms"
                }
                for model, m in metrics.items()
                if m.avg_response_time_ms > 0
            ],
            key=lambda x: x["metric"]
        )
        
        # Rank by cost (cheaper is better)
        cost_ranking = sorted(
            [
                {
                    "model": model,
                    "metric": m.avg_cost,
                    "unit": "$"
                }
                for model, m in metrics.items()
                if m.avg_cost > 0
            ],
            key=lambda x: x["metric"]
        )
        
        # Rank by success rate (higher is better)
        reliability_ranking = sorted(
            [
                {
                    "model": model,
                    "metric": m.success_rate * 100,
                    "unit": "%"
                }
                for model, m in metrics.items()
            ],
            key=lambda x: x["metric"],
            reverse=True
        )
        
        return {
            "speed": speed_ranking,
            "cost": cost_ranking,
            "reliability": reliability_ranking
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "prompt": self.prompt,
            "models": self.models,
            "results": {
                model: [r.to_dict() for r in results]
                for model, results in self.results.items()
            },
            "metrics": {
                model: metrics.to_dict()
                for model, metrics in self.get_metrics().items()
            },
            "rankings": self.get_rankings(),
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelComparison":
        """Create from dictionary."""
        results = {
            model: [BenchmarkResult.from_dict(r) for r in results]
            for model, results in data["results"].items()
        }
        
        return cls(
            prompt=data["prompt"],
            models=data["models"],
            results=results,
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


class BenchmarkHandler:
    """Handler for benchmarking AI models."""
    
    def __init__(self, cache_dir: str = "benchmarks", api_key: Optional[str] = None):
        """Initialize benchmark handler."""
        # Get API key from parameter or environment
        if api_key is None:
            api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not api_key:
            raise ValueError("OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable.")
        
        self.client = OpenRouterClient(api_key=api_key)
        self.model_cache = ModelCache()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    async def benchmark_model(
        self,
        model_id: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> BenchmarkResult:
        """Benchmark a single model with a prompt."""
        start_time = time.time()
        error = None
        response_text = None
        tokens_used = 0
        cost = 0.0
        
        try:
            # Make the API call
            response = await self.client.chat_completion(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract response data
            response_text = response["choices"][0]["message"]["content"]
            tokens_used = response.get("usage", {}).get("total_tokens", 0)
            
            # Calculate cost (simplified - would need actual pricing data)
            model_info = await self.model_cache.get_model_info(model_id)
            if model_info and "pricing" in model_info:
                # Simplified cost calculation
                prompt_price = model_info["pricing"].get("prompt", 0)
                completion_price = model_info["pricing"].get("completion", 0)
                
                # Convert to float if string
                if isinstance(prompt_price, str):
                    try:
                        prompt_price = float(prompt_price)
                    except (ValueError, TypeError):
                        prompt_price = 0
                
                if isinstance(completion_price, str):
                    try:
                        completion_price = float(completion_price)
                    except (ValueError, TypeError):
                        completion_price = 0
                
                # Rough estimate: assume half tokens for prompt, half for completion
                cost = (tokens_used / 2 * prompt_price + tokens_used / 2 * completion_price) / 1_000_000
            
        except Exception as e:
            error = str(e)
            logger.error(f"Error benchmarking {model_id}: {error}")
        
        response_time_ms = (time.time() - start_time) * 1000
        
        return BenchmarkResult(
            model_id=model_id,
            prompt=prompt,
            response=response_text,
            response_time_ms=response_time_ms,
            tokens_used=tokens_used,
            cost=cost,
            timestamp=datetime.now(timezone.utc),
            error=error
        )
    
    async def benchmark_models(
        self,
        models: List[str],
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        runs_per_model: int = 1
    ) -> ModelComparison:
        """Benchmark multiple models with the same prompt."""
        logger.info(f"Starting benchmark for {len(models)} models with {runs_per_model} runs each")
        
        results = {}
        
        for model_id in models:
            model_results = []
            
            for run in range(runs_per_model):
                logger.info(f"Benchmarking {model_id} (run {run + 1}/{runs_per_model})")
                
                result = await self.benchmark_model(
                    model_id=model_id,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                model_results.append(result)
                
                # Small delay between runs to avoid rate limiting
                if run < runs_per_model - 1:
                    await asyncio.sleep(0.5)
            
            results[model_id] = model_results
            
            # Delay between different models
            await asyncio.sleep(1)
        
        comparison = ModelComparison(
            prompt=prompt,
            models=models,
            results=results,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Save the comparison
        self.save_comparison(comparison)
        
        return comparison
    
    def save_comparison(self, comparison: ModelComparison, file_path: Optional[str] = None) -> str:
        """Save comparison results to a file."""
        if file_path is None:
            timestamp = comparison.timestamp.strftime("%Y%m%d_%H%M%S")
            file_path = self.cache_dir / f"benchmark_{timestamp}.json"
        else:
            file_path = Path(file_path)
        
        with open(file_path, "w") as f:
            json.dump(comparison.to_dict(), f, indent=2)
        
        logger.info(f"Saved benchmark comparison to {file_path}")
        return str(file_path)
    
    def load_comparison(self, file_path: str) -> ModelComparison:
        """Load comparison results from a file."""
        with open(file_path, "r") as f:
            data = json.load(f)
        
        return ModelComparison.from_dict(data)
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent benchmark history."""
        files = sorted(self.cache_dir.glob("benchmark_*.json"), reverse=True)[:limit]
        
        history = []
        for file in files:
            try:
                comparison = self.load_comparison(str(file))
                history.append({
                    "file": str(file),
                    "prompt": comparison.prompt[:100] + "..." if len(comparison.prompt) > 100 else comparison.prompt,
                    "models": comparison.models,
                    "timestamp": comparison.timestamp.isoformat(),
                    "metrics_summary": {
                        model: {
                            "avg_time_ms": metrics.avg_response_time_ms,
                            "avg_cost": metrics.avg_cost,
                            "success_rate": metrics.success_rate
                        }
                        for model, metrics in comparison.get_metrics().items()
                    }
                })
            except Exception as e:
                logger.error(f"Error loading benchmark file {file}: {e}")
        
        return history
    
    def format_comparison_report(self, comparison: ModelComparison) -> str:
        """Format a comparison as a readable report."""
        metrics = comparison.get_metrics()
        rankings = comparison.get_rankings()
        
        report = []
        report.append("=" * 80)
        report.append("Benchmark Comparison Report")
        report.append("=" * 80)
        report.append(f"\nPrompt: {comparison.prompt}")
        report.append(f"Timestamp: {comparison.timestamp.isoformat()}")
        report.append(f"Models Tested: {', '.join(comparison.models)}")
        
        report.append("\n" + "-" * 80)
        report.append("Model Performance Metrics")
        report.append("-" * 80)
        
        for model in comparison.models:
            m = metrics.get(model)
            if m:
                report.append(f"\n{model}:")
                report.append(f"  Average Response Time: {m.avg_response_time_ms:.2f} ms")
                report.append(f"  Average Tokens Used: {m.avg_tokens_used:.1f}")
                report.append(f"  Average Cost: ${m.avg_cost:.6f}")
                report.append(f"  Total Cost: ${m.total_cost:.6f}")
                report.append(f"  Success Rate: {m.success_rate * 100:.1f}%")
                report.append(f"  Sample Count: {m.sample_count}")
        
        report.append("\n" + "-" * 80)
        report.append("Rankings")
        report.append("-" * 80)
        
        for criterion, ranking in rankings.items():
            report.append(f"\n{criterion.capitalize()}:")
            for i, item in enumerate(ranking, 1):
                report.append(f"  {i}. {item['model']}: {item['metric']:.2f} {item['unit']}")
        
        report.append("\n" + "=" * 80)
        
        return "\n".join(report)


class EnhancedBenchmarkHandler(BenchmarkHandler):
    """Enhanced benchmark handler with advanced metrics and analysis."""
    
    def __init__(self, api_key: str, model_cache: ModelCache, results_dir: str = "benchmarks"):
        """Initialize enhanced benchmark handler."""
        self.client = OpenRouterClient(api_key=api_key)
        self.model_cache = model_cache
        self.cache_dir = Path(results_dir)
        self.results_dir = results_dir
        self.cache_dir.mkdir(exist_ok=True)
        self.quality_analyzer = ResponseQualityAnalyzer()
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    def assess_response_quality(self, prompt: str, response: str) -> float:
        """Assess the quality of a response using advanced analysis."""
        analysis = self.quality_analyzer.analyze_response(prompt, response)
        return analysis["quality_score"]
    
    def analyze_response_comprehensive(self, prompt: str, response: str) -> Dict[str, Any]:
        """Get comprehensive response analysis."""
        return self.quality_analyzer.analyze_response(prompt, response)
    
    def calculate_detailed_cost(self, api_response: Dict[str, Any], model_pricing: Dict[str, float]) -> Dict[str, float]:
        """Calculate detailed cost breakdown from API response."""
        usage = api_response.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        
        input_price = model_pricing.get("prompt", 0)
        output_price = model_pricing.get("completion", 0)
        
        input_cost = (prompt_tokens * input_price) / 1000
        output_cost = (completion_tokens * output_price) / 1000
        
        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": input_cost + output_cost,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens
        }
    
    async def benchmark_models_parallel(self, models: List[str], prompt: str, max_concurrent: int = 3) -> ModelComparison:
        """Benchmark multiple models in parallel for better performance."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def benchmark_with_limit(model_id: str):
            async with semaphore:
                return await self.benchmark_model(model_id, prompt)
        
        # Run benchmarks in parallel
        tasks = [benchmark_with_limit(model_id) for model_id in models]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        results = {}
        for model_id, result in zip(models, results_list):
            if isinstance(result, Exception):
                # Create error result
                error_result = BenchmarkResult(
                    model_id=model_id,
                    prompt=prompt,
                    response=None,
                    response_time_ms=0,
                    tokens_used=0,
                    cost=0,
                    timestamp=datetime.now(timezone.utc),
                    error=str(result)
                )
                results[model_id] = [error_result]
            else:
                results[model_id] = [result]
        
        return ModelComparison(
            prompt=prompt,
            models=models,
            results=results,
            timestamp=datetime.now(timezone.utc)
        )
    
    async def benchmark_model(
        self,
        model_id: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: float = 60.0
    ) -> BenchmarkResult:
        """Benchmark a single model with enhanced error handling and metrics."""
        start_time = time.time()
        error = None
        response_text = None
        tokens_used = 0
        cost = 0.0
        prompt_tokens = None
        completion_tokens = None
        quality_score = None
        response_length = None
        throughput_tokens_per_second = None
        comprehensive_analysis = {}
        
        logger.info(f"Starting benchmark for model: {model_id}")
        
        try:
            # Make the API call with timeout
            response = await asyncio.wait_for(
                self.client.chat_completion(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens
                ),
                timeout=timeout
            )
            
            # Extract response data with validation
            if not response.get("choices") or not response["choices"]:
                raise BenchmarkError(f"No choices in response from {model_id}", model_id, "NO_CHOICES")
            
            choice = response["choices"][0]
            if not choice.get("message") or not choice["message"].get("content"):
                raise BenchmarkError(f"No content in response from {model_id}", model_id, "NO_CONTENT")
            
            response_text = choice["message"]["content"]
            usage = response.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            
            # Enhanced response analysis
            if response_text and hasattr(self, 'analyze_response_comprehensive'):
                comprehensive_analysis = self.analyze_response_comprehensive(prompt, response_text)
                quality_score = comprehensive_analysis.get("quality_score")
                response_length = comprehensive_analysis.get("response_length")
            elif response_text:
                response_length = len(response_text)
                if hasattr(self, 'assess_response_quality'):
                    quality_score = self.assess_response_quality(prompt, response_text)
            
            # Enhanced cost calculation
            model_info = await self.model_cache.get_model_info(model_id)
            cost = self._calculate_cost_enhanced(model_info, prompt_tokens, completion_tokens, tokens_used)
            
            logger.info(f"Successfully benchmarked {model_id}: {tokens_used} tokens, {cost:.6f} cost")
            
        except asyncio.TimeoutError:
            error = f"Timeout after {timeout}s"
            logger.error(f"Timeout benchmarking {model_id}: {error}")
        except BenchmarkError as e:
            error = str(e)
            logger.error(f"Benchmark error for {model_id}: {error}")
        except Exception as e:
            error = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error benchmarking {model_id}: {error}", exc_info=True)
        
        response_time_ms = (time.time() - start_time) * 1000
        
        # Calculate throughput
        if response_time_ms > 0 and tokens_used > 0:
            throughput_tokens_per_second = (tokens_used / response_time_ms) * 1000
        
        # Add comprehensive analysis data to result
        result = BenchmarkResult(
            model_id=model_id,
            prompt=prompt,
            response=response_text,
            response_time_ms=response_time_ms,
            tokens_used=tokens_used,
            cost=cost,
            timestamp=datetime.now(timezone.utc),
            error=error,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            quality_score=quality_score,
            response_length=response_length,
            throughput_tokens_per_second=throughput_tokens_per_second
        )
        
        # Add comprehensive analysis fields if available
        if comprehensive_analysis:
            result.contains_code_example = comprehensive_analysis.get("contains_code_example")
            result.language_coherence_score = comprehensive_analysis.get("language_coherence_score")
        
        return result
    
    def _calculate_cost_enhanced(self, model_info: Dict[str, Any], prompt_tokens: Optional[int], 
                                completion_tokens: Optional[int], total_tokens: int) -> float:
        """Enhanced cost calculation with better error handling."""
        if not model_info or "pricing" not in model_info:
            logger.warning("No pricing information available for cost calculation")
            return 0.0
        
        try:
            prompt_price = model_info["pricing"].get("prompt", 0)
            completion_price = model_info["pricing"].get("completion", 0)
            
            # Robust type conversion
            prompt_price = self._safe_float_conversion(prompt_price, "prompt_price")
            completion_price = self._safe_float_conversion(completion_price, "completion_price")
            
            # Use actual token breakdown if available
            if prompt_tokens and completion_tokens:
                cost = (prompt_tokens * prompt_price + completion_tokens * completion_price) / 1_000_000
                logger.debug(f"Cost calculated from token breakdown: {cost}")
            else:
                # Fallback to rough estimate
                cost = (total_tokens / 2 * prompt_price + total_tokens / 2 * completion_price) / 1_000_000
                logger.debug(f"Cost estimated from total tokens: {cost}")
            
            return cost
            
        except Exception as e:
            logger.error(f"Error calculating cost: {e}")
            return 0.0
    
    def _safe_float_conversion(self, value: Any, field_name: str) -> float:
        """Safely convert a value to float with logging."""
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            try:
                return float(value)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not convert {field_name} '{value}' to float: {e}")
                return 0.0
        else:
            logger.warning(f"Unexpected type for {field_name}: {type(value)}")
            return 0.0
    
    async def benchmark_models(
        self,
        model_ids: List[str],
        prompt: str,
        runs: int = 1,
        delay_between_requests: float = 1.0,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, 'EnhancedBenchmarkResult']:
        """Benchmark multiple models with the same prompt, returning enhanced results."""
        logger.info(f"Starting benchmark for {len(model_ids)} models with {runs} runs each")
        
        results = {}
        
        for model_id in model_ids:
            model_results = []
            
            for run in range(runs):
                logger.info(f"Benchmarking {model_id} (run {run + 1}/{runs})")
                
                result = await self.benchmark_model(
                    model_id=model_id,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                model_results.append(result)
                
                # Small delay between runs to avoid rate limiting
                if run < runs_per_model - 1:
                    await asyncio.sleep(0.5)
            
            results[model_id] = model_results
            
            # Delay between different models
            await asyncio.sleep(1)
        
        comparison = ModelComparison(
            prompt=prompt,
            models=models,
            results=results,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Save the comparison
        self.save_comparison(comparison)
        
        return comparison
    
    def save_comparison(self, comparison: ModelComparison, file_path: Optional[str] = None) -> str:
        """Save comparison results to a file."""
        if file_path is None:
            timestamp = comparison.timestamp.strftime("%Y%m%d_%H%M%S")
            file_path = self.cache_dir / f"benchmark_{timestamp}.json"
        else:
            file_path = Path(file_path)
        
        with open(file_path, "w") as f:
            json.dump(comparison.to_dict(), f, indent=2)
        
        logger.info(f"Saved benchmark comparison to {file_path}")
        return str(file_path)
    
    def load_comparison(self, file_path: str) -> ModelComparison:
        """Load comparison results from a file."""
        with open(file_path, "r") as f:
            data = json.load(f)
        
        return ModelComparison.from_dict(data)
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent benchmark history."""
        files = sorted(self.cache_dir.glob("benchmark_*.json"), reverse=True)[:limit]
        
        history = []
        for file in files:
            try:
                comparison = self.load_comparison(str(file))
                history.append({
                    "file": str(file),
                    "prompt": comparison.prompt[:100] + "..." if len(comparison.prompt) > 100 else comparison.prompt,
                    "models": comparison.models,
                    "timestamp": comparison.timestamp.isoformat(),
                    "metrics_summary": {
                        model: {
                            "avg_time_ms": metrics.avg_response_time_ms,
                            "avg_cost": metrics.avg_cost,
                            "success_rate": metrics.success_rate
                        }
                        for model, metrics in comparison.get_metrics().items()
                    }
                })
            except Exception as e:
                logger.error(f"Error loading benchmark file {file}: {e}")
        
        return history
    
    def format_comparison_report(self, comparison: ModelComparison) -> str:
        """Format a comparison as a readable report."""
        metrics = comparison.get_metrics()
        rankings = comparison.get_rankings()
        
        report = []
        report.append("=" * 80)
        report.append("Benchmark Comparison Report")
        report.append("=" * 80)
        report.append(f"\nPrompt: {comparison.prompt}")
        report.append(f"Timestamp: {comparison.timestamp.isoformat()}")
        report.append(f"Models Tested: {', '.join(comparison.models)}")
        
        report.append("\n" + "-" * 80)
        report.append("Model Performance Metrics")
        report.append("-" * 80)
        
        for model in comparison.models:
            m = metrics.get(model)
            if m:
                report.append(f"\n{model}:")
                report.append(f"  Average Response Time: {m.avg_response_time_ms:.2f} ms")
                report.append(f"  Average Tokens Used: {m.avg_tokens_used:.1f}")
                report.append(f"  Average Cost: ${m.avg_cost:.6f}")
                report.append(f"  Total Cost: ${m.total_cost:.6f}")
                report.append(f"  Success Rate: {m.success_rate * 100:.1f}%")
                report.append(f"  Sample Count: {m.sample_count}")
        
        report.append("\n" + "-" * 80)
        report.append("Rankings")
        report.append("-" * 80)
        
        for criterion, ranking in rankings.items():
            report.append(f"\n{criterion.capitalize()}:")
            for i, item in enumerate(ranking, 1):
                report.append(f"  {i}. {item['model']}: {item['metric']:.2f} {item['unit']}")
        
        report.append("\n" + "=" * 80)
        
        return "\n".join(report)



class BenchmarkReportExporter:
    """Exports benchmark results to various formats."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def export_markdown(self, results: Dict[str, Any], output_path: str):
        """Export benchmark results to Markdown format."""
        lines = [
            "# Benchmark Report",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            f"- Models tested: {len(results)}",
            f"- Successful tests: {sum(1 for r in results.values() if r.success)}",
            "",
            "## Results",
            ""
        ]
        
        for model_id, result in results.items():
            lines.extend([
                f"### {model_id}",
                "",
                f"- **Success**: {'✅' if result.success else '❌'}",
            ])
            
            if result.success and hasattr(result, 'metrics'):
                lines.extend([
                    f"- **Response Time**: {result.metrics.avg_response_time:.2f}s",
                    f"- **Cost**: ${result.metrics.avg_cost:.6f}",
                    f"- **Quality Score**: {result.metrics.quality_score:.2f}",
                    f"- **Throughput**: {result.metrics.throughput:.2f} tokens/s",
                ])
            
            if result.response:
                preview = result.response[:200] + "..." if len(result.response) > 200 else result.response
                lines.extend([
                    "",
                    f"**Response Preview:**",
                    f"```",
                    preview,
                    f"```",
                ])
            
            lines.append("")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        self.logger.info(f"Markdown report exported to {output_path}")
    
    async def export_csv(self, results: Dict[str, Any], output_path: str):
        """Export benchmark results to CSV format."""
        import csv
        
        fieldnames = [
            'model_id', 'success', 'response_time', 'cost', 'quality_score',
            'throughput', 'tokens_used', 'response_length'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for model_id, result in results.items():
                row = {
                    'model_id': model_id,
                    'success': result.success,
                    'response_time': getattr(result.metrics, 'avg_response_time', 0) if hasattr(result, 'metrics') else 0,
                    'cost': getattr(result.metrics, 'avg_cost', 0) if hasattr(result, 'metrics') else 0,
                    'quality_score': getattr(result.metrics, 'quality_score', 0) if hasattr(result, 'metrics') else 0,
                    'throughput': getattr(result.metrics, 'throughput', 0) if hasattr(result, 'metrics') else 0,
                    'tokens_used': getattr(result.metrics, 'avg_total_tokens', 0) if hasattr(result, 'metrics') else 0,
                    'response_length': len(result.response) if result.response else 0
                }
                writer.writerow(row)
        
        self.logger.info(f"CSV report exported to {output_path}")
    
    async def export_json(self, results: Dict[str, Any], output_path: str):
        """Export benchmark results to JSON format."""
        export_data = {
            'timestamp': datetime.now().isoformat(),
            'results': {}
        }
        
        for model_id, result in results.items():
            result_data = {
                'model_id': model_id,
                'success': result.success,
                'response': result.response,
                'error_message': getattr(result, 'error_message', None)
            }
            
            if hasattr(result, 'metrics') and result.metrics:
                result_data['metrics'] = {
                    'avg_response_time': getattr(result.metrics, 'avg_response_time', 0),
                    'avg_cost': getattr(result.metrics, 'avg_cost', 0),
                    'quality_score': getattr(result.metrics, 'quality_score', 0),
                    'throughput': getattr(result.metrics, 'throughput', 0),
                    'avg_total_tokens': getattr(result.metrics, 'avg_total_tokens', 0),
                    'success_rate': getattr(result.metrics, 'success_rate', 1.0)
                }
            
            export_data['results'][model_id] = result_data
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"JSON report exported to {output_path}")


@dataclass
class EnhancedBenchmarkResult:
    """Enhanced benchmark result with detailed metrics."""
    
    model_id: str
    success: bool
    response: Optional[str]
    error_message: Optional[str]
    metrics: Optional['EnhancedBenchmarkMetrics']
    timestamp: datetime
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass  
class EnhancedBenchmarkMetrics:
    """Enhanced metrics with comprehensive performance data."""
    
    avg_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    avg_cost: float = 0.0
    min_cost: float = 0.0
    max_cost: float = 0.0
    avg_prompt_tokens: float = 0.0
    avg_completion_tokens: float = 0.0
    avg_total_tokens: float = 0.0
    quality_score: float = 0.0
    throughput: float = 0.0
    success_rate: float = 1.0
    speed_score: float = 0.0
    cost_score: float = 0.0
    throughput_score: float = 0.0
    
    @classmethod
    def from_benchmark_results(cls, results: List[BenchmarkResult]) -> 'EnhancedBenchmarkMetrics':
        """Create enhanced metrics from benchmark results."""
        if not results:
            return cls()
        
        successful = [r for r in results if r.error is None]
        
        if not successful:
            return cls(success_rate=0.0)
        
        # Basic metrics
        response_times = [r.response_time_ms / 1000 for r in successful]  # Convert to seconds
        costs = [r.cost for r in successful]
        
        avg_response_time = sum(response_times) / len(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        avg_cost = sum(costs) / len(costs)
        min_cost = min(costs) 
        max_cost = max(costs)
        
        # Token metrics
        prompt_tokens = [r.prompt_tokens for r in successful if r.prompt_tokens]
        completion_tokens = [r.completion_tokens for r in successful if r.completion_tokens] 
        total_tokens = [r.tokens_used for r in successful if r.tokens_used]
        
        avg_prompt_tokens = sum(prompt_tokens) / len(prompt_tokens) if prompt_tokens else 0
        avg_completion_tokens = sum(completion_tokens) / len(completion_tokens) if completion_tokens else 0
        avg_total_tokens = sum(total_tokens) / len(total_tokens) if total_tokens else 0
        
        # Quality and throughput
        quality_scores = [r.quality_score for r in successful if r.quality_score is not None]
        quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        
        throughputs = [r.throughput_tokens_per_second for r in successful if r.throughput_tokens_per_second]
        throughput = sum(throughputs) / len(throughputs) if throughputs else 0
        
        success_rate = len(successful) / len(results)
        
        # Calculate normalized scores (0-1)
        speed_score = max(0, 1.0 - (avg_response_time / 60.0))  # Normalize based on 60s max
        cost_score = max(0, 1.0 - (avg_cost * 1000))  # Normalize based on $0.001 max
        throughput_score = min(1.0, throughput / 100.0)  # Normalize based on 100 tokens/s max
        
        return cls(
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            avg_cost=avg_cost,
            min_cost=min_cost,
            max_cost=max_cost,
            avg_prompt_tokens=avg_prompt_tokens,
            avg_completion_tokens=avg_completion_tokens,
            avg_total_tokens=avg_total_tokens,
            quality_score=quality_score,
            throughput=throughput,
            success_rate=success_rate,
            speed_score=speed_score,
            cost_score=cost_score,
            throughput_score=throughput_score
        )


class ModelPerformanceAnalyzer:
    """Advanced model performance analyzer with ranking and comparison capabilities."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def rank_models(self, results: List['EnhancedBenchmarkResult']) -> List[Tuple['EnhancedBenchmarkResult', float]]:
        """Rank models by overall performance score."""
        if not results:
            return []
        
        scored_results = []
        for result in results:
            if not result.success or not result.metrics:
                scored_results.append((result, 0.0))
                continue
            
            # Calculate overall score (weighted combination)
            overall_score = (
                result.metrics.speed_score * 0.25 +
                result.metrics.cost_score * 0.25 +
                result.metrics.quality_score * 0.35 +
                result.metrics.throughput_score * 0.15
            )
            
            scored_results.append((result, overall_score))
        
        # Sort by score (highest first)
        return sorted(scored_results, key=lambda x: x[1], reverse=True)
    
    def rank_models_with_weights(self, results: List['EnhancedBenchmarkResult'], 
                               weights: Dict[str, float]) -> List[Tuple['EnhancedBenchmarkResult', float]]:
        """Rank models using custom weights."""
        if not results:
            return []
        
        scored_results = []
        for result in results:
            if not result.success or not result.metrics:
                scored_results.append((result, 0.0))
                continue
            
            # Calculate weighted score
            score = (
                result.metrics.speed_score * weights.get('speed', 0) +
                result.metrics.cost_score * weights.get('cost', 0) +
                result.metrics.quality_score * weights.get('quality', 0) +
                result.metrics.throughput_score * weights.get('throughput', 0)
            )
            
            scored_results.append((result, score))
        
        return sorted(scored_results, key=lambda x: x[1], reverse=True)
    
    def compare_models(self, results: List['EnhancedBenchmarkResult']) -> Dict[str, Any]:
        """Provide detailed comparison analysis between models."""
        if not results:
            return {}
        
        successful_results = [r for r in results if r.success and r.metrics]
        
        if not successful_results:
            return {
                "error": "No successful results to compare",
                "total_models": len(results),
                "successful_models": 0
            }
        
        # Find best performer in each category
        best_speed = min(successful_results, key=lambda r: r.metrics.avg_response_time)
        best_cost = min(successful_results, key=lambda r: r.metrics.avg_cost) 
        best_quality = max(successful_results, key=lambda r: r.metrics.quality_score)
        best_throughput = max(successful_results, key=lambda r: r.metrics.throughput)
        
        return {
            "total_models": len(results),
            "successful_models": len(successful_results),
            "best_performers": {
                "speed": {
                    "model_id": best_speed.model_id,
                    "avg_response_time": best_speed.metrics.avg_response_time
                },
                "cost": {
                    "model_id": best_cost.model_id,
                    "avg_cost": best_cost.metrics.avg_cost
                },
                "quality": {
                    "model_id": best_quality.model_id,
                    "quality_score": best_quality.metrics.quality_score
                },
                "throughput": {
                    "model_id": best_throughput.model_id,
                    "throughput": best_throughput.metrics.throughput
                }
            },
            "averages": {
                "response_time": sum(r.metrics.avg_response_time for r in successful_results) / len(successful_results),
                "cost": sum(r.metrics.avg_cost for r in successful_results) / len(successful_results),
                "quality_score": sum(r.metrics.quality_score for r in successful_results) / len(successful_results),
                "throughput": sum(r.metrics.throughput for r in successful_results) / len(successful_results)
            }
        }


# 추가 메서드들 for EnhancedBenchmarkHandler 호환성
def _patch_enhanced_benchmark_handler():
    """EnhancedBenchmarkHandler 클래스에 필요한 메서드들을 동적으로 추가합니다."""
    
    def _create_enhanced_result(self, model_id: str, benchmark_results: List[BenchmarkResult], prompt: str) -> 'EnhancedBenchmarkResult':
        """Create an enhanced benchmark result from multiple runs."""
        if not benchmark_results:
            return EnhancedBenchmarkResult(
                model_id=model_id,
                success=False,
                response=None,
                error_message="No benchmark results",
                metrics=None,
                timestamp=datetime.now(timezone.utc)
            )
        
        # Check if any runs were successful
        successful_results = [r for r in benchmark_results if r.error is None]
        
        if not successful_results:
            # All runs failed
            first_error = benchmark_results[0].error if benchmark_results else "Unknown error"
            return EnhancedBenchmarkResult(
                model_id=model_id,
                success=False,
                response=None,
                error_message=first_error,
                metrics=None,
                timestamp=datetime.now(timezone.utc)
            )
        
        # Create enhanced metrics from successful results
        metrics = EnhancedBenchmarkMetrics.from_benchmark_results(benchmark_results)
        
        # Use the best response (longest or highest quality)
        best_result = max(successful_results, key=lambda r: len(r.response or ""))
        
        return EnhancedBenchmarkResult(
            model_id=model_id,
            success=True,
            response=best_result.response,
            error_message=None,
            metrics=metrics,
            timestamp=datetime.now(timezone.utc)
        )
    
    async def save_results(self, results: Dict[str, 'EnhancedBenchmarkResult'], filename: str):
        """Save enhanced benchmark results to a JSON file."""
        output_path = os.path.join(self.results_dir, filename)
        
        # Convert results to serializable format
        serializable_results = {}
        for model_id, result in results.items():
            serializable_results[model_id] = {
                'model_id': result.model_id,
                'success': result.success,
                'response': result.response,
                'error_message': result.error_message,
                'timestamp': result.timestamp.isoformat(),
                'metrics': result.metrics.__dict__ if result.metrics else None
            }
        
        save_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'results': serializable_results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved enhanced benchmark results to {output_path}")
    
    async def benchmark_models_enhanced(
        self,
        model_ids: List[str],
        prompt: str,
        runs: int = 1,
        delay_between_requests: float = 1.0,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, 'EnhancedBenchmarkResult']:
        """Enhanced benchmark method with correct signature for mcp_benchmark.py."""
        logger.info(f"Starting enhanced benchmark for {len(model_ids)} models with {runs} runs each")
        
        results = {}
        
        for model_id in model_ids:
            model_results = []
            
            for run in range(runs):
                logger.info(f"Benchmarking {model_id} (run {run + 1}/{runs})")
                
                result = await self.benchmark_model(
                    model_id=model_id,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                model_results.append(result)
                
                # Small delay between runs to avoid rate limiting
                if run < runs - 1:
                    await asyncio.sleep(delay_between_requests / 2)
            
            # Create enhanced result from benchmark results
            enhanced_result = self._create_enhanced_result(model_id, model_results, prompt)
            results[model_id] = enhanced_result
            
            # Delay between different models
            await asyncio.sleep(delay_between_requests)
        
        return results
    
    # 메서드들을 클래스에 추가
    EnhancedBenchmarkHandler._create_enhanced_result = _create_enhanced_result
    EnhancedBenchmarkHandler.save_results = save_results
    EnhancedBenchmarkHandler.benchmark_models_enhanced = benchmark_models_enhanced

# 패치 적용
_patch_enhanced_benchmark_handler()

# MCP 도구들은 mcp_benchmark.py에서 관리됩니다.