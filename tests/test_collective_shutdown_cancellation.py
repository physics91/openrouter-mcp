from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.openrouter_mcp.collective_intelligence import (
    collaborative_solver as solver_module,
)
from src.openrouter_mcp.collective_intelligence import consensus_engine as engine_module
from src.openrouter_mcp.collective_intelligence.collaborative_solver import (
    CollaborativeSolver,
)
from src.openrouter_mcp.collective_intelligence.consensus_engine import ConsensusEngine
from src.openrouter_mcp.collective_intelligence.operational_controls import (
    TaskCancellationManager,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_cancel_all_pending_tasks_preserves_snapshot_order_and_ignores_returns(
    monkeypatch,
):
    manager = TaskCancellationManager()
    manager.pending_tasks = {"first": set(), "second": set()}
    sentinel = object()

    async def cancel(request_id, reason):
        if request_id == "first":
            manager.pending_tasks["late"] = set()
            return None
        return sentinel

    cancel_all = AsyncMock(side_effect=cancel)
    monkeypatch.setattr(manager, "cancel_all_tasks", cancel_all)

    result = await manager.cancel_all_pending_tasks("shutdown")

    assert result is None
    assert cancel_all.await_args_list == [
        call("first", "shutdown"),
        call("second", "shutdown"),
    ]


@pytest.mark.asyncio
async def test_cancel_all_pending_tasks_stops_on_first_failure(monkeypatch):
    manager = TaskCancellationManager()
    manager.pending_tasks = {"first": set(), "second": set(), "third": set()}
    error = RuntimeError("cancel failed")
    cancel_all = AsyncMock(side_effect=[None, error])
    monkeypatch.setattr(manager, "cancel_all_tasks", cancel_all)

    with pytest.raises(RuntimeError) as raised:
        await manager.cancel_all_pending_tasks()

    assert raised.value is error
    assert cancel_all.await_args_list == [
        call("first", "Shutdown requested"),
        call("second", "Shutdown requested"),
    ]


class _TrackingSessions(dict):
    def __init__(self, events):
        super().__init__({"session": object()})
        self._events = events

    def clear(self):
        self._events.append("clear sessions")
        super().clear()


@pytest.mark.asyncio
async def test_collaborative_shutdown_delegates_bulk_cancellation_in_order(monkeypatch):
    events = []
    solver = object.__new__(CollaborativeSolver)
    solver.consensus_engine = SimpleNamespace(
        shutdown=AsyncMock(side_effect=lambda: events.append("consensus shutdown"))
    )
    solver.storage_manager = SimpleNamespace(
        shutdown=AsyncMock(side_effect=lambda: events.append("storage shutdown"))
    )
    cancel = AsyncMock(side_effect=lambda reason: events.append(("cancel", reason)))
    solver.cancellation_manager = SimpleNamespace(cancel_all_pending_tasks=cancel)
    solver.active_sessions = _TrackingSessions(events)
    monkeypatch.setattr(
        solver_module.logger,
        "info",
        MagicMock(side_effect=lambda message: events.append(("log", message))),
    )

    await solver.shutdown()

    assert events == [
        ("log", "Shutting down CollaborativeSolver..."),
        "consensus shutdown",
        "storage shutdown",
        ("cancel", "Shutdown requested"),
        "clear sessions",
        ("log", "CollaborativeSolver shutdown complete"),
    ]


@pytest.mark.asyncio
async def test_consensus_shutdown_delegates_bulk_cancellation_in_order(monkeypatch):
    events = []
    engine = object.__new__(ConsensusEngine)
    engine.storage_manager = SimpleNamespace(
        shutdown=AsyncMock(side_effect=lambda: events.append("storage shutdown"))
    )
    cancel = AsyncMock(side_effect=lambda reason: events.append(("cancel", reason)))
    engine.cancellation_manager = SimpleNamespace(cancel_all_pending_tasks=cancel)
    monkeypatch.setattr(
        engine_module.logger,
        "info",
        MagicMock(side_effect=lambda message: events.append(("log", message))),
    )

    await engine.shutdown()

    assert events == [
        ("log", "Shutting down ConsensusEngine..."),
        "storage shutdown",
        ("cancel", "Shutdown requested"),
        ("log", "ConsensusEngine shutdown complete"),
    ]
