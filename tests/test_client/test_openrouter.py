import asyncio
import os
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.openrouter_mcp.client.openrouter import (
    AuthenticationError,
    InvalidRequestError,
    OpenRouterClient,
    OpenRouterError,
    RateLimitError,
)
from src.openrouter_mcp.runtime_thrift import (
    RequestCoalescer,
    get_thrift_metrics_snapshot,
    reset_thrift_metrics,
)


class TestOpenRouterClient:
    """Test cases for OpenRouterClient."""

    @pytest.mark.unit
    def test_client_initialization_with_api_key(self, mock_api_key):
        """Test client initialization with API key."""
        client = OpenRouterClient(api_key=mock_api_key)

        assert client.api_key == mock_api_key
        assert client.base_url == "https://openrouter.ai/api/v1"
        assert client.app_name is None
        assert client.http_referer is None

    @pytest.mark.unit
    def test_client_initialization_with_all_params(self, mock_api_key):
        """Test client initialization with all parameters."""
        client = OpenRouterClient(
            api_key=mock_api_key,
            base_url="https://custom.api.com/v1",
            app_name="test-app",
            http_referer="https://test.com",
        )

        assert client.api_key == mock_api_key
        assert client.base_url == "https://custom.api.com/v1"
        assert client.app_name == "test-app"
        assert client.http_referer == "https://test.com"

    @pytest.mark.unit
    def test_client_initialization_from_env(self, mock_env_vars):
        """Test client initialization from environment variables."""
        client = OpenRouterClient.from_env()

        assert client.api_key == os.getenv("OPENROUTER_API_KEY")
        assert client.base_url == os.getenv("OPENROUTER_BASE_URL")
        assert client.app_name == os.getenv("OPENROUTER_APP_NAME")
        assert client.http_referer == os.getenv("OPENROUTER_HTTP_REFERER")

    @pytest.mark.unit
    def test_client_initialization_missing_api_key(self):
        """Test client initialization fails without API key."""
        with pytest.raises(ValueError, match="API key is required"):
            OpenRouterClient(api_key="")

    @pytest.mark.unit
    def test_headers_construction(self, mock_api_key):
        """Test HTTP headers are constructed correctly."""
        client = OpenRouterClient(
            api_key=mock_api_key, app_name="test-app", http_referer="https://test.com"
        )

        headers = client._get_headers()

        assert headers["Authorization"] == f"Bearer {mock_api_key}"
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Title"] == "test-app"
        assert headers["HTTP-Referer"] == "https://test.com"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_models_success(self, mock_api_key, mock_models_response, create_response):
        """Test successful models listing."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_models_response

            models = await client.list_models()

            assert len(models) == 2
            assert models[0]["id"] == "openai/gpt-4"
            assert models[1]["id"] == "anthropic/claude-3-haiku"
            mock_request.assert_called_once_with("GET", "/models", params={})

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_models_with_filter(
        self, mock_api_key, mock_models_response, create_response
    ):
        """Test models listing with filter."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_models_response

            await client.list_models(filter_by="openai")

            mock_request.assert_called_once_with("GET", "/models", params={"filter": "openai"})

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_model_info_success(self, mock_api_key, mock_models_response):
        """Test successful model info retrieval."""
        client = OpenRouterClient(api_key=mock_api_key)
        model_data = mock_models_response["data"][0]

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = model_data

            model_info = await client.get_model_info("openai/gpt-4")

            assert model_info["id"] == "openai/gpt-4"
            assert model_info["name"] == "GPT-4"
            mock_request.assert_called_once_with("GET", "/models/openai/gpt-4")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_success(self, mock_api_key, mock_chat_response):
        """Test successful chat completion."""
        client = OpenRouterClient(api_key=mock_api_key)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ]

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_chat_response

            response = await client.chat_completion(
                model="openai/gpt-4", messages=messages, temperature=0.7, max_tokens=100
            )

            assert (
                response["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
            )
            assert response["usage"]["total_tokens"] == 18

            expected_payload = {
                "model": "openai/gpt-4",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 100,
                "stream": False,
            }
            mock_request.assert_called_once_with("POST", "/chat/completions", json=expected_payload)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_coalesces_identical_concurrent_requests(
        self, mock_api_key, mock_chat_response
    ):
        """Identical concurrent non-streaming requests should share one upstream call."""
        client = OpenRouterClient(api_key=mock_api_key)
        messages = [{"role": "user", "content": "Hello!"}]
        call_count = 0

        async def delayed_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return mock_chat_response

        with patch.object(client, "_make_request", side_effect=delayed_response):
            first, second = await asyncio.gather(
                client.chat_completion(
                    model="openai/gpt-4",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=100,
                ),
                client.chat_completion(
                    model="openai/gpt-4",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=100,
                ),
            )

        assert first == mock_chat_response
        assert second == mock_chat_response
        assert call_count == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_clears_failed_coalesced_request(
        self, mock_api_key, mock_chat_response
    ):
        """Failed coalesced requests should not poison later retries."""
        client = OpenRouterClient(api_key=mock_api_key)
        messages = [{"role": "user", "content": "Hello!"}]
        attempts = 0

        async def flaky_response(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            await asyncio.sleep(0.01)
            if attempts == 1:
                raise OpenRouterError("boom")
            return mock_chat_response

        with patch.object(client, "_make_request", side_effect=flaky_response):
            with pytest.raises(OpenRouterError, match="boom"):
                await asyncio.gather(
                    client.chat_completion(model="openai/gpt-4", messages=messages),
                    client.chat_completion(model="openai/gpt-4", messages=messages),
                )

            response = await client.chat_completion(model="openai/gpt-4", messages=messages)

        assert response == mock_chat_response
        assert attempts == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_records_coalesced_savings_metrics(
        self, mock_api_key, mock_chat_response
    ):
        """Follower joins should record avoided prompt/completion spend."""
        reset_thrift_metrics()
        client = OpenRouterClient(api_key=mock_api_key)
        messages = [{"role": "user", "content": "Hello!"}]

        async def delayed_response(*args, **kwargs):
            await asyncio.sleep(0.01)
            return mock_chat_response

        with patch.object(client, "_make_request", side_effect=delayed_response):
            await asyncio.gather(
                client.chat_completion(
                    model="openai/gpt-4",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=100,
                ),
                client.chat_completion(
                    model="openai/gpt-4",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=100,
                ),
            )

        metrics = get_thrift_metrics_snapshot()
        assert metrics["coalesced_requests"] == 1
        assert metrics["saved_prompt_tokens"] > 0
        assert metrics["saved_completion_tokens"] > 0
        assert metrics["saved_cost_usd"] > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_reuses_recent_response_within_ttl_window(
        self, mock_api_key, mock_chat_response, monkeypatch
    ):
        """Sequential identical requests should reuse a fresh cached response within TTL."""
        reset_thrift_metrics()
        monkeypatch.setenv("OPENROUTER_THRIFT_COALESCING_TTL_SECONDS", "30")

        client = OpenRouterClient(api_key=mock_api_key)
        now = [100.0]
        client._chat_coalescer = RequestCoalescer(time_fn=lambda: now[0])
        messages = [{"role": "user", "content": "Hello!"}]
        call_count = 0

        async def immediate_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_chat_response

        with patch.object(client, "_make_request", side_effect=immediate_response):
            first = await client.chat_completion(
                model="openai/gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=100,
            )
            second = await client.chat_completion(
                model="openai/gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=100,
            )

        metrics = get_thrift_metrics_snapshot()
        assert first == mock_chat_response
        assert second == mock_chat_response
        assert call_count == 1
        assert metrics["coalesced_requests"] == 0
        assert metrics["recent_reuse_requests"] == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_skips_recent_response_reuse_when_ttl_zero(
        self, mock_api_key, mock_chat_response, monkeypatch
    ):
        """TTL zero should keep the coalescer in in-flight-only mode."""
        reset_thrift_metrics()
        monkeypatch.setenv("OPENROUTER_THRIFT_COALESCING_TTL_SECONDS", "0")

        client = OpenRouterClient(api_key=mock_api_key)
        now = [100.0]
        client._chat_coalescer = RequestCoalescer(time_fn=lambda: now[0])
        messages = [{"role": "user", "content": "Hello!"}]
        call_count = 0

        async def immediate_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_chat_response

        with patch.object(client, "_make_request", side_effect=immediate_response):
            await client.chat_completion(
                model="openai/gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=100,
            )
            await client.chat_completion(
                model="openai/gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=100,
            )

        metrics = get_thrift_metrics_snapshot()
        assert call_count == 2
        assert metrics["coalesced_requests"] == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_refreshes_recent_response_after_ttl_expires(
        self, mock_api_key, mock_chat_response, monkeypatch
    ):
        """Recent response reuse should expire once the configured TTL elapses."""
        reset_thrift_metrics()
        monkeypatch.setenv("OPENROUTER_THRIFT_COALESCING_TTL_SECONDS", "5")

        client = OpenRouterClient(api_key=mock_api_key)
        now = [100.0]
        client._chat_coalescer = RequestCoalescer(time_fn=lambda: now[0])
        messages = [{"role": "user", "content": "Hello!"}]
        call_count = 0

        async def immediate_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_chat_response

        with patch.object(client, "_make_request", side_effect=immediate_response):
            await client.chat_completion(
                model="openai/gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=100,
            )
            now[0] += 6.0
            await client.chat_completion(
                model="openai/gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=100,
            )

        metrics = get_thrift_metrics_snapshot()
        assert call_count == 2
        assert metrics["coalesced_requests"] == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_skips_coalescing_when_policy_disabled(
        self, mock_api_key, mock_chat_response, monkeypatch
    ):
        reset_thrift_metrics()
        monkeypatch.setenv("OPENROUTER_THRIFT_ENABLE_GENERATION_COALESCING", "false")

        client = OpenRouterClient(api_key=mock_api_key)
        messages = [{"role": "user", "content": "Hello!"}]
        call_count = 0

        async def delayed_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return mock_chat_response

        with patch.object(client, "_make_request", side_effect=delayed_response):
            await asyncio.gather(
                client.chat_completion(
                    model="openai/gpt-4",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=100,
                ),
                client.chat_completion(
                    model="openai/gpt-4",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=100,
                ),
            )

        metrics = get_thrift_metrics_snapshot()
        assert call_count == 2
        assert metrics["coalesced_requests"] == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_adds_prefix_cache_breakpoint_for_anthropic(
        self, mock_api_key, mock_chat_response
    ):
        client = OpenRouterClient(api_key=mock_api_key)
        messages = [
            {"role": "system", "content": "stable instruction block " * 1500},
            {"role": "user", "content": "latest question"},
        ]

        with patch.object(client, "_make_request", return_value=mock_chat_response) as mock_request:
            await client.chat_completion(
                model="anthropic/claude-sonnet-4",
                messages=messages,
                temperature=0.2,
                max_tokens=64,
            )

        payload = mock_request.call_args.kwargs["json"]
        assert isinstance(payload["messages"][0]["content"], list)
        assert payload["messages"][0]["content"][-1]["cache_control"] == {"type": "ephemeral"}
        assert payload["messages"][1] == messages[1]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_skips_prefix_cache_breakpoint_when_policy_disabled(
        self, mock_api_key, mock_chat_response, monkeypatch
    ):
        monkeypatch.setenv("OPENROUTER_THRIFT_ENABLE_PREFIX_CACHE_PLANNER", "false")
        client = OpenRouterClient(api_key=mock_api_key)
        messages = [
            {"role": "system", "content": "stable instruction block " * 1500},
            {"role": "user", "content": "latest question"},
        ]

        with patch.object(client, "_make_request", return_value=mock_chat_response) as mock_request:
            await client.chat_completion(
                model="anthropic/claude-sonnet-4",
                messages=messages,
                temperature=0.2,
                max_tokens=64,
            )

        payload = mock_request.call_args.kwargs["json"]
        assert payload["messages"] == messages

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_records_cached_prompt_token_savings(self, mock_api_key):
        reset_thrift_metrics()
        client = OpenRouterClient(api_key=mock_api_key)
        response = {
            "id": "gen-cache-hit",
            "model": "anthropic/claude-sonnet-4",
            "choices": [{"message": {"role": "assistant", "content": "cached answer"}}],
            "usage": {
                "prompt_tokens": 1300,
                "completion_tokens": 40,
                "total_tokens": 1340,
                "prompt_tokens_details": {
                    "cached_tokens": 1200,
                    "cache_write_tokens": 0,
                },
            },
        }

        with patch.object(client, "_make_request", return_value=response), patch.object(
            client,
            "get_model_pricing",
            AsyncMock(return_value={"prompt": 0.00001, "completion": 0.00002}),
        ):
            await client.chat_completion(
                model="anthropic/claude-sonnet-4",
                messages=[
                    {"role": "system", "content": "stable instruction block " * 1500},
                    {"role": "user", "content": "latest question"},
                ],
                max_tokens=64,
            )

        metrics = get_thrift_metrics_snapshot()
        assert metrics["cached_prompt_tokens"] == 1200
        assert metrics["cache_write_prompt_tokens"] == 0
        assert metrics["saved_cost_usd"] > 0
        assert metrics["cache_efficiency_by_provider"]["anthropic"]["observed_requests"] == 1
        assert metrics["cache_efficiency_by_provider"]["anthropic"]["cache_hit_requests"] == 1
        assert (
            metrics["cache_efficiency_by_model"]["anthropic/claude-sonnet-4"][
                "cached_prompt_tokens"
            ]
            == 1200
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_records_cache_write_tokens(self, mock_api_key):
        reset_thrift_metrics()
        client = OpenRouterClient(api_key=mock_api_key)
        response = {
            "id": "gen-cache-write",
            "model": "anthropic/claude-sonnet-4",
            "choices": [{"message": {"role": "assistant", "content": "warm cache"}}],
            "usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 40,
                "total_tokens": 1240,
                "prompt_tokens_details": {
                    "cached_tokens": 0,
                    "cache_write_tokens": 1024,
                },
            },
        }

        with patch.object(client, "_make_request", return_value=response), patch.object(
            client,
            "get_model_pricing",
            AsyncMock(return_value={"prompt": 0.00001, "completion": 0.00002}),
        ):
            await client.chat_completion(
                model="anthropic/claude-sonnet-4",
                messages=[
                    {"role": "system", "content": "stable instruction block " * 1500},
                    {"role": "user", "content": "latest question"},
                ],
                max_tokens=64,
            )

        metrics = get_thrift_metrics_snapshot()
        assert metrics["cached_prompt_tokens"] == 0
        assert metrics["cache_write_prompt_tokens"] == 1024
        assert metrics["cache_efficiency_by_provider"]["anthropic"]["cache_write_requests"] == 1
        assert (
            metrics["cache_efficiency_by_model"]["anthropic/claude-sonnet-4"][
                "cache_write_prompt_tokens"
            ]
            == 1024
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_chat_completion_success(self, mock_api_key, mock_stream_response):
        """Test successful streaming chat completion."""
        client = OpenRouterClient(api_key=mock_api_key)

        messages = [{"role": "user", "content": "Hello!"}]

        with patch.object(client, "_stream_request") as mock_stream:

            async def mock_stream_gen():
                for chunk in mock_stream_response:
                    yield chunk

            mock_stream.return_value = mock_stream_gen()

            chunks = []
            async for chunk in client.stream_chat_completion(
                model="openai/gpt-4", messages=messages
            ):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
            assert chunks[2]["usage"]["total_tokens"] == 18

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_chat_completion_records_cached_prompt_token_savings(self, mock_api_key):
        reset_thrift_metrics()
        client = OpenRouterClient(api_key=mock_api_key)
        chunks = [
            {"choices": [{"delta": {"content": "warm"}}]},
            {
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 1100,
                    "completion_tokens": 20,
                    "total_tokens": 1120,
                    "prompt_tokens_details": {
                        "cached_tokens": 1024,
                        "cache_write_tokens": 0,
                    },
                },
            },
        ]

        async def mock_stream_gen():
            for chunk in chunks:
                yield chunk

        with patch.object(client, "_stream_request", return_value=mock_stream_gen()), patch.object(
            client,
            "get_model_pricing",
            AsyncMock(return_value={"prompt": 0.00001, "completion": 0.00002}),
        ):
            seen = []
            async for chunk in client.stream_chat_completion(
                model="anthropic/claude-sonnet-4",
                messages=[
                    {"role": "system", "content": "stable instruction block " * 1500},
                    {"role": "user", "content": "latest question"},
                ],
                max_tokens=64,
            ):
                seen.append(chunk)

        metrics = get_thrift_metrics_snapshot()
        assert len(seen) == 2
        assert metrics["cached_prompt_tokens"] == 1024
        assert metrics["cache_write_prompt_tokens"] == 0
        assert metrics["saved_cost_usd"] > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_chat_completion_records_cache_write_tokens(self, mock_api_key):
        reset_thrift_metrics()
        client = OpenRouterClient(api_key=mock_api_key)
        chunks = [
            {"choices": [{"delta": {"content": "warm"}}]},
            {
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 1100,
                    "completion_tokens": 20,
                    "total_tokens": 1120,
                    "prompt_tokens_details": {
                        "cached_tokens": 0,
                        "cache_write_tokens": 1024,
                    },
                },
            },
        ]

        async def mock_stream_gen():
            for chunk in chunks:
                yield chunk

        with patch.object(client, "_stream_request", return_value=mock_stream_gen()), patch.object(
            client,
            "get_model_pricing",
            AsyncMock(return_value={"prompt": 0.00001, "completion": 0.00002}),
        ):
            async for _chunk in client.stream_chat_completion(
                model="anthropic/claude-sonnet-4",
                messages=[
                    {"role": "system", "content": "stable instruction block " * 1500},
                    {"role": "user", "content": "latest question"},
                ],
                max_tokens=64,
            ):
                pass

        metrics = get_thrift_metrics_snapshot()
        assert metrics["cached_prompt_tokens"] == 0
        assert metrics["cache_write_prompt_tokens"] == 1024

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_track_usage_success(self, mock_api_key):
        """Test successful usage tracking."""
        client = OpenRouterClient(api_key=mock_api_key)

        usage_data = {
            "total_cost": 0.00054,
            "total_tokens": 18,
            "requests": 1,
            "models": ["openai/gpt-4"],
        }

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = usage_data

            usage = await client.track_usage(start_date="2024-01-01", end_date="2024-01-31")

            assert usage["total_cost"] == 0.00054
            assert usage["total_tokens"] == 18

            expected_params = {"start_date": "2024-01-01", "end_date": "2024-01-31"}
            mock_request.assert_called_once_with("GET", "/generation", params=expected_params)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authentication_error(self, mock_api_key, mock_error_response):
        """Test authentication error handling."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)

        with patch.object(client._client, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = mock_error_response
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Unauthorized", request=Mock(), response=mock_response
            )
            mock_request.return_value = mock_response

            with pytest.raises(AuthenticationError, match="Invalid API key provided"):
                await client.list_models()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, mock_api_key):
        """Test rate limit error handling."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)

        with patch.object(client._client, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.json.return_value = {
                "error": {
                    "type": "rate_limit_exceeded",
                    "message": "Rate limit exceeded",
                }
            }
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Too Many Requests", request=Mock(), response=mock_response
            )
            mock_request.return_value = mock_response

            with pytest.raises(RateLimitError, match="Rate limit exceeded"):
                await client.list_models()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalid_request_error(self, mock_api_key):
        """Test invalid request error handling."""
        client = OpenRouterClient(api_key=mock_api_key)

        with patch.object(client._client, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": {
                    "type": "invalid_request_error",
                    "message": "Invalid model specified",
                }
            }
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Bad Request", request=Mock(), response=mock_response
            )
            mock_request.return_value = mock_response

            with pytest.raises(InvalidRequestError, match="Invalid model specified"):
                await client.chat_completion(
                    model="invalid-model",
                    messages=[{"role": "user", "content": "test"}],
                )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_network_error_handling(self, mock_api_key):
        """Test network error handling."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)

        with patch.object(client._client, "request") as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection failed")

            with pytest.raises(OpenRouterError, match="Network error"):
                await client.list_models()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_client_cleanup(self, mock_api_key):
        """Test client cleanup and context manager."""
        client = OpenRouterClient(api_key=mock_api_key)

        async with client:
            pass

        assert client._client.is_closed

    @pytest.mark.unit
    def test_validate_messages(self, mock_api_key):
        """Test message validation."""
        client = OpenRouterClient(api_key=mock_api_key)

        # Valid messages
        valid_messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
        ]
        client._validate_messages(valid_messages)  # Should not raise

        # Invalid messages - missing role
        with pytest.raises(ValueError, match="Message must have 'role' and 'content'"):
            client._validate_messages([{"content": "Hello!"}])

        # Invalid messages - invalid role
        with pytest.raises(ValueError, match="Invalid role"):
            client._validate_messages([{"role": "invalid", "content": "Hello!"}])

        # Empty messages
        with pytest.raises(ValueError, match="Messages cannot be empty"):
            client._validate_messages([])

    @pytest.mark.unit
    def test_validate_model(self, mock_api_key):
        """Test model validation."""
        client = OpenRouterClient(api_key=mock_api_key)

        # Valid model
        client._validate_model("openai/gpt-4")  # Should not raise

        # Invalid model - empty
        with pytest.raises(ValueError, match="Model cannot be empty"):
            client._validate_model("")

        # Invalid model - None
        with pytest.raises(ValueError, match="Model cannot be empty"):
            client._validate_model(None)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_model_pricing_marks_fallback_metadata_on_cache_failure(self, mock_api_key):
        """Test pricing metadata when cache fetch fails."""
        client = OpenRouterClient(api_key=mock_api_key)
        assert client._model_cache is not None

        with patch.object(
            client._model_cache,
            "get_model_info",
            new=AsyncMock(side_effect=Exception("cache unavailable")),
        ):
            pricing = await client.get_model_pricing("openai/gpt-4")

        assert pricing["prompt"] == 0.00002
        assert pricing["completion"] == 0.00002
        assert pricing["_meta"]["fallback_used"] is True
        assert pricing["_meta"]["pricing_available"] is False
        assert pricing["_meta"]["source"] == "fallback"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_model_pricing_preserves_zero_price_with_api_metadata(self, mock_api_key):
        """Test zero pricing is preserved when pricing data exists."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)

        with patch.object(
            client,
            "get_model_info",
            new=AsyncMock(return_value={"pricing": {"prompt": 0.0, "completion": 0.0}}),
        ):
            pricing = await client.get_model_pricing("openai/gpt-4")

        assert pricing["prompt"] == 0.0
        assert pricing["completion"] == 0.0
        assert pricing["_meta"]["fallback_used"] is False
        assert pricing["_meta"]["pricing_available"] is True
        assert pricing["_meta"]["source"] == "api"
