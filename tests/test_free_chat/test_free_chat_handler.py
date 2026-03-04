from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.openrouter_mcp.client.openrouter import (
    AuthenticationError,
    InvalidRequestError,
    OpenRouterError,
    RateLimitError,
)
from src.openrouter_mcp.free.quota import QuotaExceededError
from src.openrouter_mcp.handlers.free_chat import FreeChatRequest, free_chat


@pytest.fixture
def mock_chat_response():
    """Shared mock response without ``model`` field.

    The ``model`` key is intentionally omitted so that ``_build_result`` uses
    the ``model_id`` from ``select_model`` (same behaviour as pre-native-fallback).
    Tests that verify actual-model extraction should add ``model`` explicitly.
    """
    return {
        "id": "gen-free-001",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "안녕하세요!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }


@pytest.fixture(autouse=True)
def _disable_native_fallback():
    """Disable native fallback for tests that validate local retry loop.

    Patches _try_native_fallback to return None (skip) rather than manipulating
    the module-level flag, which avoids cache-expiry check side effects on mocks.
    """
    with patch(
        "src.openrouter_mcp.handlers.free_chat._try_native_fallback",
        new_callable=AsyncMock,
        return_value=None,
    ):
        yield


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
                "google/gemma-3-27b:free", cooldown_seconds=60.0
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

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_quota_exceeded_skips_model_selection(self):
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router, patch(
            "src.openrouter_mcp.handlers.free_chat._get_quota"
        ) as mock_get_quota:
            mock_get_client.return_value = AsyncMock()

            mock_router = AsyncMock()
            mock_get_router.return_value = mock_router

            mock_quota = AsyncMock()
            mock_quota.reserve_and_record.side_effect = QuotaExceededError(
                "일일 무료 사용 한도(50회)를 초과했습니다.",
                reset_time=MagicMock(),
            )
            mock_get_quota.return_value = mock_quota

            request = FreeChatRequest(message="Hello")
            with pytest.raises(QuotaExceededError, match="일일 무료 사용 한도"):
                await free_chat(request)

            mock_router.select_model.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_after_passed_to_report_rate_limit(self, mock_chat_response):
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = [
                RateLimitError("rate limited", retry_after=30.0),
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
            await free_chat(request)

            mock_router.report_rate_limit.assert_called_once_with(
                "google/gemma-3-27b:free", cooldown_seconds=30.0
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_after_zero_uses_zero_not_default(self, mock_chat_response):
        """Retry-After: 0 should pass 0.0, not fall back to DEFAULT_COOLDOWN_SECONDS."""
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = [
                RateLimitError("rate limited", retry_after=0.0),
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
            await free_chat(request)

            mock_router.report_rate_limit.assert_called_once_with(
                "google/gemma-3-27b:free", cooldown_seconds=0.0
            )

    @pytest.mark.unit
    def test_stream_default_false(self):
        request = FreeChatRequest(message="Hello")
        assert request.stream is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_non_streaming_includes_streamed_false(self, mock_chat_response):
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

            request = FreeChatRequest(message="Hello")
            result = await free_chat(request)

            assert result["streamed"] is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_streaming_collects_chunks(self):
        async def _fake_stream(**kwargs):
            chunks = [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {"content": " world"}}]},
                {"choices": [{"delta": {}}], "usage": {"total_tokens": 5}},
            ]
            for c in chunks:
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
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hello", stream=True)
            result = await free_chat(request)

            assert result["response"] == "Hello world"
            assert result["streamed"] is True
            assert result["usage"]["total_tokens"] == 5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_streaming_empty_choices_no_crash(self):
        """Chunks with choices=[] or missing choices should not crash."""
        async def _fake_stream(**kwargs):
            chunks = [
                {},
                {"choices": []},
                {"choices": [{"delta": {"content": "ok"}}]},
                {"choices": [{}]},
            ]
            for c in chunks:
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
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hello", stream=True)
            result = await free_chat(request)

            assert result["response"] == "ok"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_streaming_rate_limit_fallback(self):
        call_count = 0

        async def _fake_stream_fail(**kwargs):
            raise RateLimitError("rate limited")
            yield  # unreachable; makes this an async generator

        async def _fake_stream_ok(**kwargs):
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

            def _side_effect(**kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return _fake_stream_fail(**kwargs)
                return _fake_stream_ok(**kwargs)

            mock_client.stream_chat_completion = _side_effect
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.side_effect = ["model-a", "model-b"]
            mock_router.report_rate_limit = MagicMock()
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hello", stream=True)
            result = await free_chat(request)

            assert result["model_used"] == "model-b"
            assert result["response"] == "hi"
