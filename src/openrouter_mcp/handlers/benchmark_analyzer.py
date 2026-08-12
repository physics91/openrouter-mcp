#!/usr/bin/env python3
"""
Benchmark model performance analysis utilities.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

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
    best_quality = max(successful_results, key=lambda item: item[1].quality_score)
    best_throughput = max(successful_results, key=lambda item: item[1].throughput)

    return {
        "speed": {
            "model_id": best_speed[0].model_id,
            "avg_response_time": best_speed[1].avg_response_time,
        },
        "cost": {
            "model_id": best_cost[0].model_id,
            "avg_cost": best_cost[1].avg_cost,
        },
        "quality": {
            "model_id": best_quality[0].model_id,
            "quality_score": best_quality[1].quality_score,
        },
        "throughput": {
            "model_id": best_throughput[0].model_id,
            "throughput": best_throughput[1].throughput,
        },
    }


def _calculate_metric_averages(
    successful_results: list[tuple[EnhancedBenchmarkResult, EnhancedBenchmarkMetrics]],
) -> dict[str, float]:
    """Calculate field-wise averages for successful benchmark results."""
    return {
        "response_time": sum(
            metrics.avg_response_time for _, metrics in successful_results
        )
        / len(successful_results),
        "cost": sum(metrics.avg_cost for _, metrics in successful_results)
        / len(successful_results),
        "quality_score": sum(metrics.quality_score for _, metrics in successful_results)
        / len(successful_results),
        "throughput": sum(metrics.throughput for _, metrics in successful_results)
        / len(successful_results),
    }


class ModelPerformanceAnalyzer:
    """Advanced model performance analyzer with ranking and comparison capabilities."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def rank_models(
        self, results: list[EnhancedBenchmarkResult]
    ) -> list[tuple[EnhancedBenchmarkResult, float]]:
        """Rank models by overall performance score."""
        return _rank_models_by(
            results,
            lambda result: (
                result.metrics.speed_score * 0.25
                + result.metrics.cost_score * 0.25
                + result.metrics.quality_score * 0.35
                + result.metrics.throughput_score * 0.15
            ),
        )

    def rank_models_with_weights(
        self, results: list[EnhancedBenchmarkResult], weights: dict[str, float]
    ) -> list[tuple[EnhancedBenchmarkResult, float]]:
        """Rank models using custom weights."""
        return _rank_models_by(
            results,
            lambda result: (
                result.metrics.speed_score * weights.get("speed", 0)
                + result.metrics.cost_score * weights.get("cost", 0)
                + result.metrics.quality_score * weights.get("quality", 0)
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
