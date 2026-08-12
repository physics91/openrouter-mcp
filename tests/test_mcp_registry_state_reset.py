import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.openrouter_mcp import mcp_registry as registry

pytestmark = pytest.mark.unit


def test_reset_shared_client_state_clears_all_singleton_globals(monkeypatch):
    monkeypatch.setattr(registry, "_client_instance", object())
    monkeypatch.setattr(registry, "_client_initialized", True)
    monkeypatch.setattr(registry, "_client_loop", object())

    registry._reset_shared_client_state()

    assert registry._client_instance is None
    assert registry._client_initialized is False
    assert registry._client_loop is None


@pytest.mark.asyncio
async def test_stale_cleanup_cancellation_uses_shared_state_reset(monkeypatch):
    current_loop = asyncio.get_running_loop()
    old_client = SimpleNamespace(
        api_key="old-key",
        _client=SimpleNamespace(is_closed=False),
    )
    error = asyncio.CancelledError()
    monkeypatch.setenv("OPENROUTER_API_KEY", "new-key")
    monkeypatch.setattr(registry, "_client_instance", old_client)
    monkeypatch.setattr(registry, "_client_initialized", True)
    monkeypatch.setattr(registry, "_client_loop", current_loop)
    monkeypatch.setattr(registry, "_client_lock", asyncio.Lock())

    with patch.object(
        registry,
        "_cleanup_stale_shared_client",
        AsyncMock(side_effect=error),
    ), patch.object(
        registry,
        "_reset_shared_client_state",
        wraps=registry._reset_shared_client_state,
    ) as reset:
        with pytest.raises(asyncio.CancelledError) as raised:
            await registry.get_shared_client()

    assert raised.value is error
    reset.assert_called_once_with()
    assert registry._client_instance is None
    assert registry._client_initialized is False
    assert registry._client_loop is None


@pytest.mark.asyncio
async def test_shutdown_cleanup_failure_uses_shared_state_reset(monkeypatch):
    error = RuntimeError("cleanup failed")
    client = MagicMock()
    client._client.is_closed = False
    client.__aexit__ = AsyncMock(side_effect=error)
    monkeypatch.setattr(registry, "_client_instance", client)
    monkeypatch.setattr(registry, "_client_initialized", True)
    monkeypatch.setattr(registry, "_client_loop", asyncio.get_running_loop())

    with patch.object(
        registry,
        "_reset_shared_client_state",
        wraps=registry._reset_shared_client_state,
    ) as reset, patch.object(registry.logger, "error") as log:
        await registry.cleanup_shared_client()

    reset.assert_called_once_with()
    log.assert_called_once_with("Error during client cleanup: cleanup failed")
    assert registry._client_instance is None
    assert registry._client_initialized is False
    assert registry._client_loop is None


@pytest.mark.asyncio
async def test_shutdown_cleanup_cancellation_uses_shared_state_reset(monkeypatch):
    current_loop = asyncio.get_running_loop()
    error = asyncio.CancelledError("stop cleanup")
    client = MagicMock()
    client._client.is_closed = False
    cleanup = AsyncMock(side_effect=error)
    monkeypatch.setattr(registry, "_client_instance", client)
    monkeypatch.setattr(registry, "_client_initialized", True)
    monkeypatch.setattr(registry, "_client_loop", current_loop)

    with patch.object(registry, "_cleanup_stale_shared_client", cleanup):
        with pytest.raises(asyncio.CancelledError) as raised:
            await registry.cleanup_shared_client()

    assert raised.value is error
    cleanup.assert_awaited_once_with(
        client,
        loop_closed=False,
        client_closed=False,
        owner_loop=current_loop,
        failure_context="client cleanup",
    )
    assert registry._client_instance is None
    assert registry._client_initialized is False
    assert registry._client_loop is None
