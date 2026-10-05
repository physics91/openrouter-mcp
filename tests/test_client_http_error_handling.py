from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from src.openrouter_mcp.client import openrouter
from src.openrouter_mcp.client.openrouter import (
    AuthenticationError,
    InvalidRequestError,
    OpenRouterClient,
    OpenRouterError,
    RateLimitError,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code, reason",
    [
        (400, "Bad Request"),
        (401, "Unauthorized"),
        (429, "Too Many Requests"),
        (500, "Internal Server Error"),
        (599, "Upstream request failed"),
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        b'{"error":{"message":"private-user-content"}}',
        b"<html>private-user-content</html>",
        b"null",
        b"",
    ],
)
async def test_http_error_body_never_becomes_public_message(status_code, reason, body):
    response = httpx.Response(status_code, content=body)
    result = await openrouter._extract_http_error_message(response)
    assert result == f"HTTP {status_code}: {reason}"
    assert "private-user-content" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (401, AuthenticationError),
        (400, InvalidRequestError),
        (500, OpenRouterError),
    ],
)
async def test_handle_http_error_delegates_message_to_status_exception(
    monkeypatch,
    mock_api_key,
    status_code,
    error_type,
):
    client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
    response = Mock(status_code=status_code, headers={})
    extract = AsyncMock(return_value="safe message")
    monkeypatch.setattr(openrouter, "_extract_http_error_message", extract)

    with pytest.raises(error_type, match="safe message"):
        await client._handle_http_error(response)

    extract.assert_awaited_once_with(response)
    await client.close()


@pytest.mark.asyncio
async def test_handle_http_error_preserves_retry_after(monkeypatch, mock_api_key):
    client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
    response = Mock(status_code=429, headers={"Retry-After": "1.5"})
    extract = AsyncMock(return_value="slow down")
    monkeypatch.setattr(openrouter, "_extract_http_error_message", extract)

    with pytest.raises(RateLimitError, match="slow down") as exc_info:
        await client._handle_http_error(response)

    assert exc_info.value.retry_after == 1.5
    extract.assert_awaited_once_with(response)
    await client.close()
