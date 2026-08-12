import json
from unittest.mock import AsyncMock, Mock

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
@pytest.mark.parametrize("async_json", [False, True])
async def test_extract_http_error_message_preserves_json_message_identity(async_json):
    message = "message-identity-marker"
    json_result = {"error": {"message": message}}
    response = Mock()
    response.json = (
        AsyncMock(return_value=json_result)
        if async_json
        else Mock(return_value=json_result)
    )

    result = await openrouter._extract_http_error_message(response)

    assert result is message
    response.json.assert_called_once_with()


@pytest.mark.asyncio
async def test_extract_http_error_message_sanitizes_parse_failure(monkeypatch):
    secret = "secret-response-body"
    response = Mock(status_code=503, text=secret)
    response.json.side_effect = json.JSONDecodeError("invalid", secret, 0)
    sanitize = Mock(return_value="<sanitized>")
    monkeypatch.setattr(
        openrouter.SensitiveDataSanitizer,
        "truncate_content",
        sanitize,
    )

    result = await openrouter._extract_http_error_message(response)

    assert result == "HTTP 503: <sanitized>"
    assert secret not in result
    sanitize.assert_called_once_with(secret, max_length=100)


@pytest.mark.asyncio
async def test_extract_http_error_message_uses_empty_body_fallback(monkeypatch):
    response = Mock(status_code=500, text="")
    response.json.side_effect = json.JSONDecodeError("invalid", "", 0)
    sanitize = Mock(side_effect=AssertionError("sanitizer must not run"))
    monkeypatch.setattr(
        openrouter.SensitiveDataSanitizer,
        "truncate_content",
        sanitize,
    )

    assert (
        await openrouter._extract_http_error_message(response)
        == "HTTP 500: No response body"
    )
    sanitize.assert_not_called()


@pytest.mark.asyncio
async def test_extract_http_error_message_does_not_swallow_payload_attribute_error(
    monkeypatch,
):
    expected_error = AttributeError("malformed payload")

    class Payload:
        def get(self, *_args, **_kwargs):
            raise expected_error

    response = Mock()
    response.json.return_value = Payload()
    sanitize = Mock()
    monkeypatch.setattr(
        openrouter.SensitiveDataSanitizer,
        "truncate_content",
        sanitize,
    )

    with pytest.raises(AttributeError) as exc_info:
        await openrouter._extract_http_error_message(response)

    assert exc_info.value is expected_error
    sanitize.assert_not_called()


@pytest.mark.asyncio
async def test_extract_http_error_message_propagates_sanitizer_failure(monkeypatch):
    expected_error = RuntimeError("sanitizer failed")
    response = Mock(status_code=500, text="body")
    response.json.side_effect = json.JSONDecodeError("invalid", "body", 0)
    monkeypatch.setattr(
        openrouter.SensitiveDataSanitizer,
        "truncate_content",
        Mock(side_effect=expected_error),
    )

    with pytest.raises(RuntimeError) as exc_info:
        await openrouter._extract_http_error_message(response)

    assert exc_info.value is expected_error


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
