"""Tests for OpenRouter native fallback (models array) feature."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.openrouter_mcp.client.openrouter import (
    InvalidRequestError,
    RateLimitError,
)
from src.openrouter_mcp.handlers.free_chat import FreeChatRequest, free_chat


def _make_response(model_id: str, content: str = "Hello!") -> dict:
    """Build a minimal chat completion response with the ``model`` field."""
    return {
        "id": "gen-native-001",
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }


@pytest.fixture(autouse=True)
def _enable_native_fallback():
    """Ensure native fallback is enabled for all tests in this module."""
    import src.openrouter_mcp.handlers.free_chat as handler_module

    handler_module._native_fallback_disabled = False
    yield
    handler_module._native_fallback_disabled = False


class TestNativeFallbackModelsArray:
    """Verify that non-streaming requests pass the ``models`` array."""

    @pytest.mark.asyncio
    async def test_models_array_passed_non_streaming(self):
        """chat_completion should receive ``models`` kwarg with top-N IDs."""
        response = _make_response("google/gemma:free")

        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = response
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_models.return_value = [
                "google/gemma:free",
                "meta/llama:free",
            ]
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hi", stream=False)
            result = await free_chat(request)

            # models array should be passed
            call_kwargs = mock_client.chat_completion.call_args[1]
            assert call_kwargs["models"] == [
                "google/gemma:free",
                "meta/llama:free",
            ]
            assert result["model_used"] == "google/gemma:free"

    @pytest.mark.asyncio
    async def test_streaming_does_not_use_models_array(self):
        """stream=True should bypass native fallback entirely."""

        async def _fake_stream(**kwargs):
            for c in [
                {"choices": [{"delta": {"content": "hi"}}]},
                {"usage": {"total_tokens": 2}},
            ]:
                yield c

        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.stream_chat_completion = _fake_stream
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.return_value = "google/gemma:free"
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hi", stream=True)
            result = await free_chat(request)

            # select_models should NOT be called (native fallback skipped)
            mock_router.select_models.assert_not_called()
            assert result["streamed"] is True


class TestNativeFallbackActualModel:
    """Verify actual model extraction from response."""

    @pytest.mark.asyncio
    async def test_actual_model_from_response(self):
        """When OpenRouter routes to a different model, model_used reflects that."""
        # Primary is model-a but OpenRouter routed to model-b
        response = _make_response("meta/llama:free", content="Fallback response")

        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = response
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_models.return_value = [
                "google/gemma:free",
                "meta/llama:free",
            ]
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hi")
            result = await free_chat(request)

            assert result["model_used"] == "meta/llama:free"

    @pytest.mark.asyncio
    async def test_missing_model_field_uses_primary(self):
        """When response lacks ``model`` field, primary model is used."""
        response = {
            "id": "gen-001",
            "choices": [
                {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
            ],
            "usage": {"total_tokens": 3},
        }

        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = response
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_models.return_value = ["google/gemma:free"]
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hi")
            result = await free_chat(request)

            assert result["model_used"] == "google/gemma:free"


class TestNativeFallbackDisablement:
    """Verify auto-disable when API returns 400 for ``models`` parameter."""

    @pytest.mark.asyncio
    async def test_models_unsupported_400_disables_native_fallback(self):
        """400 with 'models' in error message disables native fallback."""
        import src.openrouter_mcp.handlers.free_chat as handler_module

        success_response = _make_response("google/gemma:free")

        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            # First call (native fallback): 400 with "models" error
            # Second call (local retry): success
            mock_client.chat_completion.side_effect = [
                InvalidRequestError("unknown parameter 'models'"),
                success_response,
            ]
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_models.return_value = [
                "google/gemma:free",
                "meta/llama:free",
            ]
            mock_router.select_model.return_value = "google/gemma:free"
            mock_get_router.return_value = mock_router

            assert handler_module._native_fallback_disabled is False

            request = FreeChatRequest(message="Hi")
            result = await free_chat(request)

            # Flag should be set
            assert handler_module._native_fallback_disabled is True
            # Should have fallen through to local retry
            assert result["model_used"] == "google/gemma:free"

    @pytest.mark.asyncio
    async def test_models_array_limit_400_disables_native_fallback(self):
        """400 with 'models array must have N items' disables native fallback."""
        import src.openrouter_mcp.handlers.free_chat as handler_module

        success_response = _make_response("google/gemma:free")

        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = [
                InvalidRequestError("'models' array must have 3 items or fewer."),
                success_response,
            ]
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_models.return_value = [
                "google/gemma:free",
                "meta/llama:free",
            ]
            mock_router.select_model.return_value = "google/gemma:free"
            mock_get_router.return_value = mock_router

            assert handler_module._native_fallback_disabled is False

            request = FreeChatRequest(message="Hi")
            result = await free_chat(request)

            assert handler_module._native_fallback_disabled is True
            assert result["model_used"] == "google/gemma:free"

    @pytest.mark.asyncio
    async def test_non_models_400_still_raises(self):
        """400 without 'models' in message should propagate normally."""
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = InvalidRequestError(
                "invalid temperature value"
            )
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_models.return_value = ["google/gemma:free"]
            mock_get_router.return_value = mock_router

            import src.openrouter_mcp.handlers.free_chat as handler_module

            request = FreeChatRequest(message="Hi")
            with pytest.raises(InvalidRequestError, match="invalid temperature"):
                await free_chat(request)

            # Flag must remain False
            assert handler_module._native_fallback_disabled is False

    @pytest.mark.asyncio
    async def test_rate_limit_falls_through_to_local_retry(self):
        """RateLimitError in native fallback falls through to local retry."""
        success_response = _make_response("meta/llama:free")

        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = [
                RateLimitError("rate limited"),
                success_response,
            ]
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_models.return_value = [
                "google/gemma:free",
                "meta/llama:free",
            ]
            mock_router.select_model.return_value = "meta/llama:free"
            mock_router.report_rate_limit = MagicMock()
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hi")
            result = await free_chat(request)

            # Native fallback reported rate limit for primary model
            mock_router.report_rate_limit.assert_any_call(
                "google/gemma:free", cooldown_seconds=60.0
            )
            # Local retry succeeded
            assert result["model_used"] == "meta/llama:free"


    @pytest.mark.asyncio
    async def test_cache_expiry_resets_disabled_flag(self):
        """When cache expires, the disabled flag is reset for retry."""
        import src.openrouter_mcp.handlers.free_chat as handler_module

        handler_module._native_fallback_disabled = True
        response = _make_response("google/gemma:free")

        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = response
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_models.return_value = ["google/gemma:free"]
            # is_cache_expired is sync — use MagicMock to avoid coroutine
            mock_router.is_cache_expired = MagicMock(return_value=True)
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hi")
            result = await free_chat(request)

            # Flag should have been reset and native fallback used
            assert handler_module._native_fallback_disabled is False
            mock_router.select_models.assert_called_once()
            assert result["model_used"] == "google/gemma:free"


class TestSelectModels:
    """Tests for FreeModelRouter.select_models()."""

    @pytest.mark.asyncio
    async def test_returns_top_n_models(self, mock_cache, free_models):
        from src.openrouter_mcp.free.router import FreeModelRouter

        mock_cache.filter_models.return_value = free_models
        router = FreeModelRouter(mock_cache)

        result = await router.select_models(count=2)

        assert len(result) == 2
        assert all(isinstance(mid, str) for mid in result)

    @pytest.mark.asyncio
    async def test_preferred_models_prioritized(self, mock_cache, free_models):
        from src.openrouter_mcp.free.router import FreeModelRouter

        mock_cache.filter_models.return_value = free_models
        router = FreeModelRouter(mock_cache)

        result = await router.select_models(
            count=3, preferred_models=["deepseek/chat:free"]
        )

        assert result[0] == "deepseek/chat:free"
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_count_exceeds_available(self, mock_cache, free_models):
        from src.openrouter_mcp.free.router import FreeModelRouter

        mock_cache.filter_models.return_value = free_models
        router = FreeModelRouter(mock_cache)

        result = await router.select_models(count=10)

        assert len(result) == len(free_models)

    @pytest.mark.asyncio
    async def test_does_not_update_usage_counts(self, mock_cache, free_models):
        from src.openrouter_mcp.free.router import FreeModelRouter

        mock_cache.filter_models.return_value = free_models
        router = FreeModelRouter(mock_cache)

        await router.select_models(count=2)

        assert router._usage_counts == {}
