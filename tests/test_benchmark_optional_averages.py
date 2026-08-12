from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.openrouter_mcp.handlers import benchmark

pytestmark = pytest.mark.unit


def test_calculate_optional_benchmark_averages_keeps_zero_and_skips_none():
    results = [
        SimpleNamespace(
            quality_score=0.0,
            throughput_tokens_per_second=None,
            prompt_tokens=10,
            completion_tokens=4,
        ),
        SimpleNamespace(
            quality_score=1.0,
            throughput_tokens_per_second=5.0,
            prompt_tokens=None,
            completion_tokens=0,
        ),
    ]

    assert benchmark._calculate_optional_benchmark_averages(results) == (
        0.5,
        5.0,
        10.0,
        2.0,
    )


def test_calculate_optional_benchmark_averages_returns_none_when_all_missing():
    result = SimpleNamespace(
        quality_score=None,
        throughput_tokens_per_second=None,
        prompt_tokens=None,
        completion_tokens=None,
    )

    assert benchmark._calculate_optional_benchmark_averages([result]) == (
        None,
        None,
        None,
        None,
    )


def test_calculate_optional_benchmark_averages_preserves_evaluation_order():
    events = []
    expected_error = RuntimeError("throughput failed")

    class Result:
        @property
        def quality_score(self):
            events.append("quality")
            return 0.5

        @property
        def throughput_tokens_per_second(self):
            events.append("throughput")
            raise expected_error

        @property
        def prompt_tokens(self):
            events.append("prompt")
            return 1

        @property
        def completion_tokens(self):
            events.append("completion")
            return 1

    with pytest.raises(RuntimeError) as exc_info:
        benchmark._calculate_optional_benchmark_averages([Result()])

    assert exc_info.value is expected_error
    assert events == ["quality", "quality", "throughput"]


def test_benchmark_metrics_delegates_optional_averages(monkeypatch):
    successful = SimpleNamespace(
        error=None,
        response_time_ms=100.0,
        tokens_used=20,
        cost=2.0,
    )
    failed = SimpleNamespace(
        error="failed",
        response_time_ms=999.0,
        tokens_used=999,
        cost=3.0,
    )
    optional_averages = Mock(return_value=(0.5, 4.0, 12.0, 8.0))
    monkeypatch.setattr(
        benchmark,
        "_calculate_optional_benchmark_averages",
        optional_averages,
    )

    metrics = benchmark.BenchmarkMetrics.from_results([successful, failed])

    optional_averages.assert_called_once()
    received_results = optional_averages.call_args.args[0]
    assert received_results == [successful]
    assert received_results[0] is successful
    assert metrics.avg_response_time_ms == 100.0
    assert metrics.avg_tokens_used == 20.0
    assert metrics.avg_cost == 2.0
    assert metrics.total_cost == 5.0
    assert metrics.success_rate == 0.5
    assert metrics.sample_count == 2
    assert metrics.avg_quality_score == 0.5
    assert metrics.avg_throughput == 4.0
    assert metrics.avg_prompt_tokens == 12.0
    assert metrics.avg_completion_tokens == 8.0
    assert metrics.cost_per_quality_point == 4.0
