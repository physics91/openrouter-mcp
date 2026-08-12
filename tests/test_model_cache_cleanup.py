import asyncio
import concurrent.futures
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.client.openrouter import OpenRouterClient
from src.openrouter_mcp.models.cache import ModelCache

pytestmark = pytest.mark.unit


class RecordingExecutor:
    def __init__(self, events, error=None):
        self.events = events
        self.error = error
        self.calls = 0

    def shutdown(self, wait=True):
        self.calls += 1
        self.events.append(("executor", wait))
        if self.error is not None:
            raise self.error


def _bare_cache(executor, transport=None):
    cache = object.__new__(ModelCache)
    cache._cache_lock = threading.RLock()
    cache._executor = executor
    cache._shutdown_started = False
    cache._shutdown_complete = threading.Event()
    cache._shutdown_failure = None
    cache._transport = transport
    cache._inflight_refresh = None
    return cache


@pytest.mark.asyncio
async def test_model_cache_aclose_cancels_refresh_and_closes_resources_once():
    events = []
    executor = RecordingExecutor(events)

    async def close_transport():
        events.append(("transport", True))

    transport = SimpleNamespace(aclose=AsyncMock(side_effect=close_transport))
    cache = _bare_cache(executor, transport)
    refresh_started = asyncio.Event()

    async def refresh():
        refresh_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            events.append(("refresh", "finalized"))

    refresh_task = asyncio.create_task(refresh())
    cache._inflight_refresh = refresh_task
    await refresh_started.wait()

    await cache.aclose()
    await cache.aclose()

    assert refresh_task.cancelled()
    assert cache._inflight_refresh is None
    assert events == [
        ("refresh", "finalized"),
        ("executor", True),
        ("transport", True),
    ]
    assert executor.calls == 1
    transport.aclose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_model_cache_aclose_retrieves_done_refresh_exception():
    events = []
    cache = _bare_cache(RecordingExecutor(events))

    class TrackingFuture(asyncio.Future):
        retrieved = False

        def exception(self):
            self.retrieved = True
            return super().exception()

    refresh = TrackingFuture()
    refresh.set_exception(RuntimeError("refresh failed"))
    cache._inflight_refresh = refresh

    await cache.aclose()

    assert refresh.retrieved is True
    assert cache._inflight_refresh is None


@pytest.mark.asyncio
async def test_model_cache_aclose_preserves_first_failure_and_continues_cleanup():
    events = []
    executor_error = RuntimeError("executor shutdown failed")
    executor = RecordingExecutor(events, error=executor_error)

    async def close_transport():
        events.append(("transport", True))

    transport = SimpleNamespace(aclose=AsyncMock(side_effect=close_transport))
    cache = _bare_cache(executor, transport)

    with pytest.raises(RuntimeError) as raised:
        await cache.aclose()

    assert raised.value is executor_error
    assert events == [("executor", True), ("transport", True)]
    transport.aclose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_model_cache_aclose_cancellation_waits_for_executor_before_transport():
    events = []
    shutdown_started = threading.Event()
    release_shutdown = threading.Event()

    class GatedExecutor:
        def shutdown(self, wait=True):
            shutdown_started.set()
            release_shutdown.wait(timeout=1)
            events.append(("executor", "finished"))

    async def close_transport():
        events.append(("transport", True))

    transport = SimpleNamespace(aclose=AsyncMock(side_effect=close_transport))
    cache = _bare_cache(GatedExecutor(), transport)
    close_task = asyncio.create_task(cache.aclose())
    await asyncio.to_thread(shutdown_started.wait, 1)

    close_task.cancel("stop cleanup")
    await asyncio.sleep(0)

    assert not close_task.done()
    transport.aclose.assert_not_awaited()

    release_shutdown.set()
    with pytest.raises(asyncio.CancelledError) as raised:
        await close_task

    assert raised.value.args == ("stop cleanup",)
    assert events == [("executor", "finished"), ("transport", True)]


@pytest.mark.asyncio
async def test_sync_and_async_cache_shutdown_claim_executor_once():
    shutdown_started = threading.Event()
    release_shutdown = threading.Event()

    class GatedExecutor:
        calls = 0

        def shutdown(self, wait=True):
            self.calls += 1
            shutdown_started.set()
            release_shutdown.wait(timeout=1)

    executor = GatedExecutor()
    cache = _bare_cache(executor)
    sync_shutdown = asyncio.create_task(asyncio.to_thread(cache.shutdown))
    await asyncio.to_thread(shutdown_started.wait, 1)
    async_shutdown = asyncio.create_task(cache.aclose())
    await asyncio.sleep(0)

    assert not async_shutdown.done()

    release_shutdown.set()
    await asyncio.gather(sync_shutdown, async_shutdown)

    assert executor.calls == 1


