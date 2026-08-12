import asyncio

import pytest

from src.openrouter_mcp.runtime_thrift.coalescer import RequestCoalescer


@pytest.mark.asyncio
async def test_failed_leader_clears_inflight_without_caching_and_allows_retry():
    coalescer = RequestCoalescer(time_fn=lambda: 100.0)
    attempts = 0

    async def fail_once():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await coalescer.run("key", fail_once, ttl_seconds=5)

    assert coalescer._inflight == {}
    assert coalescer._recent == {}

    async def succeed():
        nonlocal attempts
        attempts += 1
        return "recovered"

    assert await coalescer.run("key", succeed, ttl_seconds=0) == "recovered"
    assert attempts == 2
    assert coalescer._inflight == {}
    assert coalescer._recent == {}


@pytest.mark.asyncio
async def test_cancelled_leader_clears_inflight_without_caching_and_allows_retry():
    coalescer = RequestCoalescer(time_fn=lambda: 100.0)
    started = asyncio.Event()

    async def wait_forever():
        started.set()
        await asyncio.Event().wait()

    leader = asyncio.create_task(coalescer.run("key", wait_forever, ttl_seconds=5))
    await started.wait()
    leader.cancel()

    with pytest.raises(asyncio.CancelledError):
        await leader

    assert coalescer._inflight == {}
    assert coalescer._recent == {}

    async def succeed():
        return "recovered"

    assert await coalescer.run("key", succeed, ttl_seconds=0) == "recovered"


@pytest.mark.asyncio
async def test_successful_leader_atomically_removes_inflight_and_caches_result():
    now = [100.0]
    coalescer = RequestCoalescer(time_fn=lambda: now[0])
    result = object()

    async def succeed():
        return result

    assert await coalescer.run("key", succeed, ttl_seconds=5) is result
    assert coalescer._inflight == {}
    assert coalescer._recent["key"].value is result
    assert coalescer._recent["key"].expires_at == 105.0


@pytest.mark.asyncio
async def test_follower_joins_single_factory_and_leader_owns_cleanup():
    coalescer = RequestCoalescer(time_fn=lambda: 100.0)
    started = asyncio.Event()
    release = asyncio.Event()
    follower_joined = asyncio.Event()
    factory_calls = 0
    result = object()

    async def factory():
        nonlocal factory_calls
        factory_calls += 1
        started.set()
        await release.wait()
        return result

    leader = asyncio.create_task(coalescer.run("key", factory, ttl_seconds=5))
    await started.wait()
    follower = asyncio.create_task(
        coalescer.run(
            "key",
            factory,
            ttl_seconds=5,
            on_follower_join=follower_joined.set,
        )
    )
    await follower_joined.wait()
    release.set()

    leader_result, follower_result = await asyncio.gather(leader, follower)

    assert leader_result is result
    assert follower_result is result
    assert factory_calls == 1
    assert coalescer._inflight == {}
    assert coalescer._recent["key"].value is result


@pytest.mark.parametrize("ttl_seconds", [0, 5])
@pytest.mark.asyncio
async def test_cancelled_follower_does_not_cancel_shared_work_or_peers(ttl_seconds):
    coalescer = RequestCoalescer(time_fn=lambda: 100.0)
    started = asyncio.Event()
    release = asyncio.Event()
    cancelled_joined = asyncio.Event()
    survivor_joined = asyncio.Event()
    factory_calls = 0
    result = object()

    async def factory():
        nonlocal factory_calls
        factory_calls += 1
        started.set()
        await release.wait()
        return result

    leader = asyncio.create_task(coalescer.run("key", factory, ttl_seconds=ttl_seconds))
    await started.wait()
    cancelled_follower = asyncio.create_task(
        coalescer.run(
            "key",
            factory,
            ttl_seconds=ttl_seconds,
            on_follower_join=cancelled_joined.set,
        )
    )
    await cancelled_joined.wait()
    surviving_follower = asyncio.create_task(
        coalescer.run(
            "key",
            factory,
            ttl_seconds=ttl_seconds,
            on_follower_join=survivor_joined.set,
        )
    )
    await survivor_joined.wait()
    shared_task = coalescer._inflight["key"]

    try:
        cancelled_follower.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled_follower

        assert not shared_task.cancelled()
        assert not leader.done()
        assert not surviving_follower.done()

        release.set()
        leader_result, follower_result = await asyncio.gather(
            leader,
            surviving_follower,
        )

        assert leader_result is result
        assert follower_result is result
        assert factory_calls == 1
        assert coalescer._inflight == {}
        if ttl_seconds == 0:
            assert coalescer._recent == {}
        else:
            assert coalescer._recent["key"].value is result
            assert coalescer._recent["key"].expires_at == 105.0
    finally:
        release.set()
        await asyncio.gather(
            leader,
            cancelled_follower,
            surviving_follower,
            return_exceptions=True,
        )


@pytest.mark.asyncio
async def test_failed_leader_does_not_remove_replacement_task():
    coalescer = RequestCoalescer(time_fn=lambda: 100.0)
    started = asyncio.Event()
    fail = asyncio.Event()

    async def failing_factory():
        started.set()
        await fail.wait()
        raise RuntimeError("boom")

    leader = asyncio.create_task(coalescer.run("key", failing_factory, ttl_seconds=5))
    await started.wait()
    replacement = asyncio.create_task(asyncio.Event().wait())

    async with coalescer._lock:
        coalescer._inflight["key"] = replacement

    fail.set()
    with pytest.raises(RuntimeError, match="boom"):
        await leader

    assert coalescer._inflight["key"] is replacement
    assert coalescer._recent == {}

    replacement.cancel()
    with pytest.raises(asyncio.CancelledError):
        await replacement
