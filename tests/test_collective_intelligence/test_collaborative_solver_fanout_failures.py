import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.collective_intelligence.collaborative_solver import (
    CollaborativeSolver,
    SolvingSession,
    SolvingStrategy,
)


class FatalComponentSignal(BaseException):
    pass


def _parallel_session(sample_task):
    return SolvingSession(
        session_id="parallel-session",
        original_task=sample_task,
        strategy=SolvingStrategy.PARALLEL,
        components_used=[],
        intermediate_results=[],
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_parallel_solver_propagates_fatal_signal_after_sibling_completion(
    mock_model_provider,
    sample_task,
):
    solver = CollaborativeSolver(mock_model_provider)
    fatal_signal = FatalComponentSignal("fatal component state")
    fatal_started = asyncio.Event()
    sibling_started = asyncio.Event()
    release_sibling = asyncio.Event()

    async def fail_fatally(_task):
        fatal_started.set()
        raise fatal_signal

    async def finish_sibling(_task):
        sibling_started.set()
        await release_sibling.wait()
        return SimpleNamespace(
            consensus_content="Consensus fallback",
            confidence_score=0.8,
        )

    solver.ensemble_reasoner.process = AsyncMock(side_effect=fail_fatally)
    solver.consensus_engine.process = AsyncMock(side_effect=finish_sibling)
    session = _parallel_session(sample_task)
    solve_task = asyncio.create_task(
        solver._solve_parallel(session, sample_task.task_id)
    )

    await fatal_started.wait()
    await sibling_started.wait()
    await asyncio.sleep(0)
    assert not solve_task.done()

    release_sibling.set()
    with pytest.raises(FatalComponentSignal) as raised:
        await solve_task

    assert raised.value is fatal_signal
    assert session.components_used == []


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize(
    "component_failure",
    [RuntimeError("component failed"), asyncio.CancelledError("component stopped")],
)
async def test_parallel_solver_keeps_recoverable_component_failure_fallback(
    mock_model_provider,
    sample_task,
    component_failure,
):
    solver = CollaborativeSolver(mock_model_provider)
    consensus_result = SimpleNamespace(
        consensus_content="Consensus fallback",
        confidence_score=0.8,
    )
    solver.ensemble_reasoner.process = AsyncMock(side_effect=component_failure)
    solver.consensus_engine.process = AsyncMock(return_value=consensus_result)
    session = _parallel_session(sample_task)

    result = await solver._solve_parallel(session, sample_task.task_id)

    assert result.final_content == "Consensus fallback"
    assert session.components_used == ["ensemble_reasoner", "consensus_engine"]
    assert session.intermediate_results == [consensus_result]
