import asyncio
from unittest.mock import Mock

import pytest

from src.openrouter_mcp.handlers import benchmark as benchmark_module
from src.openrouter_mcp.handlers.benchmark import BenchmarkHandler

pytestmark = pytest.mark.unit


class FatalBenchmarkSignal(BaseException):
    """Test-only fatal signal that ordinary model failures must not absorb."""


def _capture_internal_tasks(monkeypatch):
    original_create_task = asyncio.create_task
    created_tasks = []

    def capture(coroutine):
        task = original_create_task(coroutine)
        created_tasks.append(task)
        return task

    monkeypatch.setattr(benchmark_module.asyncio, "create_task", capture)
    return original_create_task, created_tasks


@pytest.mark.asyncio
async def test_ordinary_model_failure_stays_isolated_in_order():
    handler = object.__new__(BenchmarkHandler)
    failure = ValueError("model failed")
    build_error_result = Mock(
        side_effect=lambda model_id, exc: f"error:{model_id}:{exc}"
    )

    async def run_for_model(model_id):
        if model_id == "second":
            raise failure
        return f"result:{model_id}"

    result = await handler._run_models_with_concurrency(
        ["first", "second", "third"],
        run_for_model,
        build_error_result,
        max_concurrent=2,
    )

    assert result == {
        "first": "result:first",
        "second": "error:second:model failed",
        "third": "result:third",
    }
    build_error_result.assert_called_once_with("second", failure)


@pytest.mark.parametrize(
    "fatal_error",
    [
        pytest.param(asyncio.CancelledError("child cancelled"), id="child-cancelled"),
        pytest.param(FatalBenchmarkSignal("fatal signal"), id="fatal-base-exception"),
    ],
)
@pytest.mark.asyncio
async def test_fatal_child_signal_propagates_after_sibling_cleanup(
    monkeypatch, fatal_error
):
    handler = object.__new__(BenchmarkHandler)
    _, created_tasks = _capture_internal_tasks(monkeypatch)
    active_started = asyncio.Event()
    release_active = asyncio.Event()
    finalized_models = []
    build_error_result = Mock(return_value="ordinary failure")

    async def run_for_model(model_id):
        try:
            if model_id == "fatal":
                await active_started.wait()
                raise fatal_error
            if model_id == "active":
                active_started.set()
                await release_active.wait()
                return "active result"

            release_active.set()
            return "queued result"
        finally:
            finalized_models.append(model_id)

    with pytest.raises(type(fatal_error)) as raised:
        await handler._run_models_with_concurrency(
            ["fatal", "active", "queued"],
            run_for_model,
            build_error_result,
            max_concurrent=2,
        )

    assert raised.value is fatal_error
    build_error_result.assert_not_called()
    assert len(created_tasks) == 3
    assert all(task.done() for task in created_tasks)
    assert "active" in finalized_models


@pytest.mark.asyncio
async def test_caller_cancellation_propagates_after_all_jobs_are_reclaimed(monkeypatch):
    handler = object.__new__(BenchmarkHandler)
    original_create_task, created_tasks = _capture_internal_tasks(monkeypatch)
    both_started = asyncio.Event()
    release_jobs = asyncio.Event()
    started_models = []
    finalized_models = []
    build_error_result = Mock(return_value="ordinary failure")

    async def run_for_model(model_id):
        started_models.append(model_id)
        if len(started_models) == 2:
            both_started.set()
        try:
            await release_jobs.wait()
            return model_id
        finally:
            finalized_models.append(model_id)

    fanout = original_create_task(
        handler._run_models_with_concurrency(
            ["first", "second", "queued"],
            run_for_model,
            build_error_result,
            max_concurrent=2,
        )
    )
    await both_started.wait()

    fanout.cancel("caller stopped")
    with pytest.raises(asyncio.CancelledError) as raised:
        await fanout

    assert raised.value.args == ("caller stopped",)
    build_error_result.assert_not_called()
    assert len(created_tasks) == 3
    assert all(task.done() for task in created_tasks)
    assert started_models == ["first", "second"]
    assert finalized_models == ["first", "second"]
