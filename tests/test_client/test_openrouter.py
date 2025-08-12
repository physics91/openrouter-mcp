import os
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.openrouter_mcp.client.openrouter import (
    OpenRouterClient,
    OpenRouterError,
    AuthenticationError,
    RateLimitError,
    InvalidRequestError,
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
            http_referer="https://test.com"
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
            api_key=mock_api_key,
            app_name="test-app",
            http_referer="https://test.com"
        )
        
        headers = client._get_headers()
        
        assert headers["Authorization"] == f"Bearer {mock_api_key}"
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Title"] == "test-app"
        assert headers["HTTP-Referer"] == "https://test.com"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_models_success(
        self, mock_api_key, mock_models_response, create_response
    ):
        """Test successful models listing."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_models_response
            
            models = await client.list_models(enhance_info=False)
            
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
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_models_response
            
            models = await client.list_models(filter_by="openai")
            
            mock_request.assert_called_once_with(
                "GET", "/models", params={"filter": "openai"}
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_model_info_success(
        self, mock_api_key, mock_models_response
    ):
        """Test successful model info retrieval."""
        client = OpenRouterClient(api_key=mock_api_key)
        model_data = mock_models_response["data"][0]
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = model_data
            
            model_info = await client.get_model_info("openai/gpt-4")
            
            assert model_info["id"] == "openai/gpt-4"
            assert model_info["name"] == "GPT-4"
            mock_request.assert_called_once_with("GET", "/models/openai/gpt-4")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_completion_success(
        self, mock_api_key, mock_chat_response
    ):
        """Test successful chat completion."""
        client = OpenRouterClient(api_key=mock_api_key)
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_chat_response
            
            response = await client.chat_completion(
                model="openai/gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=100
            )
            
            assert response["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
            assert response["usage"]["total_tokens"] == 18
            
            expected_payload = {
                "model": "openai/gpt-4",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 100,
                "stream": False
            }
            mock_request.assert_called_once_with(
                "POST", "/chat/completions", json=expected_payload
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_chat_completion_success(
        self, mock_api_key, mock_stream_response
    ):
        """Test successful streaming chat completion."""
        client = OpenRouterClient(api_key=mock_api_key)
        
        messages = [{"role": "user", "content": "Hello!"}]
        
        with patch.object(client, '_stream_request') as mock_stream:
            async def mock_stream_gen():
                for chunk in mock_stream_response:
                    yield chunk
            
            mock_stream.return_value = mock_stream_gen()
            
            chunks = []
            async for chunk in client.stream_chat_completion(
                model="openai/gpt-4",
                messages=messages
            ):
                chunks.append(chunk)
            
            assert len(chunks) == 3
            assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
            assert chunks[2]["usage"]["total_tokens"] == 18

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_track_usage_success(self, mock_api_key):
        """Test successful usage tracking."""
        client = OpenRouterClient(api_key=mock_api_key)
        
        usage_data = {
            "total_cost": 0.00054,
            "total_tokens": 18,
            "requests": 1,
            "models": ["openai/gpt-4"]
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = usage_data
            
            usage = await client.track_usage(
                start_date="2024-01-01",
                end_date="2024-01-31"
            )
            
            assert usage["total_cost"] == 0.00054
            assert usage["total_tokens"] == 18
            
            expected_params = {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            }
            mock_request.assert_called_once_with(
                "GET", "/generation", params=expected_params
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authentication_error(self, mock_api_key, mock_error_response):
        """Test authentication error handling."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
        
        with patch.object(client._client, 'request') as mock_request:
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
        
        with patch.object(client._client, 'request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.json.return_value = {
                "error": {
                    "type": "rate_limit_exceeded",
                    "message": "Rate limit exceeded"
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
        
        with patch.object(client._client, 'request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": {
                    "type": "invalid_request_error",
                    "message": "Invalid model specified"
                }
            }
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Bad Request", request=Mock(), response=mock_response
            )
            mock_request.return_value = mock_response
            
            with pytest.raises(InvalidRequestError, match="Invalid model specified"):
                await client.chat_completion(
                    model="invalid-model",
                    messages=[{"role": "user", "content": "test"}]
                )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_network_error_handling(self, mock_api_key):
        """Test network error handling."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
        
        with patch.object(client._client, 'request') as mock_request:
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
            {"role": "user", "content": "Hello!"}
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