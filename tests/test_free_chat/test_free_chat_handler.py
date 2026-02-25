import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.openrouter_mcp.handlers.free_chat import free_chat, FreeChatRequest
from src.openrouter_mcp.client.openrouter import (
    RateLimitError, OpenRouterError, AuthenticationError, InvalidRequestError,
)


@pytest.fixture
def mock_chat_response():
    return {
        "id": "gen-free-001",
        "model": "google/gemma-3-27b:free",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "안녕하세요!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }


class TestFreeChatHandler:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_successful_free_chat(self, mock_chat_response):
        with patch("src.openrouter_mcp.handlers.free_chat.get_openrouter_client") as mock_get_client, \
             patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = mock_chat_response
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(
                message="안녕!",
            )
            result = await free_chat(request)

            assert result["model_used"] == "google/gemma-3-27b:free"
            assert result["response"] == "안녕하세요!"
            assert result["usage"]["total_tokens"] == 8

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rate_limit_triggers_fallback(self, mock_chat_response):
        with patch("src.openrouter_mcp.handlers.free_chat.get_openrouter_client") as mock_get_client, \
             patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = [
                RateLimitError("rate limited"),
                mock_chat_response,
            ]
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.side_effect = [
                "google/gemma-3-27b:free",
                "meta-llama/llama-4-scout:free",
            ]
            mock_router.report_rate_limit = MagicMock()
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hello")
            result = await free_chat(request)

            assert result["model_used"] == "meta-llama/llama-4-scout:free"
            mock_router.report_rate_limit.assert_called_once_with("google/gemma-3-27b:free")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_all_models_exhausted(self):
        with patch("src.openrouter_mcp.handlers.free_chat.get_openrouter_client") as mock_get_client, \
             patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = RateLimitError("rate limited")
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.side_effect = [
                "model-a",
                "model-b",
                "model-c",
                RuntimeError("사용 가능한 free 모델이 없습니다"),
            ]
            mock_router.report_rate_limit = MagicMock()
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hello")
            with pytest.raises(RuntimeError, match="사용 가능한 free 모델이 없습니다"):
                await free_chat(request)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_system_prompt_included(self, mock_chat_response):
        with patch("src.openrouter_mcp.handlers.free_chat.get_openrouter_client") as mock_get_client, \
             patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = mock_chat_response
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(
                message="What is Python?",
                system_prompt="You are a helpful assistant.",
            )
            await free_chat(request)

            call_kwargs = mock_client.chat_completion.call_args[1]
            messages = call_kwargs["messages"]
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "You are a helpful assistant."
            assert messages[1]["role"] == "user"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authentication_error_propagates_immediately(self):
        with patch("src.openrouter_mcp.handlers.free_chat.get_openrouter_client") as mock_get_client, \
             patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = AuthenticationError("Invalid API key")
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hello")
            with pytest.raises(AuthenticationError, match="Invalid API key"):
                await free_chat(request)

            mock_router.report_rate_limit.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalid_request_error_propagates_immediately(self):
        with patch("src.openrouter_mcp.handlers.free_chat.get_openrouter_client") as mock_get_client, \
             patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = InvalidRequestError("Bad request")
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hello")
            with pytest.raises(InvalidRequestError, match="Bad request"):
                await free_chat(request)

            mock_router.report_rate_limit.assert_not_called()

    @pytest.mark.unit
    def test_request_validation_defaults(self):
        request = FreeChatRequest(message="Hello")
        assert request.temperature == 0.7
        assert request.max_tokens == 4096
        assert request.system_prompt == ""
        assert request.conversation_history == []
        assert request.preferred_models == []
