"""Tests for the get_free_model_metrics MCP tool handler."""

from unittest.mock import MagicMock, call, patch

import pytest

from src.openrouter_mcp.free.metrics import MetricsCollector, ModelMetrics
from src.openrouter_mcp.handlers import free_chat as free_chat_module
from src.openrouter_mcp.handlers.free_chat import (
    _serialize_free_model_metrics,
    get_free_model_metrics,
)


class TestSerializeFreeModelMetrics:
    @pytest.mark.unit
    def test_serializes_schema_rounding_and_error_copy(self):
        collector = MagicMock(spec=MetricsCollector)
        collector.get_performance_score.return_value = 0.8549
        model_metrics = ModelMetrics(
            total_requests=10,
            success_count=9,
            failure_count=1,
            total_latency_ms=4500.0,
            total_tokens=900,
            error_counts={"RateLimitError": 1},
        )

        result = _serialize_free_model_metrics(
            collector,
            "google/gemma:free",
            model_metrics,
        )

        assert list(result) == [
            "total_requests",
            "success_count",
            "failure_count",
            "success_rate",
            "avg_latency_ms",
            "tokens_per_second",
            "performance_score",
            "error_counts",
        ]
        assert result == {
            "total_requests": 10,
            "success_count": 9,
            "failure_count": 1,
            "success_rate": 0.9,
            "avg_latency_ms": 500.0,
            "tokens_per_second": 200.0,
            "performance_score": 0.855,
            "error_counts": {"RateLimitError": 1},
        }
        assert result["error_counts"] is not model_metrics.error_counts
        collector.get_performance_score.assert_called_once_with("google/gemma:free")

    @pytest.mark.unit
    def test_serializes_zero_metrics(self):
        collector = MagicMock(spec=MetricsCollector)
        collector.get_performance_score.return_value = 0.0

        result = _serialize_free_model_metrics(
            collector,
            "google/gemma:free",
            ModelMetrics(),
        )

        assert result == {
            "total_requests": 0,
            "success_count": 0,
            "failure_count": 0,
            "success_rate": 0.0,
            "avg_latency_ms": 0.0,
            "tokens_per_second": 0.0,
            "performance_score": 0.0,
            "error_counts": {},
        }


class TestGetFreeModelMetrics:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_empty_metrics(self):
        with patch(
            "src.openrouter_mcp.handlers.free_chat._get_metrics"
        ) as mock_get_metrics:
            mock_collector = MagicMock()
            mock_collector.get_all_metrics.return_value = {}
            mock_get_metrics.return_value = mock_collector

            result = await get_free_model_metrics()
            assert result["models"] == {}
            assert result["total_models_tracked"] == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_metrics_with_data(self):
        with patch(
            "src.openrouter_mcp.handlers.free_chat._get_metrics"
        ) as mock_get_metrics:
            mock_collector = MagicMock()
            mock_collector.get_all_metrics.return_value = {
                "google/gemma:free": ModelMetrics(
                    total_requests=10,
                    success_count=9,
                    failure_count=1,
                    total_latency_ms=4500.0,
                    total_tokens=900,
                ),
            }
            mock_collector.get_performance_score.return_value = 0.85
            mock_get_metrics.return_value = mock_collector

            result = await get_free_model_metrics()
            assert result["total_models_tracked"] == 1
            model_data = result["models"]["google/gemma:free"]
            assert model_data["total_requests"] == 10
            assert model_data["success_rate"] == pytest.approx(0.9)
            assert model_data["performance_score"] == 0.85

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_includes_quota_status(self):
        with patch(
            "src.openrouter_mcp.handlers.free_chat._get_metrics"
        ) as mock_get_metrics:
            mock_collector = MagicMock()
            mock_collector.get_all_metrics.return_value = {}
            mock_get_metrics.return_value = mock_collector

            result = await get_free_model_metrics()
            assert "quota" in result
            quota = result["quota"]
            assert "daily_used" in quota
            assert "daily_limit" in quota
            assert "daily_remaining" in quota
            assert "minute_used" in quota
            assert "minute_limit" in quota
            assert "minute_remaining" in quota

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_serializes_models_in_collector_order_before_reading_quota(self):
        collector = MagicMock(spec=MetricsCollector)
        first_metrics = ModelMetrics(total_requests=2)
        second_metrics = ModelMetrics(total_requests=1)
        collector.get_all_metrics.return_value = {
            "model-b": first_metrics,
            "model-a": second_metrics,
        }
        first_payload = {"model": "b"}
        second_payload = {"model": "a"}
        quota_status = {"daily_remaining": 5}
        quota = MagicMock()
        quota.get_quota_status.return_value = quota_status

        with (
            patch.object(free_chat_module, "_get_metrics", return_value=collector),
            patch.object(
                free_chat_module,
                "_serialize_free_model_metrics",
                side_effect=[first_payload, second_payload],
            ) as serialize,
            patch.object(free_chat_module, "_get_quota", return_value=quota),
        ):
            result = await get_free_model_metrics()

        assert result == {
            "models": {
                "model-b": first_payload,
                "model-a": second_payload,
            },
            "total_models_tracked": 2,
            "quota": quota_status,
        }
        assert serialize.call_args_list == [
            call(collector, "model-b", first_metrics),
            call(collector, "model-a", second_metrics),
        ]
        quota.get_quota_status.assert_called_once_with()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_serialization_failure_prevents_quota_lookup(self):
        collector = MagicMock(spec=MetricsCollector)
        collector.get_all_metrics.return_value = {
            "google/gemma:free": ModelMetrics(),
        }

        with (
            patch.object(free_chat_module, "_get_metrics", return_value=collector),
            patch.object(
                free_chat_module,
                "_serialize_free_model_metrics",
                side_effect=RuntimeError("serialization failed"),
            ),
            patch.object(free_chat_module, "_get_quota") as get_quota,
            pytest.raises(RuntimeError, match="serialization failed"),
        ):
            await get_free_model_metrics()

        get_quota.assert_not_called()
