"""Tests for free model performance metrics."""

import pytest

from src.openrouter_mcp.free.metrics import ModelMetrics


class TestModelMetrics:
    """Tests for ModelMetrics dataclass."""

    def test_defaults_are_zero(self) -> None:
        metrics = ModelMetrics()
        assert metrics.total_requests == 0
        assert metrics.success_count == 0
        assert metrics.failure_count == 0
        assert metrics.total_latency_ms == 0.0
        assert metrics.total_tokens == 0

    def test_success_rate_with_data(self) -> None:
        metrics = ModelMetrics(
            total_requests=10, success_count=8, failure_count=2
        )
        assert metrics.success_rate == 0.8

    def test_success_rate_zero_requests(self) -> None:
        metrics = ModelMetrics()
        assert metrics.success_rate == 0.0

    def test_avg_latency_ms(self) -> None:
        metrics = ModelMetrics(success_count=4, total_latency_ms=2000.0)
        assert metrics.avg_latency_ms == 500.0

    def test_avg_latency_ms_zero_success(self) -> None:
        metrics = ModelMetrics()
        assert metrics.avg_latency_ms == 0.0

    def test_tokens_per_second(self) -> None:
        metrics = ModelMetrics(total_tokens=100, total_latency_ms=2000.0)
        assert metrics.tokens_per_second == 50.0

    def test_tokens_per_second_zero_latency(self) -> None:
        metrics = ModelMetrics(total_tokens=100, total_latency_ms=0.0)
        assert metrics.tokens_per_second == 0.0

    def test_zero_tokens_success(self) -> None:
        metrics = ModelMetrics(
            success_count=1, total_latency_ms=100.0, total_tokens=0
        )
        assert metrics.tokens_per_second == 0.0
