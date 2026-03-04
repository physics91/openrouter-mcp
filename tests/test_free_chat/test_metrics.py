"""Tests for free model performance metrics."""

import json
import os

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


class TestMetricsPersistence:
    """Tests for metrics save/load roundtrip and corruption recovery."""

    def test_save_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "metrics.json")
        collector = MetricsCollector(persistence_path=path)
        collector.record_success("model-a", latency_ms=100.0, tokens_used=10)
        collector.record_failure("model-a", error_type="timeout")
        collector.save()

        loaded = MetricsCollector(persistence_path=path)
        m = loaded.get_metrics("model-a")
        assert m is not None
        assert m.total_requests == 2
        assert m.success_count == 1
        assert m.failure_count == 1
        assert m.error_counts["timeout"] == 1

    def test_missing_file_starts_empty(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        collector = MetricsCollector(persistence_path=path)
        assert collector.get_all_metrics() == {}

    def test_corrupted_file_starts_empty(self, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("{invalid json!!!")
        collector = MetricsCollector(persistence_path=path)
        assert collector.get_all_metrics() == {}

    def test_schema_mismatch_list_root_starts_empty(self, tmp_path):
        """Valid JSON but root is a list instead of dict."""
        path = str(tmp_path / "list_root.json")
        with open(path, "w") as f:
            json.dump([{"bad": 1}], f)
        collector = MetricsCollector(persistence_path=path)
        assert collector.get_all_metrics() == {}

    def test_schema_mismatch_non_dict_values_skipped(self, tmp_path):
        """Root is dict but values are not dicts — non-dict entries are skipped."""
        path = str(tmp_path / "bad_values.json")
        with open(path, "w") as f:
            json.dump({"model-a": "not-a-dict", "model-b": {"total_requests": 5}}, f)
        collector = MetricsCollector(persistence_path=path)
        assert "model-a" not in collector.get_all_metrics()
        assert collector.get_metrics("model-b") is not None

    def test_auto_save_interval(self, tmp_path):
        path = str(tmp_path / "auto.json")
        collector = MetricsCollector(persistence_path=path)

        # Record fewer than METRICS_SAVE_INTERVAL (10) — should not save yet
        for i in range(9):
            collector.record_success("model-a", latency_ms=10.0, tokens_used=1)
        assert not os.path.exists(path)

        # 10th record triggers auto-save
        collector.record_success("model-a", latency_ms=10.0, tokens_used=1)
        assert os.path.exists(path)

    def test_no_persistence_path_skips_save(self):
        collector = MetricsCollector()
        collector.record_success("model-a", latency_ms=10.0, tokens_used=1)
        collector.save()  # should not raise

    def test_save_creates_directory(self, tmp_path):
        path = str(tmp_path / "subdir" / "metrics.json")
        collector = MetricsCollector(persistence_path=path)
        collector.record_success("model-a", latency_ms=10.0, tokens_used=1)
        collector.save()
        assert os.path.exists(path)

    def test_atomic_write_preserves_original_on_failure(self, tmp_path, monkeypatch):
        path = str(tmp_path / "metrics.json")
        collector = MetricsCollector(persistence_path=path)
        collector.record_success("model-a", latency_ms=10.0, tokens_used=1)
        collector.save()

        # Verify original data exists
        with open(path) as f:
            original = json.load(f)
        assert "model-a" in original

        # Simulate write failure after tmp file is created
        real_replace = os.replace

        def failing_replace(src, dst):
            os.unlink(src)  # clean up tmp so test doesn't leak
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", failing_replace)

        collector.record_success("model-b", latency_ms=20.0, tokens_used=2)
        collector.save()  # should fail internally

        monkeypatch.setattr(os, "replace", real_replace)

        # Original file must be intact
        with open(path) as f:
            after_failure = json.load(f)
        assert "model-a" in after_failure
        assert "model-b" not in after_failure


class TestModelMetricsSerialization:
    def test_to_dict(self):
        m = ModelMetrics(
            total_requests=5,
            success_count=3,
            failure_count=2,
            total_latency_ms=1500.0,
            total_tokens=300,
        )
        m.error_counts["timeout"] = 2
        d = m.to_dict()
        assert d["total_requests"] == 5
        assert d["error_counts"] == {"timeout": 2}

    def test_from_dict_roundtrip(self):
        original = ModelMetrics(
            total_requests=5,
            success_count=3,
            failure_count=2,
            total_latency_ms=1500.0,
            total_tokens=300,
        )
        original.error_counts["timeout"] = 2
        restored = ModelMetrics.from_dict(original.to_dict())
        assert restored.total_requests == original.total_requests
        assert restored.success_count == original.success_count
        assert restored.error_counts["timeout"] == 2
