import pytest
from unittest.mock import MagicMock

from src.openrouter_mcp.free.router import FreeModelRouter
from tests.test_free_chat.conftest import make_free_model


@pytest.fixture
def free_models():
    return [
        make_free_model("google/gemma-3-27b:free", 131072, "google"),
        make_free_model("meta-llama/llama-4-scout:free", 131072, "meta"),
        make_free_model("qwen/qwen-2.5:free", 32768, "qwen"),
    ]


@pytest.fixture
def mock_cache(free_models):
    cache = MagicMock()
    cache.filter_models.return_value = free_models
    return cache


@pytest.fixture
def router(mock_cache):
    return FreeModelRouter(mock_cache)


class TestSelectModel:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_selects_highest_quality_first(self, router):
        model_id = await router.select_model()
        assert model_id == "google/gemma-3-27b:free"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rotates_on_repeated_calls(self, router):
        first = await router.select_model()
        second = await router.select_model()
        assert first != second

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_skips_cooldown_models(self, router):
        router.report_rate_limit("google/gemma-3-27b:free")
        model_id = await router.select_model()
        assert model_id != "google/gemma-3-27b:free"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_raises_when_all_models_exhausted(self, router):
        router.report_rate_limit("google/gemma-3-27b:free")
        router.report_rate_limit("meta-llama/llama-4-scout:free")
        router.report_rate_limit("qwen/qwen-2.5:free")
        with pytest.raises(RuntimeError, match="사용 가능한 free 모델이 없습니다"):
            await router.select_model()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_preferred_models_override(self, router):
        model_id = await router.select_model(preferred_models=["qwen/qwen-2.5:free"])
        assert model_id == "qwen/qwen-2.5:free"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_preferred_model_skipped_if_cooldown(self, router):
        router.report_rate_limit("qwen/qwen-2.5:free")
        model_id = await router.select_model(preferred_models=["qwen/qwen-2.5:free"])
        assert model_id != "qwen/qwen-2.5:free"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_usage_counts_decay_prevents_stagnation(self, router):
        """After all models are used, decay resets relative counts so rotation continues."""
        # Use each model enough times that scores would all be 0.0 without decay
        selected = set()
        for _ in range(20):
            selected.add(await router.select_model())
        # All 3 models should have been used (rotation works)
        assert len(selected) == 3
        # After decay, rotation still works (doesn't stagnate)
        next_batch = set()
        for _ in range(6):
            next_batch.add(await router.select_model())
        assert len(next_batch) >= 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_preferred_paid_model_ignored(self, router):
        """Preferred model that is not in the free list should be ignored."""
        model_id = await router.select_model(preferred_models=["openai/gpt-4"])
        assert model_id != "openai/gpt-4"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_free_models_available(self):
        cache = MagicMock()
        cache.filter_models.return_value = []
        router = FreeModelRouter(cache)
        with pytest.raises(RuntimeError, match="사용 가능한 free 모델이 없습니다"):
            await router.select_model()
