from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.openrouter_mcp.client.openrouter import (
    AuthenticationError,
    InvalidRequestError,
    OpenRouterError,
    RateLimitError,
)
from src.openrouter_mcp.handlers.free_chat import FreeChatRequest, free_chat


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
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
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
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
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
            mock_router.report_rate_limit.assert_called_once_with(
                "google/gemma-3-27b:free"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_all_models_exhausted(self):
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
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
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
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
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = AuthenticationError(
                "Invalid API key"
            )
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
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
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

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_response_includes_task_type(self, mock_chat_response):
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router, patch(
            "src.openrouter_mcp.handlers.free_chat._get_metrics"
        ) as mock_get_metrics, patch(
            "src.openrouter_mcp.handlers.free_chat._get_classifier"
        ) as mock_get_classifier:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = mock_chat_response
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            mock_collector = MagicMock()
            mock_get_metrics.return_value = mock_collector

            from src.openrouter_mcp.free.classifier import TaskClassifier

            mock_get_classifier.return_value = TaskClassifier()

            request = FreeChatRequest(message="파이썬 코드를 작성해줘")
            result = await free_chat(request)

            assert "task_type" in result
            assert result["task_type"] == "coding"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_metrics_recorded_on_success(self, mock_chat_response):
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router, patch(
            "src.openrouter_mcp.handlers.free_chat._get_metrics"
        ) as mock_get_metrics, patch(
            "src.openrouter_mcp.handlers.free_chat._get_classifier"
        ) as mock_get_classifier:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = mock_chat_response
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            mock_collector = MagicMock()
            mock_get_metrics.return_value = mock_collector

            from src.openrouter_mcp.free.classifier import TaskClassifier

            mock_get_classifier.return_value = TaskClassifier()

            request = FreeChatRequest(message="Hello")
            await free_chat(request)

            mock_collector.record_success.assert_called_once()
            call_args = mock_collector.record_success.call_args
            assert call_args[0][0] == "google/gemma-3-27b:free"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_metrics_recorded_on_rate_limit(self, mock_chat_response):
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router, patch(
            "src.openrouter_mcp.handlers.free_chat._get_metrics"
        ) as mock_get_metrics, patch(
            "src.openrouter_mcp.handlers.free_chat._get_classifier"
        ) as mock_get_classifier:
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

            mock_collector = MagicMock()
            mock_get_metrics.return_value = mock_collector

            from src.openrouter_mcp.free.classifier import TaskClassifier

            mock_get_classifier.return_value = TaskClassifier()

            request = FreeChatRequest(message="Hello")
            await free_chat(request)

            mock_collector.record_failure.assert_called_once_with(
                "google/gemma-3-27b:free", "RateLimitError"
            )
            mock_collector.record_success.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_metrics_recorded_on_openrouter_error(self, mock_chat_response):
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router, patch(
            "src.openrouter_mcp.handlers.free_chat._get_metrics"
        ) as mock_get_metrics, patch(
            "src.openrouter_mcp.handlers.free_chat._get_classifier"
        ) as mock_get_classifier:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = [
                OpenRouterError("server error"),
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

            mock_collector = MagicMock()
            mock_get_metrics.return_value = mock_collector

            from src.openrouter_mcp.free.classifier import TaskClassifier

            mock_get_classifier.return_value = TaskClassifier()

            request = FreeChatRequest(message="Hello")
            await free_chat(request)

            mock_collector.record_failure.assert_called_once_with(
                "google/gemma-3-27b:free", "OpenRouterError"
            )
