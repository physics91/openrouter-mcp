"""Model transport completion is required before treating answers as evidence."""

from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.collective_intelligence.base import (
    PerformanceMetrics,
    ProcessingResult,
    TaskContext,
    TaskType,
)
from src.openrouter_mcp.collective_intelligence.consensus_engine import (
    ConsensusConfig,
    ConsensusEngine,
)
from src.openrouter_mcp.collective_intelligence.cross_validator import (
    CrossValidator,
    ValidationConfig,
    ValidationStrategy,
)
from src.openrouter_mcp.collective_intelligence.ensemble_reasoning import (
    EnsembleReasoner,
    ModelAssignment,
    SubTask,
)
from tests.test_cross_validation_acceptance import ReviewProvider

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def test_ensemble_total_cost_uses_observed_result_cost():
    provider = ReviewProvider({"model": "Answer"})
    provider.process_task = AsyncMock(
        return_value=ProcessingResult(content="Answer", cost=0.123)
    )
    result = await EnsembleReasoner(provider).process(TaskContext(content="Question"))
    assert result.total_cost == pytest.approx(provider.process_task.await_count * 0.123)


@pytest.mark.parametrize(
    "answer",
    [
        ProcessingResult(content=""),
        ProcessingResult(content="Partial", metadata={"finish_reason": "length"}),
    ],
)
async def test_consensus_excludes_empty_or_truncated_answers(answer):
    provider = ReviewProvider({"a": "", "b": ""})
    provider.process_task = AsyncMock(return_value=answer)
    engine = ConsensusEngine(
        provider, config=ConsensusConfig(min_models=2, max_models=2)
    )
    try:
        with pytest.raises(ValueError, match="Insufficient"):
            await engine.process(TaskContext(content="Question"))
        assert not engine.concurrency_limiter.active_tasks
    finally:
        await engine.shutdown()


async def test_ensemble_marks_empty_answer_as_a_failed_subtask():
    provider = ReviewProvider({"a": ""})
    reasoner = EnsembleReasoner(provider)
    subtask = SubTask(
        sub_task_id="task",
        parent_task_id="parent",
        required_capabilities=[],
        content="Question",
        task_type=TaskType.REASONING,
        max_retries=0,
    )
    assignment = ModelAssignment("task", "a", 0.8, 0.0, 1.0, "Test assignment")
    result = await reasoner._execute_single_sub_task(subtask, assignment)
    assert result.success is False


async def test_consensus_review_rejects_truncated_independent_reference_answers():
    provider = ReviewProvider({"a": "", "b": ""})
    provider.process_task = AsyncMock(
        return_value=ProcessingResult(
            content="Partial answer", metadata={"finish_reason": "length"}
        )
    )
    result = await CrossValidator(
        provider, ValidationConfig(strategy=ValidationStrategy.CONSENSUS_CHECK)
    ).process(ProcessingResult(content="Claim"), TaskContext(content="Question"))
    assert result.metadata["validation_status"] == "incomplete"
    assert provider.process_task.await_count == 2


async def test_higher_error_rate_cannot_improve_performance():
    common = {
        "response_time": 20,
        "throughput": 5,
        "success_rate": 0.5,
        "cost_efficiency": 0.1,
        "resource_utilization": 0.3,
    }
    assert (
        PerformanceMetrics(error_rate=0.0, **common).overall_performance()
        > PerformanceMetrics(error_rate=1.0, **common).overall_performance()
    )


async def test_consensus_calls_only_requested_model_ids():
    provider = ReviewProvider({"a": "Answer", "b": "Answer", "outside": "Answer"})
    provider.process_task = AsyncMock(wraps=provider.process_task)
    engine = ConsensusEngine(provider, ConsensusConfig(min_models=2, max_models=3))
    try:
        await engine.process(
            TaskContext(
                content="Question", requirements={"preferred_models": ["a", "b"]}
            )
        )
        assert {call.args[1] for call in provider.process_task.call_args_list} == {
            "a",
            "b",
        }
    finally:
        await engine.shutdown()


async def test_ensemble_calls_only_requested_model_ids():
    provider = ReviewProvider({"outside": "Answer", "requested": "Answer"})
    provider.process_task = AsyncMock(wraps=provider.process_task)
    await EnsembleReasoner(provider).process(
        TaskContext(
            content="Question", requirements={"preferred_models": ["requested"]}
        )
    )
    assert {call.args[1] for call in provider.process_task.call_args_list} == {
        "requested"
    }
