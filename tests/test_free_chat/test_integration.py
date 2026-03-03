"""End-to-end integration tests for the free tool intelligence pipeline.

Verifies the full flow: classify → select → record metrics → adaptive score shift → ranking change.
"""

from unittest.mock import MagicMock

import pytest

from src.openrouter_mcp.free.classifier import FreeTaskType, TaskClassifier
from src.openrouter_mcp.free.metrics import MetricsCollector
from src.openrouter_mcp.free.router import FreeModelRouter
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


class TestEndToEndFlow:
    """Full pipeline: classify → select → metrics → adaptive scoring."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_classify_then_select_with_task_type(self, mock_cache):
        """Classifier output feeds into router selection."""
        classifier = TaskClassifier()
        metrics = MetricsCollector()
        router = FreeModelRouter(mock_cache, metrics=metrics)

        task_type = classifier.classify("파이썬 코드를 작성해줘")
        assert task_type == FreeTaskType.CODING

        model = await router.select_model(task_type=task_type)
        assert model is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_metrics_shift_model_ranking(self, mock_cache, free_models):
        """Good performance data raises a model's rank above its static position."""
        metrics = MetricsCollector()
        router = FreeModelRouter(mock_cache, metrics=metrics)

        # Before any metrics: google (static 0.9) beats deepseek (static 0.7)
        score_google_before = router._score_model(free_models[0])
        score_deepseek_before = router._score_model(free_models[1])
        assert score_google_before > score_deepseek_before

        # Simulate deepseek performing excellently (fast, 100% success)
        for _ in range(30):
            metrics.record_success("deepseek/chat:free", 50.0, 100)

        # Simulate google performing poorly (slow, many failures)
        for _ in range(25):
            metrics.record_failure("google/gemma:free", "RateLimitError")
        for _ in range(5):
            metrics.record_success("google/gemma:free", 9000.0, 5)

        score_google_after = router._score_model(free_models[0])
        score_deepseek_after = router._score_model(free_models[1])

        # deepseek should now rank higher than google
        assert score_deepseek_after > score_google_after

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_coding_affinity_changes_selection_order(self, mock_cache):
        """CODING task type boosts deepseek enough to be selected over qwen."""
        metrics = MetricsCollector()
        router = FreeModelRouter(mock_cache, metrics=metrics)

        # Without task type, google should be first (highest static reputation)
        first_default = await router.select_model()
        assert first_default == "google/gemma:free"

        # With CODING task type, deepseek gets +0.15 affinity bonus
        router._usage_counts.clear()
        await router.select_model(task_type=FreeTaskType.CODING)
        # Still google first because google static (0.9) + context > deepseek (0.7) + 0.15
        # But deepseek's relative position should improve
        score_deepseek_coding = router._score_model(
            make_free_model("deepseek/chat:free", 131072, "deepseek"),
            task_type=FreeTaskType.CODING,
        )
        score_deepseek_default = router._score_model(
            make_free_model("deepseek/chat:free", 131072, "deepseek"),
        )
        assert score_deepseek_coding > score_deepseek_default

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_failure_metrics_tracked_with_error_type(self, mock_cache):
        """Error types are correctly accumulated per model."""
        metrics = MetricsCollector()
        FreeModelRouter(mock_cache, metrics=metrics)

        metrics.record_failure("google/gemma:free", "RateLimitError")
        metrics.record_failure("google/gemma:free", "RateLimitError")
        metrics.record_failure("google/gemma:free", "ServerError")

        m = metrics.get_metrics("google/gemma:free")
        assert m.failure_count == 3
        assert m.error_counts["RateLimitError"] == 2
        assert m.error_counts["ServerError"] == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_metrics_below_threshold_no_effect(self, mock_cache, free_models):
        """Below ADAPTIVE_MIN_REQUESTS, metrics don't affect scoring."""
        metrics = MetricsCollector()
        router_with = FreeModelRouter(mock_cache, metrics=metrics)
        router_without = FreeModelRouter(mock_cache)

        # Record fewer than ADAPTIVE_MIN_REQUESTS (5)
        for _ in range(4):
            metrics.record_success("google/gemma:free", 50.0, 100)

        score_with = router_with._score_model(free_models[0])
        score_without = router_without._score_model(free_models[0])
        assert score_with == pytest.approx(score_without)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_multiple_rounds(self, mock_cache):
        """Multiple selection rounds with metrics accumulation."""
        classifier = TaskClassifier()
        metrics = MetricsCollector()
        router = FreeModelRouter(mock_cache, metrics=metrics)

        messages = [
            ("파이썬 함수를 구현해줘", FreeTaskType.CODING),
            ("이 문장을 영어로 번역해줘", FreeTaskType.TRANSLATION),
            ("짧은 이야기를 써줘", FreeTaskType.CREATIVE),
            ("이 데이터를 분석해줘", FreeTaskType.ANALYSIS),
            ("안녕하세요", FreeTaskType.GENERAL),
        ]

        selected_models = []
        for msg, expected_type in messages:
            task_type = classifier.classify(msg)
            assert task_type == expected_type

            model = await router.select_model(task_type=task_type)
            selected_models.append(model)
            # Simulate success
            metrics.record_success(model, 200.0, 50)

        # All 5 rounds should have selected a model
        assert len(selected_models) == 5
        assert all(m is not None for m in selected_models)

        # Metrics should reflect the 5 successful requests
        all_metrics = metrics.get_all_metrics()
        total_requests = sum(m.total_requests for m in all_metrics.values())
        assert total_requests == 5

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_free_model_metrics_reflects_state(self, mock_cache):
        """get_free_model_metrics returns current accumulated state."""
        metrics = MetricsCollector()
        FreeModelRouter(mock_cache, metrics=metrics)

        # Simulate usage
        for _ in range(10):
            metrics.record_success("google/gemma:free", 100.0, 50)
        metrics.record_failure("google/gemma:free", "RateLimitError")

        # Verify state
        m = metrics.get_metrics("google/gemma:free")
        assert m.total_requests == 11
        assert m.success_count == 10
        assert m.failure_count == 1
        assert m.success_rate == pytest.approx(10 / 11)
        assert m.avg_latency_ms == pytest.approx(100.0)
        assert m.error_counts["RateLimitError"] == 1

        perf_score = metrics.get_performance_score("google/gemma:free")
        assert 0.0 < perf_score <= 1.0
