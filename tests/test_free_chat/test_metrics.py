"""Tests for free model performance metrics."""

import pytest

from src.openrouter_mcp.free.metrics import MetricsCollector, ModelMetrics


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
        metrics = ModelMetrics(total_requests=10, success_count=8, failure_count=2)
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
        metrics = ModelMetrics(success_count=1, total_latency_ms=100.0, total_tokens=0)
        assert metrics.tokens_per_second == 0.0


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    @pytest.fixture
    def collector(self) -> MetricsCollector:
        return MetricsCollector()

    def test_record_success(self, collector: MetricsCollector) -> None:
        collector.record_success("model-a", latency_ms=200.0, tokens_used=50)
        m = collector.get_metrics("model-a")
        assert m is not None
        assert m.total_requests == 1
        assert m.success_count == 1
        assert m.failure_count == 0
        assert m.total_latency_ms == 200.0
        assert m.total_tokens == 50

    def test_record_failure(self, collector: MetricsCollector) -> None:
        collector.record_failure("model-b", error_type="timeout")
        m = collector.get_metrics("model-b")
        assert m is not None
        assert m.total_requests == 1
        assert m.success_count == 0
        assert m.failure_count == 1
        assert m.error_counts["timeout"] == 1

    def test_record_failure_error_type_counts(
        self, collector: MetricsCollector
    ) -> None:
        collector.record_failure("model-b", error_type="timeout")
        collector.record_failure("model-b", error_type="timeout")
        collector.record_failure("model-b", error_type="rate_limit")

        m = collector.get_metrics("model-b")
        assert m is not None
        assert m.failure_count == 3
        assert m.error_counts["timeout"] == 2
        assert m.error_counts["rate_limit"] == 1

    def test_get_metrics_unknown_model(self, collector: MetricsCollector) -> None:
        assert collector.get_metrics("nonexistent") is None

    def test_get_all_metrics_empty(self, collector: MetricsCollector) -> None:
        result = collector.get_all_metrics()
        assert result == {}

    def test_get_all_metrics(self, collector: MetricsCollector) -> None:
        collector.record_success("model-a", latency_ms=100.0, tokens_used=10)
        collector.record_failure("model-b", error_type="rate_limit")
        result = collector.get_all_metrics()
        assert "model-a" in result
        assert "model-b" in result
        # Verify it returns a copy
        result["model-c"] = ModelMetrics()
        assert "model-c" not in collector.get_all_metrics()

    def test_multiple_records_accumulate(self, collector: MetricsCollector) -> None:
        collector.record_success("model-a", latency_ms=100.0, tokens_used=20)
        collector.record_success("model-a", latency_ms=300.0, tokens_used=30)
        collector.record_failure("model-a", error_type="error")
        m = collector.get_metrics("model-a")
        assert m is not None
        assert m.total_requests == 3
        assert m.success_count == 2
        assert m.failure_count == 1
        assert m.total_latency_ms == 400.0
        assert m.total_tokens == 50

    def test_performance_score_no_data(self, collector: MetricsCollector) -> None:
        assert collector.get_performance_score("unknown") == 0.0

    def test_performance_score_perfect(self, collector: MetricsCollector) -> None:
        """Perfect model: 100% success, 0ms latency, max throughput."""
        # success_rate = 1.0, latency_score = 1.0, throughput_score = 1.0
        # score = 0.5*1.0 + 0.3*1.0 + 0.2*1.0 = 1.0
        # Need: total_requests=1, success_count=1, low latency, high tokens
        # latency_score = 1 - min(avg_latency / 10000, 1) = 1 - 0.001 = 0.999
        # throughput = tokens / (latency/1000) = 500 / (10/1000) = 50000
        # throughput_score = min(50000/50, 1) = 1.0
        collector.record_success("perfect", latency_ms=10.0, tokens_used=500)
        score = collector.get_performance_score("perfect")
        # success_rate = 1.0 -> 0.5 * 1.0 = 0.5
        # avg_latency = 10.0 -> latency_score = 1 - 10/10000 = 0.999
        #   -> 0.3 * 0.999 = 0.2997
        # tokens_per_second = 500 / 0.01 = 50000 -> score = min(50000/50, 1) = 1.0
        #   -> 0.2 * 1.0 = 0.2
        # total = 0.5 + 0.2997 + 0.2 = 0.9997
        assert score == pytest.approx(0.9997, abs=1e-4)

    def test_performance_score_range(self, collector: MetricsCollector) -> None:
        """Score is always between 0.0 and 1.0."""
        collector.record_success("model-x", latency_ms=5000.0, tokens_used=10)
        collector.record_failure("model-x", error_type="error")
        score = collector.get_performance_score("model-x")
        assert 0.0 <= score <= 1.0
