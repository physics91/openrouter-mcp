"""Solver evidence regressions with simulated components, not live acceptance."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.collective_intelligence.base import (
    ProcessingResult,
    TaskContext,
)
from src.openrouter_mcp.collective_intelligence.collaborative_solver import (
    CollaborativeSolver,
    SolvingSession,
    SolvingStrategy,
)
from src.openrouter_mcp.collective_intelligence.cross_validator import CrossValidator
from src.openrouter_mcp.handlers._collective_serialization import (
    _serialize_solving_result,
)
from tests.test_cross_validation_acceptance import ReviewProvider, review

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def session():
    return SolvingSession(
        "session", TaskContext(content="Question"), SolvingStrategy.SEQUENTIAL, [], []
    )


async def test_all_parallel_components_failing_is_an_error_and_releases_slot():
    solver = CollaborativeSolver(ReviewProvider({}))
    solver.ensemble_reasoner.process = AsyncMock(
        side_effect=RuntimeError("ensemble failed")
    )
    solver.consensus_engine.process = AsyncMock(
        side_effect=RuntimeError("consensus failed")
    )
    try:
        with pytest.raises(RuntimeError, match="component|solution"):
            await solver.process(
                TaskContext(content="Question"), strategy=SolvingStrategy.PARALLEL
            )
        assert not solver.active_sessions
        assert not solver.concurrency_limiter.active_tasks
    finally:
        await solver.shutdown()


async def test_successful_solver_records_actual_elapsed_time():
    from unittest.mock import patch

    solver = CollaborativeSolver(ReviewProvider({}))

    async def solve(current, request_id):
        return solver._create_solving_result(current, "Candidate")

    solver._solve_parallel = solve
    try:
        with patch(
            "src.openrouter_mcp.collective_intelligence.collaborative_solver.perf_counter",
            side_effect=[10.0, 12.5],
        ):
            result = await solver.process(
                TaskContext(content="Question"), strategy=SolvingStrategy.PARALLEL
            )
        assert result.total_processing_time == 2.5
    finally:
        await solver.shutdown()


async def test_unreviewed_solution_does_not_invent_quality():
    solver = CollaborativeSolver(ReviewProvider({}))
    try:
        payload = _serialize_solving_result(
            solver._create_solving_result(session(), "Candidate")
        )
        assert payload["quality_assessment"] is None
        assert payload["confidence"] is None
        assert payload["validation_status"] == "not_evaluated"
    finally:
        await solver.shutdown()


@pytest.mark.parametrize(
    "final_content, expected",
    [("Reviewed answer", 0.2), ("Different final answer", None)],
)
async def test_quality_only_uses_review_of_the_actual_final_content(
    final_content, expected
):
    provider = ReviewProvider({"a": review(0.2), "b": review(0.2)})
    assessment = await CrossValidator(provider).process(
        ProcessingResult(content="Reviewed answer"), TaskContext(content="Question")
    )
    solver = CollaborativeSolver(provider)
    current = session()
    current.intermediate_results.append(assessment)
    try:
        result = _serialize_solving_result(
            solver._create_solving_result(current, final_content)
        )
        assert result["confidence"] == expected
        if expected is not None:
            assert result["is_valid"] is False
    finally:
        await solver.shutdown()


async def test_sequential_strategy_reviews_combined_output_not_single_subtask():
    provider = ReviewProvider({})
    solver = CollaborativeSolver(provider)
    solver.adaptive_router.process = AsyncMock(return_value=SimpleNamespace())
    solver.ensemble_reasoner.process = AsyncMock(
        return_value=SimpleNamespace(
            final_content="Combined final answer",
            success_rate=1.0,
            sub_task_results=[
                SimpleNamespace(
                    success=True,
                    result=ProcessingResult(
                        content="Only one sub-answer", confidence=0.9
                    ),
                )
            ],
        )
    )
    solver.cross_validator.process = AsyncMock(
        return_value=SimpleNamespace(is_valid=True)
    )
    try:
        await solver._solve_sequential(session(), "request")
        candidate = solver.cross_validator.process.call_args.args[0]
        assert candidate.content == "Combined final answer"
    finally:
        await solver.shutdown()
