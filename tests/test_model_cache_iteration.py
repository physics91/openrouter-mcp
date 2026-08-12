import threading

import pytest

from src.openrouter_mcp.models.cache import ModelCache

pytestmark = pytest.mark.unit


class _TrackingLock:
    def __init__(self, events):
        self._events = events

    def __enter__(self):
        self._events.append("enter")

    def __exit__(self, exc_type, exc_value, traceback):
        self._events.append("exit")


def _cache_with(models, lock):
    cache = object.__new__(ModelCache)
    cache._memory_cache = models
    cache._cache_lock = lock
    return cache


def test_iter_models_takes_lazy_membership_snapshot_before_first_yield():
    events = []
    first = {"id": "first"}
    second = {"id": "second"}
    cache = _cache_with([first, second], _TrackingLock(events))

    iterator = cache.iter_models()

    assert events == []
    assert next(iterator) is first
    assert events == ["enter", "exit"]
    assert list(iterator) == [second]


def test_iter_models_releases_lock_while_consumer_is_paused():
    cache = _cache_with(
        [{"id": "first"}, {"id": "second"}],
        threading.RLock(),
    )
    iterator = cache.iter_models()
    next(iterator)
    worker_entered = threading.Event()

    def acquire_cache_lock():
        with cache._cache_lock:
            worker_entered.set()

    worker = threading.Thread(target=acquire_cache_lock)
    worker.start()
    try:
        assert worker_entered.wait(timeout=0.5)
    finally:
        iterator.close()
        worker.join(timeout=1.0)

    assert not worker.is_alive()


def test_iter_models_excludes_members_added_after_iteration_starts():
    first = {"id": "first"}
    second = {"id": "second"}
    late = {"id": "late"}
    models = [first, second]
    cache = _cache_with(models, threading.RLock())
    iterator = cache.iter_models()

    assert next(iterator) is first
    models.append(late)

    remaining = list(iterator)
    assert remaining == [second]
    assert remaining[0] is second
