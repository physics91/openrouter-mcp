import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.openrouter_mcp.handlers.free_chat import list_free_models


@pytest.fixture
def free_models():
    return [
        {
            "id": "google/gemma-3-27b:free",
            "name": "Gemma 3 27B",
            "context_length": 131072,
            "cost_tier": "free",
            "provider": "google",
            "capabilities": {"supports_vision": True},
        },
        {
            "id": "meta-llama/llama-4-scout:free",
            "name": "Llama 4 Scout",
            "context_length": 131072,
            "cost_tier": "free",
            "provider": "meta",
            "capabilities": {},
        },
    ]


class TestListFreeModels:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lists_free_models_with_scores(self, free_models):
        with patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_router = MagicMock()
            mock_router._cache.filter_models.return_value = free_models
            mock_router._score_model.side_effect = [0.85, 0.75]
            mock_router._is_available.return_value = True
            mock_get_router.return_value = mock_router

            result = await list_free_models()

            assert len(result["models"]) == 2
            assert result["total_count"] == 2
            assert result["models"][0]["id"] == "google/gemma-3-27b:free"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_shows_unavailable_models(self, free_models):
        with patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_router = MagicMock()
            mock_router._cache.filter_models.return_value = free_models
            mock_router._score_model.side_effect = [0.85, 0.75]
            mock_router._is_available.side_effect = [False, True]
            mock_get_router.return_value = mock_router

            result = await list_free_models()

            assert result["available_count"] == 1
            assert result["models"][0]["available"] is False
            assert result["models"][1]["available"] is True
