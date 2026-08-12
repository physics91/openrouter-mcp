from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.openrouter_mcp.handlers import benchmark_analyzer as analyzer_module
from src.openrouter_mcp.handlers.benchmark_analyzer import (
    ModelPerformanceAnalyzer,
    _build_best_performers,
)

pytestmark = pytest.mark.unit


def _result_pair(
    model_id,
    *,
    response_time,
    cost,
    quality,
    throughput,
):
    metrics = SimpleNamespace(
        avg_response_time=response_time,
        avg_cost=cost,
        quality_score=quality,
        throughput=throughput,
    )
    result = SimpleNamespace(model_id=model_id, success=True, metrics=metrics)
    return result, metrics


def test_build_best_performers_preserves_category_policies_and_schema():
    fastest = _result_pair(
        "fastest",
        response_time=1,
        cost=5,
        quality=0.4,
        throughput=10,
    )
    cheapest = _result_pair(
        "cheapest",
        response_time=2,
        cost=1,
        quality=0.5,
        throughput=20,
    )
    highest_quality = _result_pair(
        "highest-quality",
        response_time=3,
        cost=3,
        quality=0.9,
        throughput=30,
    )
    highest_throughput = _result_pair(
        "highest-throughput",
        response_time=4,
        cost=4,
        quality=0.6,
        throughput=100,
    )

    best = _build_best_performers(
        [fastest, cheapest, highest_quality, highest_throughput]
    )

    assert list(best) == ["speed", "cost", "quality", "throughput"]
    assert best == {
        "speed": {
            "model_id": "fastest",
            "avg_response_time": 1,
        },
        "cost": {
            "model_id": "cheapest",
            "avg_cost": 1,
        },
        "quality": {
            "model_id": "highest-quality",
            "quality_score": 0.9,
        },
        "throughput": {
            "model_id": "highest-throughput",
            "throughput": 100,
        },
    }


def test_build_best_performers_keeps_first_result_for_all_ties():
    first = _result_pair(
        "first",
        response_time=1,
        cost=2,
        quality=3,
        throughput=4,
    )
    second = _result_pair(
        "second",
        response_time=1,
        cost=2,
        quality=3,
        throughput=4,
    )
    successful_results = [first, second]

    best = _build_best_performers(successful_results)

    assert [entry["model_id"] for entry in best.values()] == ["first"] * 4
    assert successful_results[0] is first
    assert successful_results[1] is second
    assert successful_results == [first, second]


def test_compare_models_delegates_successes_and_preserves_averages():
    first, first_metrics = _result_pair(
        "first",
        response_time=1,
        cost=2,
        quality=3,
        throughput=4,
    )
    failed = SimpleNamespace(success=False, metrics=SimpleNamespace())
    missing_metrics = SimpleNamespace(success=True, metrics=None)
    second, second_metrics = _result_pair(
        "second",
        response_time=3,
        cost=4,
        quality=5,
        throughput=6,
    )
    best_performers = {"sentinel": object()}

    with patch.object(
        analyzer_module,
        "_build_best_performers",
        return_value=best_performers,
    ) as build_best:
        comparison = ModelPerformanceAnalyzer().compare_models(
            [first, failed, missing_metrics, second]
        )

    assert comparison == {
        "total_models": 4,
        "successful_models": 2,
        "best_performers": best_performers,
        "averages": {
            "response_time": 2,
            "cost": 3,
            "quality_score": 4,
            "throughput": 5,
        },
    }
    assert comparison["best_performers"] is best_performers
    successful_results = build_best.call_args.args[0]
    assert successful_results[0][0] is first
    assert successful_results[0][1] is first_metrics
    assert successful_results[1][0] is second
    assert successful_results[1][1] is second_metrics


def test_compare_models_skips_best_performers_without_successes():
    failed_results = [
        SimpleNamespace(success=False, metrics=SimpleNamespace()),
        SimpleNamespace(success=True, metrics=None),
    ]

    with patch.object(analyzer_module, "_build_best_performers") as build_best:
        assert ModelPerformanceAnalyzer().compare_models([]) == {}
        assert ModelPerformanceAnalyzer().compare_models(failed_results) == {
            "error": "No successful results to compare",
            "total_models": 2,
            "successful_models": 0,
        }

    build_best.assert_not_called()
