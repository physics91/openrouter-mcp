"""Tests for adaptive scoring and task-type affinity in FreeModelRouter."""

import pytest
from unittest.mock import MagicMock

from src.openrouter_mcp.free.router import FreeModelRouter
from src.openrouter_mcp.free.metrics import MetricsCollector
from src.openrouter_mcp.free.classifier import TaskType
from tests.test_free_chat.conftest import make_free_model


@pytest.fixture
def free_models():
    return [
        make_free_model("google/gemma:free", 131072, "google"),
        make_free_model("deepseek/chat:free", 131072, "deepseek"),
        make_free_model("qwen/model:free", 32768, "qwen"),
    ]


@pytest.fixture
def mock_cache(free_models):
    cache = MagicMock()
    cache.filter_models.return_value = free_models
    return cache


class TestAdaptiveScoring:
    @pytest.mark.unit
    def test_no_metrics_uses_static_reputation(self, mock_cache, free_models):
        router = FreeModelRouter(mock_cache)
        score = router._score_model(free_models[0])
        assert 0.0 < score <= 1.0

    @pytest.mark.unit
    def test_metrics_below_min_requests_uses_static(self, mock_cache, free_models):
        metrics = MetricsCollector()
        metrics.record_success("google/gemma:free", 100.0, 50)
        router_no_metrics = FreeModelRouter(mock_cache)
        router_with_metrics = FreeModelRouter(mock_cache, metrics=metrics)
        score_static = router_no_metrics._score_model(free_models[0])
        score_adaptive = router_with_metrics._score_model(free_models[0])
        assert score_static == pytest.approx(score_adaptive)

    @pytest.mark.unit
    def test_metrics_above_min_blends_score(self, mock_cache, free_models):
        metrics = MetricsCollector()
        for _ in range(20):
            metrics.record_success("google/gemma:free", 100.0, 50)
        router_no_metrics = FreeModelRouter(mock_cache)
        router_with_metrics = FreeModelRouter(mock_cache, metrics=metrics)
        score_static = router_no_metrics._score_model(free_models[0])
        score_adaptive = router_with_metrics._score_model(free_models[0])
        assert score_adaptive > score_static
        assert abs(score_adaptive - score_static) > 0.01

    @pytest.mark.unit
    def test_poor_performance_lowers_score(self, mock_cache, free_models):
        metrics = MetricsCollector()
        for _ in range(20):
            metrics.record_failure("google/gemma:free", "error")
        for _ in range(5):
            metrics.record_success("google/gemma:free", 8000.0, 5)
        router = FreeModelRouter(mock_cache, metrics=metrics)
        router_static = FreeModelRouter(mock_cache)
        score_adaptive = router._score_model(free_models[0])
        score_static = router_static._score_model(free_models[0])
        assert score_adaptive < score_static


class TestTaskTypeSelection:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_coding_task_accepts_task_type(self, mock_cache):
        router = FreeModelRouter(mock_cache)
        model = await router.select_model(task_type=TaskType.CODING)
        assert model is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_general_task_no_affinity_change(self, mock_cache):
        router = FreeModelRouter(mock_cache)
        model_default = await router.select_model()
        router._usage_counts.clear()
        model_general = await router.select_model(task_type=TaskType.GENERAL)
        assert model_default == model_general

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_none_task_type_is_default(self, mock_cache):
        router = FreeModelRouter(mock_cache)
        model = await router.select_model(task_type=None)
        assert model is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_coding_affinity_boosts_deepseek(self, mock_cache):
        router = FreeModelRouter(mock_cache)
        score_default = router._score_model(
            make_free_model("deepseek/chat:free", 131072, "deepseek")
        )
        score_coding = router._score_model(
            make_free_model("deepseek/chat:free", 131072, "deepseek"),
            task_type=TaskType.CODING,
        )
        assert score_coding > score_default
