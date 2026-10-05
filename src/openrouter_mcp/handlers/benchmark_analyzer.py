#!/usr/bin/env python3
"""
Benchmark model performance analysis utilities.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .benchmark_metrics import validate_performance_weights

if TYPE_CHECKING:
    from .benchmark import EnhancedBenchmarkMetrics, EnhancedBenchmarkResult


def _rank_models_by(
    results: list[EnhancedBenchmarkResult],
    score_result: Callable[["EnhancedBenchmarkResult"], float],
) -> list[tuple[EnhancedBenchmarkResult, float]]:
    """Rank results with shared failure handling and stable score ordering."""
    if not results:
        return []

    scored_results: list[tuple[EnhancedBenchmarkResult, float]] = []
    for result in results:
        if not result.success or result.metrics is None:
            scored_results.append((result, 0.0))
            continue

        scored_results.append((result, score_result(result)))

    return sorted(scored_results, key=lambda item: item[1], reverse=True)


def _build_best_performers(
    successful_results: list[tuple[EnhancedBenchmarkResult, EnhancedBenchmarkMetrics]],
) -> dict[str, dict[str, Any]]:
    """Build the category winner summary for successful benchmark results."""
    best_speed = min(successful_results, key=lambda item: item[1].avg_response_time)
    best_cost = min(successful_results, key=lambda item: item[1].avg_cost)
    best_throughput = max(successful_results, key=lambda item: item[1].throughput)

    best = {
        "speed": {
            "model_id": best_speed[0].model_id,
            "avg_response_time": best_speed[1].avg_response_time,
        },
        "cost": {
            "model_id": best_cost[0].model_id,
            "avg_cost": best_cost[1].avg_cost,
        },
    }
    evaluated = [
        item for item in successful_results if item[1].quality_score is not None
    ]
    if evaluated:
        best_quality = max(evaluated, key=lambda item: item[1].quality_score)
        best["quality"] = {
            "model_id": best_quality[0].model_id,
            "quality_score": best_quality[1].quality_score,
        }
    best["throughput"] = {
        "model_id": best_throughput[0].model_id,
        "throughput": best_throughput[1].throughput,
    }
    return best


def _calculate_metric_averages(
    successful_results: list[tuple[EnhancedBenchmarkResult, EnhancedBenchmarkMetrics]],
) -> dict[str, float | None]:
    """Calculate field-wise averages for successful benchmark results."""
    averages = {
        "response_time": sum(
            metrics.avg_response_time for _, metrics in successful_results
        )
        / len(successful_results),
        "cost": sum(metrics.avg_cost for _, metrics in successful_results)
        / len(successful_results),
    }
    quality_scores = [
        score
        for _, metrics in successful_results
        if (score := metrics.quality_score) is not None
    ]
    averages["quality_score"] = (
        sum(quality_scores) / len(quality_scores) if quality_scores else None
    )
    averages["throughput"] = sum(
        metrics.throughput for _, metrics in successful_results
    ) / len(successful_results)
    return averages


class ModelPerformanceAnalyzer:
    """Advanced model performance analyzer with ranking and comparison capabilities."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def rank_models(
        self, results: list[EnhancedBenchmarkResult]
    ) -> list[tuple[EnhancedBenchmarkResult, float]]:
        """Rank models by overall performance score."""
        weights = {"speed": 0.25, "cost": 0.25, "quality": 0.35, "throughput": 0.15}
        if any(
            result.metrics.quality_score is None
            for result in results
            if result.success and result.metrics
        ):
            weights.pop("quality")
            total = sum(weights.values())
            weights = {name: weight / total for name, weight in weights.items()}
        return self.rank_models_with_weights(results, weights)

    def rank_models_with_weights(
        self, results: list[EnhancedBenchmarkResult], weights: dict[str, float]
    ) -> list[tuple[EnhancedBenchmarkResult, float]]:
        """Rank models using custom weights."""
        validate_performance_weights(weights)
        if weights.get("quality", 0) > 0 and any(
            result.metrics.quality_score is None
            for result in results
            if result.success and result.metrics
        ):
            raise ValueError(
                "Quality ranking requires evaluated quality scores for every model"
            )
        return _rank_models_by(
            results,
            lambda result: (
                result.metrics.speed_score * weights.get("speed", 0)
                + result.metrics.cost_score * weights.get("cost", 0)
                + (result.metrics.quality_score or 0.0) * weights.get("quality", 0)
                + result.metrics.throughput_score * weights.get("throughput", 0)
            ),
        )

    def compare_models(self, results: list[EnhancedBenchmarkResult]) -> dict[str, Any]:
        """Provide detailed comparison analysis between models."""
        if not results:
            return {}

        successful_results: list[
            tuple[EnhancedBenchmarkResult, EnhancedBenchmarkMetrics]
        ] = [
            (result, result.metrics)
            for result in results
            if result.success and result.metrics is not None
        ]

        if not successful_results:
            return {
                "error": "No successful results to compare",
                "total_models": len(results),
                "successful_models": 0,
            }

        best_performers = _build_best_performers(successful_results)
        averages = _calculate_metric_averages(successful_results)

        return {
            "total_models": len(results),
            "successful_models": len(successful_results),
            "best_performers": best_performers,
            "averages": averages,
        }
