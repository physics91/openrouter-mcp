"""
Benchmark handler for comparing multiple AI models.

This module provides functionality to benchmark and compare multiple AI models
by sending the same prompt to each model and analyzing their responses.
"""

import asyncio
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

from ..client.openrouter import OpenRouterClient
from ..config.constants import BenchmarkDefaults, EnvVars, ModelDefaults, PricingDefaults
from ..models.cache import ModelCache
from ..utils.env import get_env_value
from ..utils.pricing import (
    cost_for_tokens,
    estimate_cost_from_usage,
    normalize_pricing,
    parse_price,
)
from ..utils.text import CORE_ENGLISH_STOPWORDS
from .benchmark_analyzer import ModelPerformanceAnalyzer  # noqa: F401
from .benchmark_exporter import BenchmarkReportExporter  # noqa: F401

logger = logging.getLogger(__name__)


class BenchmarkError(Exception):
    """Custom exception for benchmark-related errors."""

    def __init__(
        self,
        message: str,
        model_id: Optional[str] = None,
        error_code: Optional[str] = None,
    ):
        self.model_id = model_id
        self.error_code = error_code
        super().__init__(message)


class ResponseQualityAnalyzer:
    """Advanced response quality analysis with multiple metrics."""

    def __init__(self) -> None:
        # Common patterns for detecting code examples
        self.code_patterns = [
            r"```[\w]*\n.*?\n```",  # Code blocks
            r"`[^`\n]+`",  # Inline code
            r"def\s+\w+\s*\(",  # Function definitions
            r"class\s+\w+\s*\(",  # Class definitions
            r"import\s+\w+",  # Import statements
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
                "relevance_score": 0.0,
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
        quality_score = completeness_score * 0.4 + relevance_score * 0.4 + coherence_score * 0.2

        return {
            "quality_score": min(quality_score, 1.0),
            "response_length": response_length,
            "contains_code_example": contains_code_example,
            "language_coherence_score": coherence_score,
            "completeness_score": completeness_score,
            "relevance_score": relevance_score,
        }

    def _calculate_completeness(self, prompt: str, response: str) -> float:
        """Calculate how complete the response appears to be."""
        # Simple heuristic: longer responses that end with proper punctuation
        response = response.strip()

        if len(response) < 10:
            return 0.1

        # Check if response ends properly
        ends_properly = response.endswith((".", "!", "?", "```"))
        length_factor = min(len(response) / 300, 1.0)  # Normalize to 300 chars

        base_score = length_factor * 0.7
        if ends_properly:
            base_score += 0.3

        return min(base_score, 1.0)

    def _calculate_relevance(self, prompt: str, response: str) -> float:
        """Calculate how relevant the response is to the prompt."""
        prompt_terms = self._extract_meaningful_words(prompt)
        response_terms = self._extract_meaningful_words(response)
        prompt_words = set(prompt_terms)
        response_words = set(response_terms)

        if not prompt_words:
            return 0.5  # Default score if no meaningful words in prompt

        # Calculate word overlap
        overlap = len(prompt_words.intersection(response_words))
        relevance_score = overlap / len(prompt_words)

        # Bonus for addressing the main topic
        if prompt_terms:
            main_words = prompt_terms[:3]
            main_word_matches = sum(1 for word in main_words if word in response_words)
            relevance_score += (main_word_matches / len(main_words)) * 0.3

        return min(relevance_score, 1.0)

    def _extract_meaningful_words(self, text: str) -> List[str]:
        """Extract unique, non-stopword tokens while preserving prompt order."""
        seen: set[str] = set()
        meaningful_words: List[str] = []

        for word in re.findall(r"\b[\w'-]+\b", text.lower()):
            if word in CORE_ENGLISH_STOPWORDS or word in seen:
                continue
            seen.add(word)
            meaningful_words.append(word)

        return meaningful_words

    def _calculate_coherence(self, response: str) -> float:
        """Calculate language coherence score."""
        sentences = [s.strip() for s in response.split(".") if s.strip()]

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
    # Compatibility fields used by some benchmark tools/tests
    success: Optional[bool] = None
    error_message: Optional[str] = None
    metrics: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
        if self.success is None:
            self.success = self.error is None
        if self.error_message is None and self.error:
            self.error_message = self.error

    @classmethod
    def from_standard_result(
        cls,
        *,
        model_id: str,
        prompt: str,
        response: Optional[str],
        response_time_ms: float,
        tokens_used: int,
        cost: float,
        timestamp: datetime,
        error: Optional[str] = None,
        **extra: Any,
    ) -> "BenchmarkResult":
        """Build a standard benchmark result with explicit fields."""
        return cls(
            model_id=model_id,
            prompt=prompt,
            response=response,
            response_time_ms=response_time_ms,
            tokens_used=tokens_used,
            cost=cost,
            timestamp=timestamp,
            error=error,
            **extra,
        )

    @classmethod
    def from_enhanced_result(
        cls,
        *,
        model_id: str,
        success: bool,
        response: Optional[str],
        error_message: Optional[str],
        metrics: Optional[Any] = None,
        timestamp: Optional[datetime] = None,
        **extra: Any,
    ) -> "BenchmarkResult":
        """Build a compatibility result for enhanced benchmark consumers."""
        return cls(
            model_id=model_id,
            prompt="",
            response=response,
            response_time_ms=0.0,
            tokens_used=0,
            cost=0.0,
            timestamp=timestamp or datetime.now(timezone.utc),
            error=error_message,
            success=success,
            error_message=error_message,
            metrics=metrics,
            **extra,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkResult":
        """Create from dictionary."""
        payload = dict(data)
        payload["timestamp"] = datetime.fromisoformat(payload["timestamp"])

        if {
            "prompt",
            "response_time_ms",
            "tokens_used",
            "cost",
        }.issubset(payload):
            return cls(**payload)

        return cls.from_enhanced_result(
            model_id=payload["model_id"],
            success=payload.get("success", payload.get("error") is None),
            response=payload.get("response"),
            error_message=payload.get("error_message", payload.get("error")),
            metrics=payload.get("metrics"),
            timestamp=payload["timestamp"],
            prompt_tokens=payload.get("prompt_tokens"),
            completion_tokens=payload.get("completion_tokens"),
            input_cost_per_1k_tokens=payload.get("input_cost_per_1k_tokens"),
            output_cost_per_1k_tokens=payload.get("output_cost_per_1k_tokens"),
            quality_score=payload.get("quality_score"),
            response_length=payload.get("response_length"),
            contains_code_example=payload.get("contains_code_example"),
            language_coherence_score=payload.get("language_coherence_score"),
            throughput_tokens_per_second=payload.get("throughput_tokens_per_second"),
        )


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
    avg_total_tokens: Optional[float] = None
    avg_response_length: Optional[float] = None
    avg_input_cost_per_1k_tokens: Optional[float] = None
    avg_output_cost_per_1k_tokens: Optional[float] = None

    @classmethod
    def from_results(cls, results: List[BenchmarkResult]) -> "BenchmarkMetrics":
        """Calculate metrics from benchmark results."""
        if not results:
            return cls(0, 0, 0, 0, 0, 0)

        successful_results = [r for r in results if r.error is None]
        success_rate = len(successful_results) / len(results) if results else 0

        if not successful_results:
            return cls(0, 0, 0, 0, success_rate, len(results))

        avg_response_time = sum(r.response_time_ms for r in successful_results) / len(
            successful_results
        )
        avg_tokens = sum(r.tokens_used for r in successful_results) / len(successful_results)
        avg_cost = sum(r.cost for r in successful_results) / len(successful_results)
        total_cost = sum(r.cost for r in results)

        # Calculate enhanced metrics
        quality_scores = [
            r.quality_score for r in successful_results if r.quality_score is not None
        ]
        avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else None

        throughputs = [
            r.throughput_tokens_per_second
            for r in successful_results
            if r.throughput_tokens_per_second is not None
        ]
        avg_throughput = sum(throughputs) / len(throughputs) if throughputs else None

        prompt_tokens = [r.prompt_tokens for r in successful_results if r.prompt_tokens is not None]
        avg_prompt_tokens = sum(prompt_tokens) / len(prompt_tokens) if prompt_tokens else None

        completion_tokens = [
            r.completion_tokens for r in successful_results if r.completion_tokens is not None
        ]
        avg_completion_tokens = (
            sum(completion_tokens) / len(completion_tokens) if completion_tokens else None
        )

        cost_per_quality_point = (
            avg_cost / avg_quality_score if avg_quality_score and avg_quality_score > 0 else None
        )

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
            cost_per_quality_point=cost_per_quality_point,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    # Compatibility properties for consumers expecting enhanced metric names.
    @property
    def avg_response_time(self) -> float:
        """Average response time in seconds."""
        return self.avg_response_time_ms / 1000.0

    @property
    def quality_score(self) -> float:
        """Alias for average quality score."""
        return self.avg_quality_score or 0.0

    @property
    def throughput(self) -> float:
        """Alias for average throughput (tokens/sec)."""
        return self.avg_throughput or 0.0

    @property
    def speed_score(self) -> float:
        """Normalized speed score (0-1) derived from response time."""
        avg_response_time = self.avg_response_time
        return max(0.0, 1.0 - (avg_response_time / 60.0))

    @property
    def cost_score(self) -> float:
        """Normalized cost score (0-1) derived from average cost."""
        avg_cost = self.avg_cost if self.avg_cost is not None else 0.0
        return max(0.0, 1.0 - (avg_cost * 1000.0))

    @property
    def throughput_score(self) -> float:
        """Normalized throughput score (0-1) derived from throughput."""
        throughput = self.throughput
        return min(1.0, throughput / 100.0)


class RankingEntry(TypedDict):
    """Ranking payload entry."""

    model: str
    metric: float
    unit: str


class ModelComparison:
    """Comparison results for multiple models."""

    def __init__(
        self,
        prompt: str,
        models: List[str],
        results: Dict[str, List[BenchmarkResult]],
        timestamp: datetime,
    ):
        self.prompt = prompt
        self.models = models
        self.results = results
        self.timestamp = timestamp

    def get_metrics(self) -> Dict[str, BenchmarkMetrics]:
        """Get metrics for each model."""
        return {
            model: BenchmarkMetrics.from_results(results) for model, results in self.results.items()
        }

    def get_rankings(self) -> Dict[str, List[RankingEntry]]:
        """Get model rankings by different criteria."""
        metrics = self.get_metrics()

        # Rank by speed (faster is better)
        speed_candidates: List[RankingEntry] = [
            {"model": model, "metric": m.avg_response_time_ms, "unit": "ms"}
            for model, m in metrics.items()
            if m.avg_response_time_ms > 0
        ]
        speed_ranking = sorted(speed_candidates, key=lambda x: x["metric"])

        # Rank by cost (cheaper is better)
        cost_candidates: List[RankingEntry] = [
            {"model": model, "metric": m.avg_cost, "unit": "$"}
            for model, m in metrics.items()
            if m.avg_cost > 0
        ]
        cost_ranking = sorted(cost_candidates, key=lambda x: x["metric"])

        # Rank by success rate (higher is better)
        reliability_candidates: List[RankingEntry] = [
            {"model": model, "metric": m.success_rate * 100, "unit": "%"}
            for model, m in metrics.items()
        ]
        reliability_ranking = sorted(
            reliability_candidates,
            key=lambda x: x["metric"],
            reverse=True,
        )

        return {
            "speed": speed_ranking,
            "cost": cost_ranking,
            "reliability": reliability_ranking,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "prompt": self.prompt,
            "models": self.models,
            "results": {
                model: [r.to_dict() for r in results] for model, results in self.results.items()
            },
            "metrics": {model: metrics.to_dict() for model, metrics in self.get_metrics().items()},
            "rankings": self.get_rankings(),
            "timestamp": self.timestamp.isoformat(),
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
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class BenchmarkHandler:
    """Handler for benchmarking AI models."""

    def _build_benchmark_result(
        self,
        *,
        model_id: str,
        prompt: str,
        response: Optional[str],
        response_time_ms: float,
        tokens_used: int,
        cost: float,
        timestamp: datetime,
        error: Optional[str] = None,
        **extra: Any,
    ) -> BenchmarkResult:
        """Build a benchmark result with standard fields and optional extras."""
        return BenchmarkResult.from_standard_result(
            model_id=model_id,
            prompt=prompt,
            response=response,
            response_time_ms=response_time_ms,
            tokens_used=tokens_used,
            cost=cost,
            timestamp=timestamp,
            error=error,
            **extra,
        )

    def _build_error_result(
        self,
        *,
        model_id: str,
        prompt: str,
        error: str,
        timestamp: Optional[datetime] = None,
    ) -> BenchmarkResult:
        """Build a standardized error result for failed benchmarks."""
        return self._build_benchmark_result(
            model_id=model_id,
            prompt=prompt,
            response=None,
            response_time_ms=0.0,
            tokens_used=0,
            cost=0.0,
            timestamp=timestamp or datetime.now(timezone.utc),
            error=error,
        )

    def __init__(
        self,
        cache_dir: str = BenchmarkDefaults.DEFAULT_RESULTS_DIR,
        api_key: Optional[str] = None,
        *,
        client: Optional[OpenRouterClient] = None,
        model_cache: Optional[ModelCache] = None,
    ) -> None:
        """Initialize benchmark handler."""
        if client is None:
            # Get API key from parameter or environment
            if api_key is None:
                api_key = get_env_value(EnvVars.API_KEY)

            if not api_key:
                raise ValueError(
                    f"OpenRouter API key is required. Set {EnvVars.API_KEY} environment variable."
                )

            client = OpenRouterClient(api_key=api_key)

        self.client = client
        self.model_cache = model_cache or ModelCache()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _build_prompt_messages(prompt: str) -> List[Dict[str, str]]:
        """Build a single-message chat payload for benchmarking."""
        return [{"role": "user", "content": prompt}]

    async def benchmark_model(
        self,
        model_id: str,
        prompt: str,
        temperature: float = ModelDefaults.TEMPERATURE,
        max_tokens: int = BenchmarkDefaults.DEFAULT_MAX_TOKENS,
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
                messages=self._build_prompt_messages(prompt),
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Extract response data
            response_text = response["choices"][0]["message"]["content"]
            tokens_used = response.get("usage", {}).get("total_tokens", 0)

            # Calculate cost using model pricing when available
            model_info = await self.model_cache.get_model_info(model_id)
            if model_info and "pricing" in model_info:
                cost = estimate_cost_from_usage(
                    response.get("usage", {}),
                    model_info.get("pricing", {}),
                    PricingDefaults.DEFAULT_TOKEN_PRICE,
                )

        except Exception as e:
            error = str(e)
            logger.error(f"Error benchmarking {model_id}: {error}")

        response_time_ms = (time.time() - start_time) * 1000

        return self._build_benchmark_result(
            model_id=model_id,
            prompt=prompt,
            response=response_text,
            response_time_ms=response_time_ms,
            tokens_used=tokens_used,
            cost=cost,
            timestamp=datetime.now(timezone.utc),
            error=error,
        )

    async def benchmark_models(
        self,
        models: List[str],
        prompt: str,
        temperature: float = ModelDefaults.TEMPERATURE,
        max_tokens: int = BenchmarkDefaults.DEFAULT_MAX_TOKENS,
        runs_per_model: int = BenchmarkDefaults.DEFAULT_RUNS_PER_MODEL,
    ) -> Union[ModelComparison, Dict[str, "EnhancedBenchmarkResult"]]:
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
                    max_tokens=max_tokens,
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
            timestamp=datetime.now(timezone.utc),
        )

        # Save the comparison
        self.save_comparison(comparison)

        return comparison

    def save_comparison(self, comparison: ModelComparison, file_path: Optional[str] = None) -> str:
        """Save comparison results to a file."""
        if file_path is None:
            timestamp = comparison.timestamp.strftime("%Y%m%d_%H%M%S")
            output_path = self.cache_dir / f"benchmark_{timestamp}.json"
        else:
            output_path = Path(file_path)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(comparison.to_dict(), f, indent=2)

        logger.info(f"Saved benchmark comparison to {output_path}")
        return str(output_path)

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
                history.append(
                    {
                        "file": str(file),
                        "prompt": (
                            comparison.prompt[:100] + "..."
                            if len(comparison.prompt) > 100
                            else comparison.prompt
                        ),
                        "models": comparison.models,
                        "timestamp": comparison.timestamp.isoformat(),
                        "metrics_summary": {
                            model: {
                                "avg_time_ms": metrics.avg_response_time_ms,
                                "avg_cost": metrics.avg_cost,
                                "success_rate": metrics.success_rate,
                            }
                            for model, metrics in comparison.get_metrics().items()
                        },
                    }
                )
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

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_cache: Optional[ModelCache] = None,
        results_dir: str = BenchmarkDefaults.DEFAULT_RESULTS_DIR,
        *,
        client: Optional[OpenRouterClient] = None,
    ) -> None:
        """Initialize enhanced benchmark handler."""
        super().__init__(
            cache_dir=results_dir,
            api_key=api_key,
            client=client,
            model_cache=model_cache,
        )
        self.results_dir = results_dir
        self.quality_analyzer = ResponseQualityAnalyzer()
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._executor_shutdown = False

    async def benchmark_models(
        self,
        models: Optional[List[str]] = None,
        prompt: str = BenchmarkDefaults.DEFAULT_PROMPT,
        temperature: float = ModelDefaults.TEMPERATURE,
        max_tokens: int = BenchmarkDefaults.DEFAULT_MAX_TOKENS,
        runs_per_model: int = BenchmarkDefaults.DEFAULT_RUNS_PER_MODEL,
        model_ids: Optional[List[str]] = None,
        runs: Optional[int] = None,
        delay_between_requests: float = BenchmarkDefaults.DEFAULT_DELAY_SECONDS,
    ) -> Union[ModelComparison, Dict[str, "EnhancedBenchmarkResult"]]:
        """
        Backwards-compatible benchmark wrapper.

        - If model_ids/runs are provided, delegate to benchmark_models_enhanced.
        - Otherwise, fall back to the base BenchmarkHandler implementation.
        """
        use_enhanced = model_ids is not None or runs is not None
        if use_enhanced:
            effective_ids = model_ids or models or []
            effective_runs = runs if runs is not None else runs_per_model
            return await self.benchmark_models_enhanced(
                model_ids=effective_ids,
                prompt=prompt,
                runs=effective_runs,
                delay_between_requests=delay_between_requests,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        return await super().benchmark_models(
            models=models or [],
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            runs_per_model=runs_per_model,
        )

    def assess_response_quality(self, prompt: str, response: str) -> float:
        """Assess the quality of a response using advanced analysis."""
        analysis = self.quality_analyzer.analyze_response(prompt, response)
        return float(analysis.get("quality_score", 0.0))

    def analyze_response_comprehensive(self, prompt: str, response: str) -> Dict[str, Any]:
        """Get comprehensive response analysis."""
        return self.quality_analyzer.analyze_response(prompt, response)

    def calculate_detailed_cost(
        self, api_response: Dict[str, Any], model_pricing: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate detailed cost breakdown from API response."""
        usage = api_response.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        normalized_pricing = normalize_pricing(
            model_pricing,
            PricingDefaults.DEFAULT_TOKEN_PRICE,
            normalize_units=False,
        )
        prompt_price = normalized_pricing["prompt"]
        completion_price = normalized_pricing["completion"]

        input_cost = cost_for_tokens(prompt_tokens, prompt_price)
        output_cost = cost_for_tokens(completion_tokens, completion_price)

        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": input_cost + output_cost,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }

    async def benchmark_models_parallel(
        self, models: List[str], prompt: str, max_concurrent: int = 3
    ) -> ModelComparison:
        """Benchmark multiple models in parallel for better performance."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def benchmark_with_limit(model_id: str) -> BenchmarkResult:
            async with semaphore:
                return await self.benchmark_model(model_id, prompt)

        # Run benchmarks in parallel
        tasks = [benchmark_with_limit(model_id) for model_id in models]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        results: Dict[str, List[BenchmarkResult]] = {}
        for model_id, result in zip(models, results_list):
            if isinstance(result, BaseException):
                # Create error result
                error_result = self._build_error_result(
                    model_id=model_id,
                    prompt=prompt,
                    error=str(result),
                )
                results[model_id] = [error_result]
            else:
                results[model_id] = [result]

        return ModelComparison(
            prompt=prompt,
            models=models,
            results=results,
            timestamp=datetime.now(timezone.utc),
        )

    async def benchmark_model(
        self,
        model_id: str,
        prompt: str,
        temperature: float = ModelDefaults.TEMPERATURE,
        max_tokens: int = BenchmarkDefaults.DEFAULT_MAX_TOKENS,
        timeout: float = BenchmarkDefaults.DEFAULT_TIMEOUT_SECONDS,
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
                    messages=self._build_prompt_messages(prompt),
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=timeout,
            )

            # Extract response data with validation
            if not response.get("choices") or not response["choices"]:
                raise BenchmarkError(
                    f"No choices in response from {model_id}", model_id, "NO_CHOICES"
                )

            choice = response["choices"][0]
            if not choice.get("message") or not choice["message"].get("content"):
                raise BenchmarkError(
                    f"No content in response from {model_id}", model_id, "NO_CONTENT"
                )

            response_text = choice["message"]["content"]
            usage = response.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")

            # Enhanced response analysis
            if response_text and hasattr(self, "analyze_response_comprehensive"):
                comprehensive_analysis = self.analyze_response_comprehensive(prompt, response_text)
                quality_score = comprehensive_analysis.get("quality_score")
                response_length = comprehensive_analysis.get("response_length")
            elif response_text:
                response_length = len(response_text)
                if hasattr(self, "assess_response_quality"):
                    quality_score = self.assess_response_quality(prompt, response_text)

            # Enhanced cost calculation
            model_info = await self.model_cache.get_model_info(model_id) or {}
            cost = self._calculate_cost_enhanced(
                model_info, prompt_tokens, completion_tokens, tokens_used
            )

            logger.info(
                f"Successfully benchmarked {model_id}: {tokens_used} tokens, {cost:.6f} cost"
            )

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
        result = self._build_benchmark_result(
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
            throughput_tokens_per_second=throughput_tokens_per_second,
        )

        # Add comprehensive analysis fields if available
        if comprehensive_analysis:
            result.contains_code_example = comprehensive_analysis.get("contains_code_example")
            result.language_coherence_score = comprehensive_analysis.get("language_coherence_score")

        return result

    def _calculate_cost_enhanced(
        self,
        model_info: Dict[str, Any],
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        total_tokens: int,
    ) -> float:
        """Enhanced cost calculation with better error handling."""
        if not model_info or "pricing" not in model_info:
            logger.warning("No pricing information available for cost calculation")
            return 0.0

        try:
            prompt_price = self._safe_float_conversion(
                model_info["pricing"].get("prompt", 0), "prompt_price"
            )
            completion_price = self._safe_float_conversion(
                model_info["pricing"].get("completion", 0), "completion_price"
            )

            # Use actual token breakdown if available
            if prompt_tokens is not None and completion_tokens is not None:
                cost = (
                    prompt_tokens * prompt_price + completion_tokens * completion_price
                ) / 1_000_000
                logger.debug(f"Cost calculated from token breakdown: {cost}")
            else:
                # Fallback to rough estimate
                cost = (
                    total_tokens / 2 * prompt_price + total_tokens / 2 * completion_price
                ) / 1_000_000
                logger.debug(f"Cost estimated from total tokens: {cost}")

            return cost
        except Exception as e:
            logger.error(f"Error calculating cost: {e}")
            return 0.0

    def _safe_float_conversion(self, value: Any, field_name: str) -> float:
        """Safely convert a value to float with logging."""
        result = parse_price(value)
        if result == 0.0 and value not in (0, 0.0, "0", "0.0", "", None):
            logger.warning(f"Could not convert {field_name} '{value}' to float; using 0.0")
        return float(result)

    def _create_enhanced_result(
        self, model_id: str, benchmark_results: List[BenchmarkResult], prompt: str
    ) -> "EnhancedBenchmarkResult":
        """Create an enhanced benchmark result from multiple runs."""
        if not benchmark_results:
            return EnhancedBenchmarkResult(
                model_id=model_id,
                success=False,
                response=None,
                error_message="No benchmark results",
                metrics=None,
                timestamp=datetime.now(timezone.utc),
            )

        successful_results = [r for r in benchmark_results if r.error is None]
        if not successful_results:
            first_error = benchmark_results[0].error if benchmark_results else "Unknown error"
            return EnhancedBenchmarkResult(
                model_id=model_id,
                success=False,
                response=None,
                error_message=first_error,
                metrics=None,
                timestamp=datetime.now(timezone.utc),
            )

        metrics = EnhancedBenchmarkMetrics.from_benchmark_results(benchmark_results)
        best_result = max(successful_results, key=lambda r: len(r.response or ""))

        return EnhancedBenchmarkResult(
            model_id=model_id,
            success=True,
            response=best_result.response,
            error_message=None,
            metrics=metrics,
            timestamp=datetime.now(timezone.utc),
        )

    async def save_results(
        self, results: Dict[str, "EnhancedBenchmarkResult"], filename: str
    ) -> None:
        """Save enhanced benchmark results to a JSON file."""
        output_path = self.cache_dir / filename

        serializable_results: Dict[str, Dict[str, Any]] = {}
        for model_id, result in results.items():
            serializable_results[model_id] = {
                "model_id": result.model_id,
                "success": result.success,
                "response": result.response,
                "error_message": result.error_message,
                "timestamp": result.timestamp.isoformat(),
                "metrics": result.metrics.__dict__ if result.metrics else None,
            }

        save_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": serializable_results,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved enhanced benchmark results to {output_path}")

    async def benchmark_models_enhanced(
        self,
        model_ids: List[str],
        prompt: str,
        runs: int = BenchmarkDefaults.DEFAULT_RUNS_PER_MODEL,
        delay_between_requests: float = BenchmarkDefaults.DEFAULT_DELAY_SECONDS,
        temperature: float = ModelDefaults.TEMPERATURE,
        max_tokens: int = BenchmarkDefaults.DEFAULT_MAX_TOKENS,
    ) -> Dict[str, "EnhancedBenchmarkResult"]:
        """Enhanced benchmark method with correct signature for MCP tools."""
        logger.info(
            f"Starting enhanced benchmark for {len(model_ids)} models with {runs} runs each"
        )

        results: Dict[str, "EnhancedBenchmarkResult"] = {}

        for model_id in model_ids:
            model_results: List[BenchmarkResult] = []

            for run in range(runs):
                logger.info(f"Benchmarking {model_id} (run {run + 1}/{runs})")

                result = await self.benchmark_model(
                    model_id=model_id,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                model_results.append(result)

                if run < runs - 1:
                    await asyncio.sleep(delay_between_requests / 2)

            enhanced_result = self._create_enhanced_result(model_id, model_results, prompt)
            results[model_id] = enhanced_result

            await asyncio.sleep(delay_between_requests)

        return results

    def shutdown(self) -> None:
        """Shutdown the benchmark handler and cleanup resources."""
        if not self._executor_shutdown:
            logger.info("Shutting down ThreadPoolExecutor")
            self._executor.shutdown(wait=True)
            self._executor_shutdown = True

    def __enter__(self) -> "EnhancedBenchmarkHandler":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Literal[False]:
        """Context manager exit - ensure cleanup."""
        self.shutdown()
        return False

    async def __aenter__(self) -> "EnhancedBenchmarkHandler":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Literal[False]:
        """Async context manager exit - ensure cleanup."""
        self.shutdown()
        return False

    def __del__(self) -> None:
        """Destructor - ensure executor is shutdown."""
        if hasattr(self, "_executor_shutdown") and not self._executor_shutdown:
            try:
                self.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down executor in destructor: {e}")


@dataclass
class EnhancedBenchmarkResult:
    """Enhanced benchmark result with detailed metrics."""

    model_id: str
    success: bool
    response: Optional[str]
    error_message: Optional[str]
    metrics: Optional["EnhancedBenchmarkMetrics"]
    timestamp: datetime

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)


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
    def from_benchmark_results(cls, results: List[BenchmarkResult]) -> "EnhancedBenchmarkMetrics":
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
        avg_completion_tokens = (
            sum(completion_tokens) / len(completion_tokens) if completion_tokens else 0
        )
        avg_total_tokens = sum(total_tokens) / len(total_tokens) if total_tokens else 0

        # Quality and throughput
        quality_scores = [r.quality_score for r in successful if r.quality_score is not None]
        quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        throughputs = [
            r.throughput_tokens_per_second for r in successful if r.throughput_tokens_per_second
        ]
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
            throughput_score=throughput_score,
        )


# MCP 도구들은 mcp_benchmark.py에서 관리됩니다.
