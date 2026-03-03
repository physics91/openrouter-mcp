import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from httpx import Response

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_api_key() -> str:
    """Mock API key for testing."""
    return "sk-or-test-key-123456789"


@pytest.fixture
def mock_openrouter_base_url() -> str:
    """Mock base URL for OpenRouter API."""
    return "https://openrouter.ai/api/v1"


@pytest.fixture
def mock_env_vars(mock_api_key: str, mock_openrouter_base_url: str, monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("OPENROUTER_API_KEY", mock_api_key)
    monkeypatch.setenv("OPENROUTER_BASE_URL", mock_openrouter_base_url)
    monkeypatch.setenv("OPENROUTER_APP_NAME", "test-app")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://test.com")


@pytest.fixture
def mock_models_response() -> Dict[str, Any]:
    """Mock response for models endpoint."""
    return {
        "data": [
            {
                "id": "openai/gpt-4",
                "name": "GPT-4",
                "description": "OpenAI's GPT-4 model",
                "pricing": {"prompt": "0.00003", "completion": "0.00006"},
                "context_length": 8192,
                "architecture": {
                    "modality": "text",
                    "tokenizer": "cl100k_base",
                    "instruct_type": None,
                },
                "top_provider": {
                    "context_length": 8192,
                    "max_completion_tokens": 4096,
                    "is_moderated": True,
                },
                "per_request_limits": None,
            },
            {
                "id": "anthropic/claude-3-haiku",
                "name": "Claude 3 Haiku",
                "description": "Anthropic's fastest model",
                "pricing": {"prompt": "0.00025", "completion": "0.00125"},
                "context_length": 200000,
                "architecture": {
                    "modality": "text",
                    "tokenizer": "claude",
                    "instruct_type": None,
                },
                "top_provider": {
                    "context_length": 200000,
                    "max_completion_tokens": 4096,
                    "is_moderated": False,
                },
                "per_request_limits": None,
            },
        ]
    }


@pytest.fixture
def mock_chat_response() -> Dict[str, Any]:
    """Mock response for chat completion endpoint."""
    return {
        "id": "gen-1234567890",
        "provider": "OpenAI",
        "model": "openai/gpt-4",
        "object": "chat.completion",
        "created": 1692901234,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?",
                },
                "logprobs": None,
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    }


@pytest.fixture
def mock_stream_response() -> List[Dict[str, Any]]:
    """Mock response for streaming chat completion."""
    return [
        {
            "id": "gen-1234567890",
            "provider": "OpenAI",
            "model": "openai/gpt-4",
            "object": "chat.completion.chunk",
            "created": 1692901234,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Hello"},
                    "logprobs": None,
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "gen-1234567890",
            "provider": "OpenAI",
            "model": "openai/gpt-4",
            "object": "chat.completion.chunk",
            "created": 1692901234,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": "! How can I help you today?"},
                    "logprobs": None,
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "gen-1234567890",
            "provider": "OpenAI",
            "model": "openai/gpt-4",
            "object": "chat.completion.chunk",
            "created": 1692901234,
            "choices": [
                {"index": 0, "delta": {}, "logprobs": None, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        },
    ]


@pytest.fixture
def mock_error_response() -> Dict[str, Any]:
    """Mock error response from OpenRouter API."""
    return {
        "error": {
            "type": "invalid_request_error",
            "code": "invalid_api_key",
            "message": "Invalid API key provided",
        }
    }


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for testing."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


def create_mock_response(
    status_code: int = 200,
    json_data: Dict[str, Any] = None,
    text_data: str = None,
    headers: Dict[str, str] = None,
) -> Mock:
    """Create a mock HTTP response."""
    response = Mock(spec=Response)
    response.status_code = status_code
    response.headers = headers or {"content-type": "application/json"}

    if json_data is not None:
        response.json.return_value = json_data

    if text_data is not None:
        response.text = text_data

    response.raise_for_status = Mock()
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "HTTP Error", request=Mock(), response=response
        )

    return response


@pytest.fixture
def create_response():
    """Factory fixture for creating mock responses."""
    return create_mock_response
