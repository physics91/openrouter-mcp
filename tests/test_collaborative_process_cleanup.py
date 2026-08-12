import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.openrouter_mcp.collective_intelligence.base import TaskContext
from src.openrouter_mcp.collective_intelligence.collaborative_solver import (
    CollaborativeSolver,
    SolvingStrategy,
)

pytestmark = pytest.mark.unit


def _bare_solver(strategy_effect):
    solver = object.__new__(CollaborativeSolver)
    solver.active_sessions = {}
    solver.concurrency_limiter = SimpleNamespace(
        acquire_task_slot=AsyncMock(return_value=True),
        release_task_slot=MagicMock(),
    )
    solver.failure_controller = SimpleNamespace(
        check_circuit_breaker=AsyncMock(return_value=True),
        record_circuit_breaker_success=MagicMock(),
        record_circuit_breaker_failure=MagicMock(),
        record_failure=AsyncMock(return_value=False),
    )
    solver.quota_tracker = SimpleNamespace(
        check_and_increment=AsyncMock(return_value=(True, "ok")),
        reset_request=MagicMock(),
    )
    solver.storage_manager = SimpleNamespace(add_item=AsyncMock())
    solver.cancellation_manager = SimpleNamespace(cancel_all_tasks=AsyncMock())
    solver._execute_solving_strategy = AsyncMock(side_effect=strategy_effect)
    return solver


@pytest.mark.asyncio
async def test_process_cancellation_discards_active_session_and_releases_controls():
    error = asyncio.CancelledError("stop solving")
    solver = _bare_solver(error)
    task = TaskContext(task_id="cancelled-task", content="work")

    with pytest.raises(asyncio.CancelledError) as raised:
        await solver.process(task, strategy=SolvingStrategy.SEQUENTIAL)

    assert raised.value is error
    assert solver.active_sessions == {}
    solver.failure_controller.record_circuit_breaker_failure.assert_called_once_with(
        "collaborative_solver"
    )
    solver.concurrency_limiter.release_task_slot.assert_called_once()
    solver.quota_tracker.reset_request.assert_called_once_with("cancelled-task")
    solver.failure_controller.record_failure.assert_not_awaited()
    solver.cancellation_manager.cancel_all_tasks.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_discards_successful_session_before_storage():
    result = object()
    solver = _bare_solver(None)
    solver._execute_solving_strategy.return_value = result
    task = TaskContext(task_id="successful-task", content="work")

    async def store_session(session_id, session):
        assert session_id not in solver.active_sessions
        assert session.final_result is result

    solver.storage_manager.add_item.side_effect = store_session

    assert await solver.process(task, strategy=SolvingStrategy.SEQUENTIAL) is result
    assert solver.active_sessions == {}
    solver.storage_manager.add_item.assert_awaited_once()
    solver.failure_controller.record_circuit_breaker_success.assert_called_once_with(
        "collaborative_solver"
    )


@pytest.mark.asyncio
async def test_process_error_discards_session_and_preserves_failure_policy():
    error = RuntimeError("strategy failed")
    solver = _bare_solver(error)
    task = TaskContext(task_id="failed-task", content="work")

    with pytest.raises(RuntimeError) as raised:
        await solver.process(task, strategy=SolvingStrategy.SEQUENTIAL)

    assert raised.value is error
    assert solver.active_sessions == {}
    solver.failure_controller.record_failure.assert_awaited_once_with(
        "failed-task",
        "strategy failed",
        is_critical=True,
    )
    solver.failure_controller.record_circuit_breaker_failure.assert_called_once_with(
        "collaborative_solver"
    )
    solver.concurrency_limiter.release_task_slot.assert_called_once()
    solver.quota_tracker.reset_request.assert_called_once_with("failed-task")
