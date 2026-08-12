from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.openrouter_mcp.client.openrouter import (
    AuthenticationError,
    InvalidRequestError,
    OpenRouterError,
    RateLimitError,
)
from src.openrouter_mcp.free.quota import QuotaExceededError
from src.openrouter_mcp.handlers.free_chat import (
    FreeChatRequest,
    _aggregate_stream_chunks,
    _execute_chat,
    _normalize_chat_response,
    free_chat,
)
from src.openrouter_mcp.runtime_thrift import (
    get_thrift_metrics_snapshot,
    record_coalesced_savings,
    record_compaction_savings,
    record_prompt_cache_activity,
    reset_thrift_metrics,
)


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


@pytest.mark.unit
def test_aggregate_stream_chunks_uses_first_choices_and_last_truthy_usage():
    first_usage = {"total_tokens": 3}
    last_usage = {"total_tokens": 5}
    chunks = [
        {
            "choices": [
                {"delta": {"content": "first"}},
                {"delta": {"content": "ignored"}},
            ],
            "usage": first_usage,
        },
        {"choices": [], "usage": {}},
        {"choices": [{"delta": {"content": "-last"}}], "usage": last_usage},
    ]
    original_chunks = list(chunks)

    result = _aggregate_stream_chunks(chunks)

    assert result == {
        "content": "first-last",
        "usage": last_usage,
        "streamed": True,
        "actual_model": None,
    }
    assert result["usage"] is last_usage
    assert chunks == original_chunks
    assert chunks[0] is original_chunks[0]


@pytest.mark.unit
def test_aggregate_stream_chunks_keeps_previous_usage_after_falsy_values():
    usage = {"total_tokens": 3}

    result = _aggregate_stream_chunks(
        [
            {"usage": usage},
            {"usage": {}},
            {"usage": None},
        ]
    )

    assert result["usage"] is usage


@pytest.mark.unit
def test_aggregate_stream_chunks_preserves_non_string_content_error():
    with pytest.raises(TypeError):
        _aggregate_stream_chunks([{"choices": [{"delta": {"content": 7}}]}])


@pytest.mark.unit
def test_aggregate_stream_chunks_preserves_malformed_choices_error():
    with pytest.raises(KeyError) as raised:
        _aggregate_stream_chunks([{"choices": {"unexpected": "choice"}}])

    assert raised.value.args == (0,)


@pytest.mark.unit
def test_normalize_chat_response_uses_first_choice_and_preserves_values():
    usage = {"total_tokens": 3}
    actual_model = "".join(["provider/", "actual-model"])
    response = {
        "choices": [
            {"message": {"content": "first"}},
            {"message": {"content": "ignored"}},
        ],
        "usage": usage,
        "model": actual_model,
    }
    original_response = deepcopy(response)

    result = _normalize_chat_response(response)

    assert result == {
        "content": "first",
        "usage": usage,
        "streamed": False,
        "actual_model": actual_model,
    }
    assert result["usage"] is usage
    assert result["actual_model"] is actual_model
    assert response == original_response