@pytest.mark.asyncio
async def test_sync_shutdown_does_not_block_running_loop_waiting_for_async_owner():
    cache = _bare_cache(RecordingExecutor([]))
    cache._shutdown_started = True

    class UnexpectedBlockingWait:
        def is_set(self):
            return False

        def wait(self):
            raise AssertionError("shutdown blocked the running event loop")

    cache._shutdown_complete = UnexpectedBlockingWait()

    with pytest.raises(RuntimeError, match="await cache.aclose"):
        cache.shutdown()


@pytest.mark.asyncio
async def test_model_cache_aclose_reaps_refresh_on_its_owner_loop():
    owner_loop = asyncio.new_event_loop()
    refresh_ready = concurrent.futures.Future()
    refresh_started = threading.Event()
    refresh_finalized = threading.Event()
    finalizer_thread = concurrent.futures.Future()

    async def refresh():
        refresh_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            finalizer_thread.set_result(threading.get_ident())
            refresh_finalized.set()

    def run_owner_loop():
        asyncio.set_event_loop(owner_loop)
        refresh_task = owner_loop.create_task(refresh())
        refresh_ready.set_result(refresh_task)
        owner_loop.run_forever()
        owner_loop.close()

    owner_thread = threading.Thread(target=run_owner_loop)
    owner_thread.start()

    try:
        refresh_task = await asyncio.to_thread(refresh_ready.result, 1)
        assert await asyncio.to_thread(refresh_started.wait, 1)
        cache = _bare_cache(RecordingExecutor([]))
        cache._inflight_refresh = refresh_task

        await cache.aclose()

        assert refresh_task.cancelled()
        assert await asyncio.to_thread(refresh_finalized.wait, 1)
        assert finalizer_thread.result(timeout=1) == owner_thread.ident
    finally:
        owner_loop.call_soon_threadsafe(owner_loop.stop)
        await asyncio.to_thread(owner_thread.join, 1)
        assert not owner_thread.is_alive()


@pytest.mark.asyncio
async def test_model_cache_aclose_reports_stopped_foreign_refresh_loop():
    owner_loop = asyncio.new_event_loop()

    async def refresh():
        await asyncio.Event().wait()

    refresh_task = owner_loop.create_task(refresh())
    events = []
    cache = _bare_cache(RecordingExecutor(events))
    cache._inflight_refresh = refresh_task
    refresh_task.add_done_callback(cache._clear_inflight_refresh)

    def resume_owner_loop():
        asyncio.set_event_loop(owner_loop)
        owner_loop.call_later(0.1, owner_loop.stop)
        owner_loop.run_forever()
        return refresh_task.cancelled(), cache._inflight_refresh is None

    def close_owner_loop():
        asyncio.set_event_loop(owner_loop)
        if not refresh_task.done():
            refresh_task.cancel()
            owner_loop.run_until_complete(
                asyncio.gather(refresh_task, return_exceptions=True)
            )
        owner_loop.close()

    try:
        with pytest.raises(RuntimeError, match="cancellation was queued"):
            await cache.aclose()

        assert events == [("executor", True)]
        assert cache._inflight_refresh is refresh_task

        cleanup_state = await asyncio.to_thread(resume_owner_loop)
        assert cleanup_state == (True, True)
    finally:
        await asyncio.to_thread(close_owner_loop)


@pytest.mark.asyncio
async def test_openrouter_close_closes_primary_after_cache_failure():
    events = []
    cache_error = RuntimeError("cache close failed")

    async def close_cache():
        events.append("cache")
        raise cache_error

    async def close_primary():
        events.append("primary")

    client = object.__new__(OpenRouterClient)
    client._model_cache = SimpleNamespace(aclose=AsyncMock(side_effect=close_cache))
    client._client = SimpleNamespace(aclose=AsyncMock(side_effect=close_primary))

    with pytest.raises(RuntimeError) as raised:
        await client.close()

    assert raised.value is cache_error
    assert events == ["cache", "primary"]


@pytest.mark.asyncio
async def test_openrouter_close_keeps_primary_failure_priority():
    events = []
    cache_error = RuntimeError("cache close failed")
    primary_error = RuntimeError("primary close failed")

    async def close_cache():
        events.append("cache")
        raise cache_error

    async def close_primary():
        events.append("primary")
        raise primary_error

    client = object.__new__(OpenRouterClient)
    client._model_cache = SimpleNamespace(aclose=AsyncMock(side_effect=close_cache))
    client._client = SimpleNamespace(aclose=AsyncMock(side_effect=close_primary))

    with pytest.raises(RuntimeError) as raised:
        await client.close()

    assert raised.value is primary_error
    assert events == ["cache", "primary"]
