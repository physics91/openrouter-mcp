import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.openrouter_mcp import mcp_registry as registry

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_cleanup_stale_shared_client_runs_on_foreign_owner_loop():
    owner_loop = asyncio.new_event_loop()
    owner_started = threading.Event()
    cleanup_loops = []

    class LoopBoundClient:
        async def __aexit__(self, exc_type, exc, traceback):
            cleanup_loops.append(asyncio.get_running_loop())

    def run_owner_loop():
        asyncio.set_event_loop(owner_loop)
        owner_started.set()
        owner_loop.run_forever()
        owner_loop.close()

    owner_thread = threading.Thread(target=run_owner_loop)
    owner_thread.start()

    try:
        assert await asyncio.to_thread(owner_started.wait, 1)
        await registry._cleanup_stale_shared_client(
            LoopBoundClient(),
            loop_closed=False,
            client_closed=False,
            owner_loop=owner_loop,
        )

        assert cleanup_loops == [owner_loop]
    finally:
        owner_loop.call_soon_threadsafe(owner_loop.stop)
        await asyncio.to_thread(owner_thread.join, 1)
        assert not owner_thread.is_alive()


@pytest.mark.asyncio
async def test_cleanup_stale_shared_client_rejects_stopped_owner_loop():
    owner_loop = asyncio.new_event_loop()
    owner_stopped = threading.Event()
    resume_owner = threading.Event()
    cleanup_threads = []

    class LoopBoundClient:
        async def __aexit__(self, exc_type, exc, traceback):
            assert asyncio.get_running_loop() is owner_loop
            cleanup_threads.append(threading.get_ident())

    def run_owner_loop():
        asyncio.set_event_loop(owner_loop)
        owner_loop.call_soon(owner_loop.stop)
        owner_loop.run_forever()
        owner_stopped.set()
        resume_owner.wait(timeout=1)
        owner_loop.run_forever()
        owner_loop.close()

    owner_thread = threading.Thread(target=run_owner_loop)
    owner_thread.start()

    try:
        assert await asyncio.to_thread(owner_stopped.wait, 1)
        with pytest.raises(registry.StaleClientCleanupDeferred):
            await registry._cleanup_stale_shared_client(
                LoopBoundClient(),
                loop_closed=False,
                client_closed=False,
                owner_loop=owner_loop,
            )

        assert cleanup_threads == []
    finally:
        resume_owner.set()
        owner_loop.call_soon_threadsafe(owner_loop.stop)
        await asyncio.to_thread(owner_thread.join, 1)
        assert not owner_thread.is_alive()


@pytest.mark.asyncio
async def test_get_shared_client_preserves_state_when_owner_loop_is_stopped(
    monkeypatch,
):
    owner_loop = asyncio.new_event_loop()
    old_client = SimpleNamespace(
        api_key="old-key",
        _client=SimpleNamespace(is_closed=False),
    )
    initialize = AsyncMock()
    monkeypatch.setenv("OPENROUTER_API_KEY", "new-key")
    monkeypatch.setattr(registry, "_client_instance", old_client)
    monkeypatch.setattr(registry, "_client_initialized", True)
    monkeypatch.setattr(registry, "_client_loop", owner_loop)
    monkeypatch.setattr(registry, "_client_lock", asyncio.Lock())

    try:
        with patch.object(registry, "_initialize_shared_client", initialize):
            with pytest.raises(registry.StaleClientCleanupDeferred):
                await registry.get_shared_client()

        assert registry._client_instance is old_client
        assert registry._client_initialized is True
        assert registry._client_loop is owner_loop
        initialize.assert_not_awaited()
    finally:
        owner_loop.close()


@pytest.mark.asyncio
async def test_cleanup_shared_client_runs_on_foreign_owner_loop(monkeypatch):
    owner_loop = asyncio.new_event_loop()
    owner_started = threading.Event()
    cleanup_done = threading.Event()
    cleanup_threads = []

    class LoopBoundClient:
        api_key = "test-key"
        _client = SimpleNamespace(is_closed=False)

        async def __aexit__(self, exc_type, exc, traceback):
            assert asyncio.get_running_loop() is owner_loop
            cleanup_threads.append(threading.get_ident())
            cleanup_done.set()

    def run_owner_loop():
        asyncio.set_event_loop(owner_loop)
        owner_started.set()
        owner_loop.run_forever()
        owner_loop.close()

    owner_thread = threading.Thread(target=run_owner_loop)
    owner_thread.start()
    client = LoopBoundClient()
    monkeypatch.setattr(registry, "_client_instance", client)
    monkeypatch.setattr(registry, "_client_initialized", True)
    monkeypatch.setattr(registry, "_client_loop", owner_loop)

    try:
        assert await asyncio.to_thread(owner_started.wait, 1)
        await registry.cleanup_shared_client()

        assert await asyncio.to_thread(cleanup_done.wait, 1)
        assert cleanup_threads == [owner_thread.ident]
        assert registry._client_instance is None
    finally:
        owner_loop.call_soon_threadsafe(owner_loop.stop)
        await asyncio.to_thread(owner_thread.join, 1)
        assert not owner_thread.is_alive()


@pytest.mark.asyncio
async def test_cleanup_shared_client_preserves_stopped_owner_state(monkeypatch):
    owner_loop = asyncio.new_event_loop()
    client = MagicMock()
    client._client.is_closed = False
    client.__aexit__ = AsyncMock()
    monkeypatch.setattr(registry, "_client_instance", client)
    monkeypatch.setattr(registry, "_client_initialized", True)
    monkeypatch.setattr(registry, "_client_loop", owner_loop)

    try:
        with pytest.raises(registry.StaleClientCleanupDeferred):
            await registry.cleanup_shared_client()

        assert registry._client_instance is client
        assert registry._client_initialized is True
        assert registry._client_loop is owner_loop
        client.__aexit__.assert_not_awaited()
    finally:
        owner_loop.close()


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
        owner_loop=current_loop,
    )
    assert registry._client_instance is None
    assert registry._client_initialized is False
    assert registry._client_loop is None
