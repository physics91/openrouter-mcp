import pytest
from unittest.mock import AsyncMock, MagicMock

from src.openrouter_mcp.free.router import FreeModelRouter


@pytest.fixture
def mock_model_cache():
    cache = MagicMock()
    cache.filter_models.return_value = []
    return cache


@pytest.fixture
def router(mock_model_cache):
    return FreeModelRouter(mock_model_cache)


@pytest.fixture
def free_model_google():
    return {
        "id": "google/gemma-3-27b-it:free",
        "name": "Gemma 3 27B",
        "context_length": 131072,
        "cost_tier": "free",
        "provider": "google",
        "capabilities": {
            "supports_vision": True,
            "supports_function_calling": False,
        },
    }


@pytest.fixture
def free_model_meta():
    return {
        "id": "meta-llama/llama-4-scout:free",
        "name": "Llama 4 Scout",
        "context_length": 32768,
        "cost_tier": "free",
        "provider": "meta",
        "capabilities": {
            "supports_vision": False,
            "supports_function_calling": False,
        },
    }


@pytest.fixture
def free_model_unknown():
    return {
        "id": "unknown-org/some-model:free",
        "name": "Some Model",
        "context_length": 8192,
        "cost_tier": "free",
        "provider": "unknown",
        "capabilities": {},
    }


class TestFreeModelRouterScoring:
    @pytest.mark.unit
    def test_score_google_model_higher_than_meta(self, router, free_model_google, free_model_meta):
        score_google = router._score_model(free_model_google)
        score_meta = router._score_model(free_model_meta)
        assert score_google > score_meta

    @pytest.mark.unit
    def test_score_meta_higher_than_unknown(self, router, free_model_meta, free_model_unknown):
        score_meta = router._score_model(free_model_meta)
        score_unknown = router._score_model(free_model_unknown)
        assert score_meta > score_unknown

    @pytest.mark.unit
    def test_score_range_is_zero_to_one(self, router, free_model_google):
        score = router._score_model(free_model_google)
        assert 0.0 <= score <= 1.0

    @pytest.mark.unit
    def test_score_vision_bonus(self, router, free_model_google):
        score_google = router._score_model(free_model_google)
        no_vision = {**free_model_google, "capabilities": {"supports_vision": False, "supports_function_calling": False}}
        score_no_vision = router._score_model(no_vision)
        assert score_google > score_no_vision

    @pytest.mark.unit
    def test_score_empty_capabilities(self, router, free_model_unknown):
        score = router._score_model(free_model_unknown)
        assert 0.0 <= score <= 1.0
