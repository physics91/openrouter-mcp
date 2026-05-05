import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import httpx
import pytest

from tests.fixtures.mock_responses import ResponseFactory, create_mock_response

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
    return ResponseFactory.models_list()


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
            "choices": [{"index": 0, "delta": {}, "logprobs": None, "finish_reason": "stop"}],
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


@pytest.fixture
def create_response():
    """Factory fixture for creating mock responses."""
    return create_mock_response


@pytest.fixture(autouse=True)
def isolate_default_cache_files(tmp_path, monkeypatch):
    """Keep tests from mutating the developer's real cache files."""
    from src.openrouter_mcp.config.constants import CacheConfig, FreeChatConfig

    monkeypatch.setattr(
        CacheConfig,
        "MODEL_CACHE_FILE",
        str(tmp_path / "openrouter_model_cache.json"),
    )
    monkeypatch.setattr(
        FreeChatConfig,
        "METRICS_CACHE_FILE",
        str(tmp_path / "free_metrics.json"),
    )
