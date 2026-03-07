"""Reusable helpers for mocking httpx.AsyncClient in tests."""

from __future__ import annotations

from typing import Any, Dict, Tuple
from unittest.mock import AsyncMock, MagicMock


def setup_async_client_mock(
    mock_httpx_client: Any,
    json_payload: Dict[str, Any],
    *,
    capture_headers: bool = False,
) -> Tuple[MagicMock, MagicMock, Dict[str, str]]:
    """Configure a patched ``httpx.AsyncClient`` with a JSON response payload."""
    client = MagicMock()
    mock_httpx_client.return_value = client

    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    response = MagicMock()
    response.json.return_value = json_payload
    response.raise_for_status = MagicMock()

    captured_headers: Dict[str, str] = {}

    async def _mock_get(*args, **kwargs):
        if capture_headers:
            captured_headers.update(kwargs.get("headers", {}))
        return response

    client.get = AsyncMock(side_effect=_mock_get)
    return client, response, captured_headers


__all__ = ["setup_async_client_mock"]
