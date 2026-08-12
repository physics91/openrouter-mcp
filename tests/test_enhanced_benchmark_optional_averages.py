from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.openrouter_mcp.handlers import benchmark

pytestmark = pytest.mark.unit


def test_calculate_enhanced_optional_averages_preserves_filter_semantics():
    results = [
        SimpleNamespace(
            prompt_tokens=0,
            completion_tokens=None,
            tokens_used=10,
            quality_score=0.0,
            throughput_tokens_per_second=0.0,
        ),
        SimpleNamespace(
            prompt_tokens=20,
            completion_tokens=-4,
            tokens_used=0,
            quality_score=None,
            throughput_tokens_per_second=-2.0,
        ),
    ]

    assert benchmark._calculate_enhanced_optional_averages(results) == (
        20.0,
        -4.0,
        10.0,
        0.0,
        -2.0,
    )


def test_calculate_enhanced_optional_averages_returns_zero_when_absent():
    result = SimpleNamespace(
        prompt_tokens=0,
        completion_tokens=None,
        tokens_used=0,
        quality_score=None,
        throughput_tokens_per_second=0,
    )

    assert benchmark._calculate_enhanced_optional_averages([result]) == (
        0,
        0,
        0,
        0,
        0,
    )


def test_calculate_enhanced_optional_averages_preserves_access_order():
    events = []
    expected_error = RuntimeError("completion failed")

    class Result:
        @property
        def prompt_tokens(self):
            events.append("prompt")
            return 1

        @property
        def completion_tokens(self):
            events.append("completion")
            raise expected_error

        @property
        def tokens_used(self):
            events.append("total")
            return 1

        @property
        def quality_score(self):
            events.append("quality")
            return 1.0

        @property
        def throughput_tokens_per_second(self):
            events.append("throughput")
            return 1.0

    with pytest.raises(RuntimeError) as exc_info:
        benchmark._calculate_enhanced_optional_averages([Result()])

    assert exc_info.value is expected_error
    assert events == ["prompt", "prompt", "completion"]


def test_enhanced_benchmark_metrics_delegates_optional_averages(monkeypatch):
    successful = SimpleNamespace(
        error=None,
        response_time_ms=30000.0,
        cost=0.0005,
    )
    failed = SimpleNamespace(
        error="failed",
        response_time_ms=99999.0,
        cost=9.0,
    )
    optional_averages = Mock(return_value=(12.0, 8.0, 20.0, 0.75, 50.0))
    monkeypatch.setattr(
        benchmark,
        "_calculate_enhanced_optional_averages",
        optional_averages,
    )

    metrics = benchmark.EnhancedBenchmarkMetrics.from_benchmark_results(
        [successful, failed]
    )

    optional_averages.assert_called_once()
    received_results = optional_averages.call_args.args[0]
    assert received_results == [successful]
    assert received_results[0] is successful
    assert metrics.avg_response_time == 30.0
    assert metrics.min_response_time == 30.0
    assert metrics.max_response_time == 30.0
    assert metrics.avg_cost == 0.0005
    assert metrics.min_cost == 0.0005
    assert metrics.max_cost == 0.0005
    assert metrics.avg_prompt_tokens == 12.0
    assert metrics.avg_completion_tokens == 8.0
    assert metrics.avg_total_tokens == 20.0
    assert metrics.quality_score == 0.75
    assert metrics.throughput == 50.0
    assert metrics.success_rate == 0.5
    assert metrics.speed_score == 0.5
    assert metrics.cost_score == 0.5
    assert metrics.throughput_score == 0.5