@pytest.mark.unit
@pytest.mark.parametrize("choices", [None, [], ()])
def test_normalize_chat_response_preserves_falsey_choices_and_none_usage(choices):
    result = _normalize_chat_response(
        {"choices": choices, "usage": None, "model": None}
    )

    assert result == {
        "content": "",
        "usage": None,
        "streamed": False,
        "actual_model": None,
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "response",
    [
        {"choices": [None]},
        {"choices": [{"message": None}]},
    ],
)
def test_normalize_chat_response_preserves_malformed_choice_errors(response):
    with pytest.raises(AttributeError):
        _normalize_chat_response(response)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_chat_delegates_non_stream_response_normalization():
    client = AsyncMock()
    response = {"choices": []}
    client.chat_completion.return_value = response
    original_messages = [{"role": "user", "content": "original"}]
    effective_messages = [{"role": "user", "content": "compacted"}]
    compaction = MagicMock(messages=effective_messages)
    normalized = {"normalized": True}

    with patch(
        "src.openrouter_mcp.handlers.free_chat.compact_messages_for_model",
        new=AsyncMock(return_value=compaction),
    ) as compact, patch(
        "src.openrouter_mcp.handlers.free_chat._normalize_chat_response",
        return_value=normalized,
    ) as normalize:
        result = await _execute_chat(
            client,
            "provider/model",
            original_messages,
            0.25,
            17,
            False,
            fallback_models=["provider/model", "provider/fallback"],
        )

    assert result is normalized
    compact.assert_awaited_once_with(
        client,
        "provider/model",
        original_messages,
        max_completion_tokens=17,
    )
    client.chat_completion.assert_awaited_once_with(
        model="provider/model",
        messages=effective_messages,
        temperature=0.25,
        max_tokens=17,
        stream=False,
        models=["provider/model", "provider/fallback"],
    )
    normalize.assert_called_once_with(response)
    assert normalize.call_args.args[0] is response


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
    async def test_free_chat_returns_request_scoped_thrift_summary(self, mock_chat_response):
        reset_thrift_metrics()
        record_compaction_savings(42)
        record_coalesced_savings(prompt_tokens=100, completion_tokens=20, estimated_cost_usd=0.003)
        record_prompt_cache_activity(
            cached_prompt_tokens=300,
            cache_write_prompt_tokens=100,
            estimated_saved_cost_usd=0.007,
        )

        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router, patch(
            "src.openrouter_mcp.handlers.free_chat._execute_chat",
            new_callable=AsyncMock,
        ) as mock_execute_chat:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            async def execute_with_request_local_thrift(*args, **kwargs):
                record_compaction_savings(7)
                record_coalesced_savings(
                    prompt_tokens=30,
                    completion_tokens=10,
                    estimated_cost_usd=0.002,
                )
                record_prompt_cache_activity(
                    cached_prompt_tokens=120,
                    cache_write_prompt_tokens=40,
                    estimated_saved_cost_usd=0.004,
                )
                return {
                    "content": mock_chat_response["choices"][0]["message"]["content"],
                    "usage": mock_chat_response["usage"],
                    "streamed": False,
                    "actual_model": None,
                }

            mock_execute_chat.side_effect = execute_with_request_local_thrift

            result = await free_chat(FreeChatRequest(message="안녕!"))

            assert result["thrift_metrics"]["compacted_tokens"] == 7
            assert result["thrift_summary"]["saved_cost_usd"] == 0.006
            assert result["thrift_summary"]["prompt_savings_breakdown"]["cache_reuse_tokens"] == 120
            assert (
                result["thrift_summary"]["prompt_savings_breakdown"]["coalesced_prompt_tokens"]
                == 30
            )
            assert result["thrift_summary"]["cache_efficiency"]["reuse_to_write_ratio"] == 3.0
            mock_client.get_model_pricing.assert_not_called()
            assert get_thrift_metrics_snapshot()["compacted_tokens"] == 49
            assert get_thrift_metrics_snapshot()["saved_cost_usd"] == 0.016

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
            assert messages == [
                {
                    "role": "system",
                    "content": "You are a helpful assistant.",
                },
                {"role": "user", "content": "What is Python?"},
            ]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_free_chat_compacts_long_history(self, mock_chat_response):
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = mock_chat_response
            mock_client.model_cache.get_model_info = AsyncMock(
                return_value={"id": "google/gemma-3-27b:free", "context_length": 160}
            )
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(
                message="latest user question " * 30,
                system_prompt="You are a helpful assistant.",
                conversation_history=[
                    {"role": "user", "content": "older question one " * 40},
                    {"role": "assistant", "content": "same older answer " * 40},
                    {"role": "user", "content": "older question two " * 40},
                    {"role": "assistant", "content": "same older answer " * 40},
                    {"role": "user", "content": "recent question one " * 30},
                    {"role": "assistant", "content": "recent answer one " * 30},
                    {"role": "user", "content": "recent question two " * 30},
                    {"role": "assistant", "content": "recent answer two " * 30},
                ],
                max_tokens=16,
            )
            await free_chat(request)

            sent_messages = mock_client.chat_completion.call_args.kwargs["messages"]
            assert sent_messages[0]["role"] == "system"
            assert sent_messages[1]["role"] == "assistant"
            assert "Conversation summary" in sent_messages[1]["content"]
            assert sent_messages[-1]["content"] == "latest user question " * 30

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authentication_error_propagates_immediately(self):
        with patch(
            "src.openrouter_mcp.handlers.free_chat.get_openrouter_client"
        ) as mock_get_client, patch(
            "src.openrouter_mcp.handlers.free_chat._get_router"
        ) as mock_get_router:
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
