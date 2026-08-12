import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.openrouter_mcp import mcp_registry as registry

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_cleanup_stale_shared_client_closes_open_client():
    client = MagicMock()
    client.__aexit__ = AsyncMock(return_value=None)

    await registry._cleanup_stale_shared_client(
        client,
        loop_closed=False,
        client_closed=False,
    )

    client.__aexit__.assert_awaited_once_with(None, None, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("loop_closed", "client_closed"),
    [(True, False), (False, True), (True, True)],
)
async def test_cleanup_stale_shared_client_skips_closed_resources(
    loop_closed,
    client_closed,
):
    client = MagicMock()
    client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(registry.logger, "info") as log:
        await registry._cleanup_stale_shared_client(
            client,
            loop_closed=loop_closed,
            client_closed=client_closed,
        )

    client.__aexit__.assert_not_awaited()
    log.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_stale_shared_client_logs_and_swallows_cleanup_failure():
    error = RuntimeError("cleanup failed")
    client = MagicMock()
    client.__aexit__ = AsyncMock(side_effect=error)

    with patch.object(registry.logger, "error") as log:
        await registry._cleanup_stale_shared_client(
            client,
            loop_closed=False,
            client_closed=False,
        )

    log.assert_called_once()


@pytest.mark.asyncio
async def test_get_shared_client_resets_stale_state_when_cleanup_is_cancelled(
    monkeypatch,
):
    current_loop = asyncio.get_running_loop()
    old_client = SimpleNamespace(
        api_key="old-key",
        _client=SimpleNamespace(is_closed=False),
    )
    error = asyncio.CancelledError()
    cleanup = AsyncMock(side_effect=error)
    monkeypatch.setenv("OPENROUTER_API_KEY", "new-key")
    monkeypatch.setattr(registry, "_client_instance", old_client)
    monkeypatch.setattr(registry, "_client_initialized", True)
    monkeypatch.setattr(registry, "_client_loop", current_loop)
    monkeypatch.setattr(registry, "_client_lock", asyncio.Lock())

    with patch.object(
        registry,
        "_cleanup_stale_shared_client",
        cleanup,
    ):
        with pytest.raises(asyncio.CancelledError) as raised:
            await registry.get_shared_client()

    assert raised.value is error
    cleanup.assert_awaited_once_with(
        old_client,
        loop_closed=False,
        client_closed=False,
    )
    assert registry._client_instance is None
    assert registry._client_initialized is False
    assert registry._client_loop is None
