import pytest
from unittest.mock import MagicMock

from src.openrouter_mcp.free.router import FreeModelRouter


def _make_free_model(model_id, context_length=32768, provider="unknown"):
    return {
        "id": model_id,
        "name": model_id,
        "context_length": context_length,
        "cost_tier": "free",
        "provider": provider,
        "capabilities": {},
    }


@pytest.fixture
def free_models():
    return [
        _make_free_model("google/gemma-3-27b:free", 131072, "google"),
        _make_free_model("meta-llama/llama-4-scout:free", 131072, "meta"),
        _make_free_model("qwen/qwen-2.5:free", 32768, "qwen"),
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
    async def test_no_free_models_available(self):
        cache = MagicMock()
        cache.filter_models.return_value = []
        router = FreeModelRouter(cache)
        with pytest.raises(RuntimeError, match="사용 가능한 free 모델이 없습니다"):
            await router.select_model()
