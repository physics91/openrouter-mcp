from unittest.mock import AsyncMock, patch

import pytest

from src.openrouter_mcp.handlers.free_chat import list_free_models


class TestListFreeModels:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lists_free_models_with_scores(self):
        with patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_router = AsyncMock()
            mock_router.list_models_with_status.return_value = [
                {
                    "id": "google/gemma-3-27b:free",
                    "name": "Gemma 3 27B",
                    "context_length": 131072,
                    "provider": "google",
                    "quality_score": 0.85,
                    "available": True,
                },
                {
                    "id": "meta-llama/llama-4-scout:free",
                    "name": "Llama 4 Scout",
                    "context_length": 131072,
                    "provider": "meta",
                    "quality_score": 0.75,
                    "available": True,
                },
            ]
            mock_get_router.return_value = mock_router

            result = await list_free_models()

            assert len(result["models"]) == 2
            assert result["total_count"] == 2
            assert result["models"][0]["id"] == "google/gemma-3-27b:free"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_shows_unavailable_models(self):
        with patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_router = AsyncMock()
            mock_router.list_models_with_status.return_value = [
                {
                    "id": "google/gemma-3-27b:free",
                    "name": "Gemma 3 27B",
                    "context_length": 131072,
                    "provider": "google",
                    "quality_score": 0.85,
                    "available": False,
                },
                {
                    "id": "meta-llama/llama-4-scout:free",
                    "name": "Llama 4 Scout",
                    "context_length": 131072,
                    "provider": "meta",
                    "quality_score": 0.75,
                    "available": True,
                },
            ]
            mock_get_router.return_value = mock_router

            result = await list_free_models()

            assert result["available_count"] == 1
            assert result["models"][0]["available"] is False
            assert result["models"][1]["available"] is True
