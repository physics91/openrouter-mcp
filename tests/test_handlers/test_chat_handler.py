from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.openrouter_mcp.client.openrouter import OpenRouterClient, OpenRouterError
from src.openrouter_mcp.handlers.chat import (
    ChatCompletionRequest,
    ModelListRequest,
    UsageStatsRequest,
    chat_with_model,
    get_usage_stats,
    list_available_models,
)
from src.openrouter_mcp.runtime_thrift import ThriftMetricsCollector, get_thrift_metrics_snapshot
from src.openrouter_mcp.runtime_thrift import metrics as thrift_metrics_module
from src.openrouter_mcp.runtime_thrift import (
    record_coalesced_savings,
    record_compaction_savings,
    record_model_request,
    record_prompt_cache_activity,
    record_recent_reuse_savings,
    reset_thrift_metrics,
)


class TestChatHandler:
    """Test cases for chat handler functions."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_with_model_success(self, mock_chat_response):
        """Test successful chat completion."""
        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.chat_completion.return_value = mock_chat_response
            mock_get_client.return_value = mock_client

            request = ChatCompletionRequest(
                model="openai/gpt-4",
                messages=[{"role": "user", "content": "Hello!"}],
                temperature=0.7,
                max_tokens=100,
            )

            result = await chat_with_model(request)

            assert result["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
            assert result["usage"]["total_tokens"] == 18

            mock_client.chat_completion.assert_called_once_with(
                model="openai/gpt-4",
                messages=[{"role": "user", "content": "Hello!"}],
                temperature=0.7,
                max_tokens=100,
                stream=False,
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_with_model_returns_request_scoped_thrift_metadata(self, mock_chat_response):
        reset_thrift_metrics()
        record_compaction_savings(42)
        record_coalesced_savings(prompt_tokens=100, completion_tokens=20, estimated_cost_usd=0.003)
        record_prompt_cache_activity(
            cached_prompt_tokens=300,
            cache_write_prompt_tokens=100,
            estimated_saved_cost_usd=0.007,
        )

        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)

            async def chat_completion_with_request_local_thrift(*args, **kwargs):
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
                return mock_chat_response

            mock_client.chat_completion.side_effect = chat_completion_with_request_local_thrift
            mock_get_client.return_value = mock_client

            result = await chat_with_model(
                ChatCompletionRequest(
                    model="openai/gpt-4",
                    messages=[{"role": "user", "content": "Hello!"}],
                )
            )

            assert result["thrift_metrics"]["compacted_tokens"] == 7
            assert result["thrift_summary"]["saved_cost_usd"] == 0.006
            assert result["thrift_summary"]["prompt_savings_breakdown"]["cache_reuse_tokens"] == 120
            assert (
                result["thrift_summary"]["prompt_savings_breakdown"]["coalesced_prompt_tokens"]
                == 30
            )
            assert get_thrift_metrics_snapshot()["compacted_tokens"] == 49
            assert get_thrift_metrics_snapshot()["saved_cost_usd"] == 0.016

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_with_model_streaming(self, mock_stream_response):
        """Test streaming chat completion."""
        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)

            async def mock_stream_gen():
                for chunk in mock_stream_response:
                    yield chunk

            mock_client.stream_chat_completion.return_value = mock_stream_gen()
            mock_get_client.return_value = mock_client

            request = ChatCompletionRequest(
                model="openai/gpt-4",
                messages=[{"role": "user", "content": "Hello!"}],
                stream=True,
            )

            result = await chat_with_model(request)

            # For streaming, result should be a list of chunks
            assert isinstance(result, list)
            assert len(result) == 3
            assert result[0]["choices"][0]["delta"]["content"] == "Hello"
            assert result[2]["usage"]["total_tokens"] == 18

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_with_model_streaming_attaches_request_scoped_thrift_to_final_chunk(
        self, mock_stream_response
    ):
        reset_thrift_metrics()
        record_compaction_savings(42)

        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)

            async def mock_stream_gen():
                record_compaction_savings(5)
                record_prompt_cache_activity(
                    cached_prompt_tokens=80,
                    cache_write_prompt_tokens=20,
                    estimated_saved_cost_usd=0.005,
                )
                for chunk in mock_stream_response:
                    yield chunk

            mock_client.stream_chat_completion.return_value = mock_stream_gen()
            mock_get_client.return_value = mock_client

            result = await chat_with_model(
                ChatCompletionRequest(
                    model="openai/gpt-4",
                    messages=[{"role": "user", "content": "Hello!"}],
                    stream=True,
                )
            )

            assert len(result) == 3
            assert "thrift_metrics" not in result[0]
            assert result[-1]["thrift_metrics"]["compacted_tokens"] == 5
            assert result[-1]["thrift_summary"]["saved_cost_usd"] == 0.005
            assert (
                result[-1]["thrift_summary"]["prompt_savings_breakdown"]["cache_reuse_tokens"] == 80
            )
            assert get_thrift_metrics_snapshot()["compacted_tokens"] == 47

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_with_model_validation_error(self):
        """Test chat completion with validation error."""
        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.chat_completion.side_effect = ValueError("Invalid model")
            mock_get_client.return_value = mock_client

            request = ChatCompletionRequest(
                model="",  # Invalid empty model
                messages=[{"role": "user", "content": "Hello!"}],
            )

            with pytest.raises(ValueError, match="Invalid model"):
                await chat_with_model(request)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_with_model_api_error(self):
        """Test chat completion with API error."""
        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.chat_completion.side_effect = OpenRouterError("API error")
            mock_get_client.return_value = mock_client

            request = ChatCompletionRequest(
                model="openai/gpt-4", messages=[{"role": "user", "content": "Hello!"}]
            )

            with pytest.raises(OpenRouterError, match="API error"):
                await chat_with_model(request)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_with_model_compacts_long_conversation(self, mock_chat_response):
        """Long conversations should be compacted before chat completion."""
        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.chat_completion.return_value = mock_chat_response
            mock_client.model_cache.get_model_info = AsyncMock(
                return_value={"id": "openai/gpt-4", "context_length": 160}
            )
            mock_get_client.return_value = mock_client

            request = ChatCompletionRequest(
                model="openai/gpt-4",
                messages=[
                    {"role": "system", "content": "You are concise and helpful."},
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

            await chat_with_model(request)

            sent_messages = mock_client.chat_completion.call_args.kwargs["messages"]
            assert sent_messages[0]["role"] == "system"
            assert sent_messages[1]["role"] == "assistant"
            assert "Conversation summary" in sent_messages[1]["content"]
            assert sent_messages[2]["content"] == "recent question one " * 30
            assert sent_messages[-1]["content"] == "recent answer two " * 30

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_available_models_success(self, mock_models_response):
        """Test successful model listing."""
        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.list_models.return_value = mock_models_response["data"]
            mock_get_client.return_value = mock_client

            request = ModelListRequest()

            result = await list_available_models(request)

            assert len(result) == 2
            assert result[0]["id"] == "openai/gpt-4"
            assert result[1]["id"] == "anthropic/claude-3-haiku"

            mock_client.list_models.assert_called_once_with(filter_by=None)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_available_models_with_filter(self, mock_models_response):
        """Test model listing with filter."""
        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            # Filter results to only include GPT models
            filtered_models = [
                model for model in mock_models_response["data"] if "gpt" in model["id"].lower()
            ]
            mock_client.list_models.return_value = filtered_models
            mock_get_client.return_value = mock_client

            request = ModelListRequest(filter_by="gpt")

            result = await list_available_models(request)

            assert len(result) == 1
            assert result[0]["id"] == "openai/gpt-4"

            mock_client.list_models.assert_called_once_with(filter_by="gpt")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_available_models_api_error(self):
        """Test model listing with API error."""
        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.list_models.side_effect = OpenRouterError("API error")
            mock_get_client.return_value = mock_client

            request = ModelListRequest()

            with pytest.raises(OpenRouterError, match="API error"):
                await list_available_models(request)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_usage_stats_success(self):
        """Test successful usage stats retrieval."""
        usage_data = {
            "total_cost": 0.00054,
            "total_tokens": 18,
            "requests": 1,
            "models": ["openai/gpt-4"],
        }

        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.track_usage.return_value = usage_data
            mock_get_client.return_value = mock_client

            request = UsageStatsRequest(start_date="2024-01-01", end_date="2024-01-31")

            result = await get_usage_stats(request)

            assert result["total_cost"] == 0.00054
            assert result["total_tokens"] == 18
            assert result["requests"] == 1
            assert "openai/gpt-4" in result["models"]

            mock_client.track_usage.assert_called_once_with(
                start_date="2024-01-01", end_date="2024-01-31"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_usage_stats_no_dates(self):
        """Test usage stats retrieval without date range."""
        usage_data = {
            "total_cost": 0.00054,
            "total_tokens": 18,
            "requests": 1,
            "models": ["openai/gpt-4"],
        }

        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.track_usage.return_value = usage_data
            mock_get_client.return_value = mock_client

            request = UsageStatsRequest()

            result = await get_usage_stats(request)

            assert result["total_cost"] == 0.00054

            mock_client.track_usage.assert_called_once_with(start_date=None, end_date=None)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_usage_stats_includes_thrift_metrics(self):
        """Usage stats should include thrift savings metadata."""
        reset_thrift_metrics()
        record_compaction_savings(42)
        usage_data = {
            "total_cost": 0.00054,
            "total_tokens": 18,
            "requests": 1,
            "models": ["openai/gpt-4"],
        }

        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.track_usage.return_value = usage_data
            mock_get_client.return_value = mock_client

            result = await get_usage_stats(UsageStatsRequest())

            assert result["thrift_metrics"]["compacted_tokens"] == 42

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_usage_stats_includes_thrift_summary(self):
        reset_thrift_metrics()
        record_compaction_savings(42)
        record_coalesced_savings(prompt_tokens=100, completion_tokens=20, estimated_cost_usd=0.003)
        record_recent_reuse_savings(
            prompt_tokens=25,
            completion_tokens=5,
            estimated_cost_usd=0.001,
        )
        record_model_request("anthropic/claude-sonnet-4")
        record_prompt_cache_activity(
            cached_prompt_tokens=300,
            cache_write_prompt_tokens=100,
            estimated_saved_cost_usd=0.007,
            model="anthropic/claude-sonnet-4",
        )
        usage_data = {
            "total_cost": 0.09,
            "total_tokens": 1800,
            "requests": 10,
            "models": ["anthropic/claude-sonnet-4"],
        }

        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.track_usage.return_value = usage_data
            mock_get_client.return_value = mock_client

            result = await get_usage_stats(UsageStatsRequest())

            assert result["thrift_summary"]["saved_cost_usd"] == 0.011
            assert result["thrift_summary"]["estimated_cost_without_thrift_usd"] == 0.101
            assert result["thrift_summary"]["effective_cost_reduction_pct"] == 10.89
            assert result["thrift_summary"]["prompt_savings_breakdown"]["cache_reuse_tokens"] == 300
            assert (
                result["thrift_summary"]["prompt_savings_breakdown"]["coalesced_prompt_tokens"]
                == 100
            )
            assert (
                result["thrift_summary"]["prompt_savings_breakdown"]["recent_reuse_prompt_tokens"]
                == 25
            )
            assert result["thrift_summary"]["prompt_savings_breakdown"]["compacted_tokens"] == 42
            assert result["thrift_summary"]["request_savings_breakdown"] == {
                "coalesced_requests": 1,
                "recent_reuse_requests": 1,
                "deferred_requests": 0,
            }
            assert result["thrift_summary"]["cache_efficiency"]["cache_write_prompt_tokens"] == 100
            assert result["thrift_summary"]["cache_efficiency"]["cache_hit_requests"] == 1
            assert result["thrift_summary"]["cache_efficiency"]["cache_write_requests"] == 1
            assert (
                result["thrift_summary"]["cache_efficiency"]["cache_hit_request_rate_pct"] == 10.0
            )
            assert (
                result["thrift_summary"]["cache_efficiency"]["cache_write_request_rate_pct"] == 10.0
            )
            assert result["thrift_summary"]["cache_efficiency"]["reuse_to_write_ratio"] == 3.0
            assert (
                result["thrift_summary"]["cache_efficiency_by_provider"]["anthropic"][
                    "cache_hit_request_rate_pct"
                ]
                == 100.0
            )
            assert (
                result["thrift_summary"]["cache_efficiency_by_model"]["anthropic/claude-sonnet-4"][
                    "cache_write_request_rate_pct"
                ]
                == 100.0
            )
            assert result["thrift_summary"]["cache_hotspots"] == {
                "providers": [
                    {
                        "provider": "anthropic",
                        "saved_cost_usd": 0.007,
                        "cached_prompt_tokens": 300,
                        "cache_hit_request_rate_pct": 100.0,
                        "cache_write_request_rate_pct": 100.0,
                        "reuse_to_write_ratio": 3.0,
                        "reason": "Hit volume keeps pace with writes, so warming converts into real savings",
                    }
                ],
                "models": [
                    {
                        "model": "anthropic/claude-sonnet-4",
                        "saved_cost_usd": 0.007,
                        "cached_prompt_tokens": 300,
                        "cache_hit_request_rate_pct": 100.0,
                        "cache_write_request_rate_pct": 100.0,
                        "reuse_to_write_ratio": 3.0,
                        "reason": "Hit volume keeps pace with writes, so warming converts into real savings",
                    }
                ],
            }
            assert result["thrift_summary"]["cache_deadspots"] == {
                "providers": [],
                "models": [],
            }

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_usage_stats_uses_date_filtered_thrift_rollup(self, tmp_path, monkeypatch):
        current_time = {"value": datetime(2026, 4, 10, 12, 0, 0)}
        collector = ThriftMetricsCollector(
            persistence_path=str(tmp_path / "runtime_thrift_metrics.json"),
            now_provider=lambda: current_time["value"],
        )
        monkeypatch.setattr(thrift_metrics_module, "_collector", collector)

        record_compaction_savings(10)
        record_coalesced_savings(
            prompt_tokens=100,
            completion_tokens=20,
            estimated_cost_usd=0.003,
        )
        record_model_request("anthropic/claude-sonnet-4")
        record_prompt_cache_activity(
            cached_prompt_tokens=300,
            cache_write_prompt_tokens=100,
            estimated_saved_cost_usd=0.007,
            model="anthropic/claude-sonnet-4",
        )

        current_time["value"] = datetime(2026, 4, 11, 12, 0, 0)
        record_recent_reuse_savings(
            prompt_tokens=25,
            completion_tokens=5,
            estimated_cost_usd=0.001,
        )
        record_model_request("openai/gpt-4o-mini")
        record_prompt_cache_activity(
            cached_prompt_tokens=80,
            cache_write_prompt_tokens=20,
            estimated_saved_cost_usd=0.002,
            model="openai/gpt-4o-mini",
        )

        usage_data = {
            "total_cost": 0.09,
            "total_tokens": 1800,
            "requests": 10,
            "models": ["anthropic/claude-sonnet-4"],
        }

        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.track_usage.return_value = usage_data
            mock_get_client.return_value = mock_client

            result = await get_usage_stats(
                UsageStatsRequest(
                    start_date="2026-04-10",
                    end_date="2026-04-10",
                )
            )

            assert result["thrift_summary"]["saved_cost_usd"] == 0.01
            assert result["thrift_summary"]["prompt_savings_breakdown"] == {
                "cache_reuse_tokens": 300,
                "coalesced_prompt_tokens": 100,
                "recent_reuse_prompt_tokens": 0,
                "compacted_tokens": 10,
            }
            assert result["thrift_summary"]["request_savings_breakdown"] == {
                "coalesced_requests": 1,
                "recent_reuse_requests": 0,
                "deferred_requests": 0,
            }
            assert "openai" not in result["thrift_summary"]["cache_efficiency_by_provider"]
            assert (
                result["thrift_summary"]["cache_efficiency_by_provider"]["anthropic"][
                    "cached_prompt_tokens"
                ]
                == 300
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_usage_stats_api_error(self):
        """Test usage stats retrieval with API error."""
        with patch("src.openrouter_mcp.handlers.chat.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.track_usage.side_effect = OpenRouterError("API error")
            mock_get_client.return_value = mock_client

            request = UsageStatsRequest()

            with pytest.raises(OpenRouterError, match="API error"):
                await get_usage_stats(request)

    @pytest.mark.unit
    def test_chat_completion_request_validation(self):
        """Test ChatCompletionRequest validation."""
        # Valid request
        request = ChatCompletionRequest(
            model="openai/gpt-4", messages=[{"role": "user", "content": "Hello!"}]
        )
        assert request.model == "openai/gpt-4"
        assert len(request.messages) == 1
        assert request.temperature == 0.7  # default value
        assert request.max_tokens is None  # default value
        assert request.stream is False  # default value

        # Request with custom parameters
        request_custom = ChatCompletionRequest(
            model="anthropic/claude-3-haiku",
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello!"},
            ],
            temperature=0.5,
            max_tokens=200,
            stream=True,
        )
        assert request_custom.temperature == 0.5
        assert request_custom.max_tokens == 200
        assert request_custom.stream is True

    @pytest.mark.unit
    def test_model_list_request_validation(self):
        """Test ModelListRequest validation."""
        # Default request
        request = ModelListRequest()
        assert request.filter_by is None

        # Request with filter
        request_filtered = ModelListRequest(filter_by="gpt")
        assert request_filtered.filter_by == "gpt"

    @pytest.mark.unit
    def test_usage_stats_request_validation(self):
        """Test UsageStatsRequest validation."""
        # Default request
        request = UsageStatsRequest()
        assert request.start_date is None
        assert request.end_date is None

        # Request with date range
        request_dated = UsageStatsRequest(start_date="2024-01-01", end_date="2024-01-31")
        assert request_dated.start_date == "2024-01-01"
        assert request_dated.end_date == "2024-01-31"
