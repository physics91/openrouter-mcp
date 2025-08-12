import pytest
from unittest.mock import AsyncMock, patch, Mock
from typing import Any, Dict, List

from src.openrouter_mcp.handlers.chat import (
    chat_with_model,
    list_available_models,
    get_usage_stats,
    ChatCompletionRequest,
    ModelListRequest,
    UsageStatsRequest
)
from src.openrouter_mcp.client.openrouter import OpenRouterClient, OpenRouterError


class TestChatHandler:
    """Test cases for chat handler functions."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_with_model_success(self, mock_chat_response):
        """Test successful chat completion."""
        with patch('src.openrouter_mcp.handlers.chat.get_openrouter_client') as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.chat_completion.return_value = mock_chat_response
            mock_get_client.return_value = mock_client
            
            request = ChatCompletionRequest(
                model="openai/gpt-4",
                messages=[{"role": "user", "content": "Hello!"}],
                temperature=0.7,
                max_tokens=100
            )
            
            result = await chat_with_model.fn(request)
            
            assert result["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
            assert result["usage"]["total_tokens"] == 18
            
            mock_client.chat_completion.assert_called_once_with(
                model="openai/gpt-4",
                messages=[{"role": "user", "content": "Hello!"}],
                temperature=0.7,
                max_tokens=100,
                stream=False
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_with_model_streaming(self, mock_stream_response):
        """Test streaming chat completion."""
        with patch('src.openrouter_mcp.handlers.chat.get_openrouter_client') as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            
            async def mock_stream_gen():
                for chunk in mock_stream_response:
                    yield chunk
            
            mock_client.stream_chat_completion.return_value = mock_stream_gen()
            mock_get_client.return_value = mock_client
            
            request = ChatCompletionRequest(
                model="openai/gpt-4",
                messages=[{"role": "user", "content": "Hello!"}],
                stream=True
            )
            
            result = await chat_with_model.fn(request)
            
            # For streaming, result should be a list of chunks
            assert isinstance(result, list)
            assert len(result) == 3
            assert result[0]["choices"][0]["delta"]["content"] == "Hello"
            assert result[2]["usage"]["total_tokens"] == 18

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_with_model_validation_error(self):
        """Test chat completion with validation error."""
        with patch('src.openrouter_mcp.handlers.chat.get_openrouter_client') as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.chat_completion.side_effect = ValueError("Invalid model")
            mock_get_client.return_value = mock_client
            
            request = ChatCompletionRequest(
                model="",  # Invalid empty model
                messages=[{"role": "user", "content": "Hello!"}]
            )
            
            with pytest.raises(ValueError, match="Invalid model"):
                await chat_with_model.fn(request)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_with_model_api_error(self):
        """Test chat completion with API error."""
        with patch('src.openrouter_mcp.handlers.chat.get_openrouter_client') as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.chat_completion.side_effect = OpenRouterError("API error")
            mock_get_client.return_value = mock_client
            
            request = ChatCompletionRequest(
                model="openai/gpt-4",
                messages=[{"role": "user", "content": "Hello!"}]
            )
            
            with pytest.raises(OpenRouterError, match="API error"):
                await chat_with_model.fn(request)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_available_models_success(self, mock_models_response):
        """Test successful model listing."""
        with patch('src.openrouter_mcp.handlers.chat.get_openrouter_client') as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.list_models.return_value = mock_models_response["data"]
            mock_get_client.return_value = mock_client
            
            request = ModelListRequest()
            
            result = await list_available_models.fn(request)
            
            assert len(result) == 2
            assert result[0]["id"] == "openai/gpt-4"
            assert result[1]["id"] == "anthropic/claude-3-haiku"
            
            mock_client.list_models.assert_called_once_with(filter_by=None)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_available_models_with_filter(self, mock_models_response):
        """Test model listing with filter."""
        with patch('src.openrouter_mcp.handlers.chat.get_openrouter_client') as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            # Filter results to only include GPT models
            filtered_models = [model for model in mock_models_response["data"] if "gpt" in model["id"].lower()]
            mock_client.list_models.return_value = filtered_models
            mock_get_client.return_value = mock_client
            
            request = ModelListRequest(filter_by="gpt")
            
            result = await list_available_models.fn(request)
            
            assert len(result) == 1
            assert result[0]["id"] == "openai/gpt-4"
            
            mock_client.list_models.assert_called_once_with(filter_by="gpt")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_available_models_api_error(self):
        """Test model listing with API error."""
        with patch('src.openrouter_mcp.handlers.chat.get_openrouter_client') as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.list_models.side_effect = OpenRouterError("API error")
            mock_get_client.return_value = mock_client
            
            request = ModelListRequest()
            
            with pytest.raises(OpenRouterError, match="API error"):
                await list_available_models.fn(request)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_usage_stats_success(self):
        """Test successful usage stats retrieval."""
        usage_data = {
            "total_cost": 0.00054,
            "total_tokens": 18,
            "requests": 1,
            "models": ["openai/gpt-4"]
        }
        
        with patch('src.openrouter_mcp.handlers.chat.get_openrouter_client') as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.track_usage.return_value = usage_data
            mock_get_client.return_value = mock_client
            
            request = UsageStatsRequest(
                start_date="2024-01-01",
                end_date="2024-01-31"
            )
            
            result = await get_usage_stats.fn(request)
            
            assert result["total_cost"] == 0.00054
            assert result["total_tokens"] == 18
            assert result["requests"] == 1
            assert "openai/gpt-4" in result["models"]
            
            mock_client.track_usage.assert_called_once_with(
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_usage_stats_no_dates(self):
        """Test usage stats retrieval without date range."""
        usage_data = {
            "total_cost": 0.00054,
            "total_tokens": 18,
            "requests": 1,
            "models": ["openai/gpt-4"]
        }
        
        with patch('src.openrouter_mcp.handlers.chat.get_openrouter_client') as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.track_usage.return_value = usage_data
            mock_get_client.return_value = mock_client
            
            request = UsageStatsRequest()
            
            result = await get_usage_stats.fn(request)
            
            assert result["total_cost"] == 0.00054
            
            mock_client.track_usage.assert_called_once_with(
                start_date=None,
                end_date=None
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_usage_stats_api_error(self):
        """Test usage stats retrieval with API error."""
        with patch('src.openrouter_mcp.handlers.chat.get_openrouter_client') as mock_get_client:
            mock_client = AsyncMock(spec=OpenRouterClient)
            mock_client.track_usage.side_effect = OpenRouterError("API error")
            mock_get_client.return_value = mock_client
            
            request = UsageStatsRequest()
            
            with pytest.raises(OpenRouterError, match="API error"):
                await get_usage_stats.fn(request)

    @pytest.mark.unit
    def test_chat_completion_request_validation(self):
        """Test ChatCompletionRequest validation."""
        # Valid request
        request = ChatCompletionRequest(
            model="openai/gpt-4",
            messages=[{"role": "user", "content": "Hello!"}]
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
                {"role": "user", "content": "Hello!"}
            ],
            temperature=0.5,
            max_tokens=200,
            stream=True
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
        request_dated = UsageStatsRequest(
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        assert request_dated.start_date == "2024-01-01"
        assert request_dated.end_date == "2024-01-31"