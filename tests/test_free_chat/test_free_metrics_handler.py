"""Tests for the get_free_model_metrics MCP tool handler."""

from unittest.mock import MagicMock, patch

import pytest

from src.openrouter_mcp.free.metrics import ModelMetrics
from src.openrouter_mcp.handlers.free_chat import get_free_model_metrics


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
