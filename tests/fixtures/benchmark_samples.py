"""Shared benchmark sample payload builders used by benchmark tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Type


def build_enhanced_metric_results(benchmark_result_cls: Type[Any]) -> List[Any]:
    """Return two BenchmarkResult-style objects used in enhanced metric assertions."""
    timestamp = datetime.now(timezone.utc)
    return [
        benchmark_result_cls(
            model_id="model1",
            prompt="test",
            response="response1",
            response_time_ms=1000,
            tokens_used=100,
            cost=0.005,
            timestamp=timestamp,
            prompt_tokens=40,
            completion_tokens=60,
            quality_score=0.8,
            throughput_tokens_per_second=100.0,
        ),
        benchmark_result_cls(
            model_id="model1",
            prompt="test",
            response="response2",
            response_time_ms=1500,
            tokens_used=150,
            cost=0.0075,
            timestamp=timestamp,
            prompt_tokens=50,
            completion_tokens=100,
            quality_score=0.9,
            throughput_tokens_per_second=100.0,
        ),
    ]


__all__ = ["build_enhanced_metric_results"]
