import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.openrouter_mcp.collective_intelligence import consensus_engine
from src.openrouter_mcp.collective_intelligence.base import (
    ProcessingResult,
    TaskContext,
)
from src.openrouter_mcp.collective_intelligence.consensus_engine import (
    ConsensusConfig,
    ConsensusEngine,
)


class FatalModelSignal(BaseException):
    pass


def _build_engine(provider, *, min_models=1, unregister_side_effect=None):
    engine = object.__new__(ConsensusEngine)
    engine.config = ConsensusConfig(
        min_models=min_models,
        max_models=max(1, min_models),
        timeout_seconds=5.0,
    )
    engine.model_provider = provider
    engine.model_reliability = {}
    limiter = SimpleNamespace(
        acquire_model_slot=AsyncMock(return_value=True),
        release_model_slot=Mock(),
    )
    quota_tracker = SimpleNamespace(
        check_and_increment=AsyncMock(return_value=(True, "accepted")),
    )
    cancellation_manager = SimpleNamespace(
        register_task=AsyncMock(),
        unregister_task=AsyncMock(side_effect=unregister_side_effect),
    )
    engine.concurrency_limiter = limiter
    engine.quota_tracker = quota_tracker
    engine.cancellation_manager = cancellation_manager
    return engine, limiter, cancellation_manager


@pytest.mark.asyncio
@pytest.mark.unit
async def test_model_fanout_propagates_fatal_signal_after_sibling_cleanup(monkeypatch):
    fatal_signal = FatalModelSignal("fatal provider state")
    fatal_started = asyncio.Event()
    sibling_started = asyncio.Event()
    release_sibling = asyncio.Event()

    async def process_task(task, model_id):
        if model_id == "fatal-model":
            fatal_started.set()
            raise fatal_signal

        sibling_started.set()
        await release_sibling.wait()
        return ProcessingResult(
            task_id=task.task_id,
            model_id=model_id,
            content="sibling result",
        )

    provider = SimpleNamespace(process_task=AsyncMock(side_effect=process_task))
    engine, limiter, cancellation = _build_engine(provider)
    monkeypatch.setattr(consensus_engine, "count_tokens", lambda content, model_id: 1)
    response_task = asyncio.create_task(
        engine._get_model_responses(
            TaskContext(task_id="task", content="prompt"),
            ["fatal-model", "sibling-model"],
            "request",
        )
    )

    await fatal_started.wait()
    await sibling_started.wait()
    await asyncio.sleep(0)
    assert not response_task.done()

    release_sibling.set()
    with pytest.raises(FatalModelSignal) as raised:
        await response_task

    assert raised.value is fatal_signal
    assert limiter.release_model_slot.call_count == 2
    assert cancellation.unregister_task.await_count == 2
    registered_tasks = [
        call.args[1] for call in cancellation.register_task.await_args_list
    ]
    assert len(registered_tasks) == 2
    assert all(task.done() for task in registered_tasks)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_model_fanout_keeps_independent_cancellation_isolated(monkeypatch):
    async def process_task(task, model_id):
        raise asyncio.CancelledError("provider stopped")

    provider = SimpleNamespace(process_task=AsyncMock(side_effect=process_task))
    engine, limiter, cancellation = _build_engine(provider)
    monkeypatch.setattr(consensus_engine, "count_tokens", lambda content, model_id: 1)

    with pytest.raises(ValueError, match="Insufficient responses"):
        await engine._get_model_responses(
            TaskContext(task_id="task", content="prompt"),
            ["cancelled-model"],
            "request",
        )

    limiter.release_model_slot.assert_called_once_with()
    cancellation.unregister_task.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_model_fanout_keeps_unregister_error_isolated(monkeypatch):
    result = ProcessingResult(
        task_id="task",
        model_id="model",
        content="answer",
    )
    provider = SimpleNamespace(process_task=AsyncMock(return_value=result))
    engine, limiter, cancellation = _build_engine(
        provider,
        unregister_side_effect=RuntimeError("unregister failed"),
    )
    monkeypatch.setattr(consensus_engine, "count_tokens", lambda content, model_id: 1)

    with pytest.raises(ValueError, match="Insufficient responses"):
        await engine._get_model_responses(
            TaskContext(task_id="task", content="prompt"),
            ["model"],
            "request",
        )

    limiter.release_model_slot.assert_called_once_with()
    cancellation.unregister_task.assert_awaited_once()
