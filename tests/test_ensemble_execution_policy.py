from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.collective_intelligence.base import (
    ModelCapability,
    ProcessingResult,
    TaskContext,
    TaskType,
)
from src.openrouter_mcp.collective_intelligence.ensemble_reasoning import (
    DecompositionStrategy,
    EnsembleReasoner,
    EnsembleTask,
    ModelAssignment,
    SubTask,
    SubTaskResult,
    TaskPriority,
)


class FatalSubTaskSignal(BaseException):
    pass


def _build_ensemble_task(
    strategy: DecompositionStrategy,
    *,
    first_priority: TaskPriority = TaskPriority.MEDIUM,
) -> EnsembleTask:
    sub_tasks = [
        SubTask(
            sub_task_id="first",
            parent_task_id="ensemble",
            content="first task",
            task_type=TaskType.REASONING,
            required_capabilities=[ModelCapability.REASONING],
            priority=first_priority,
        ),
        SubTask(
            sub_task_id="second",
            parent_task_id="ensemble",
            content="second task",
            task_type=TaskType.ANALYSIS,
            required_capabilities=[ModelCapability.ACCURACY],
        ),
    ]
    assignments = [
        ModelAssignment(
            sub_task_id=sub_task.sub_task_id,
            model_id=f"model-{index}",
            confidence_score=0.9,
            estimated_cost=0.01,
            estimated_time=1.0,
            justification="test assignment",
        )
        for index, sub_task in enumerate(sub_tasks)
    ]
    return EnsembleTask(
        task_id="ensemble",
        original_task=TaskContext(
            task_id="original",
            task_type=TaskType.REASONING,
            content="original task",
            requirements={"format": "structured"},
            constraints={"max_tokens": 256},
        ),
        decomposition_strategy=strategy,
        sub_tasks=sub_tasks,
        assignments=assignments,
    )


def _build_success_result(
    sub_task: SubTask,
    assignment: ModelAssignment,
) -> SubTaskResult:
    return SubTaskResult(
        sub_task=sub_task,
        assignment=assignment,
        result=ProcessingResult(
            task_id=sub_task.sub_task_id,
            model_id=assignment.model_id,
            content=f"result for {sub_task.sub_task_id}",
            confidence=0.9,
        ),
        success=True,
    )


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize(
    "strategy",
    [
        DecompositionStrategy.SEQUENTIAL,
        DecompositionStrategy.PARALLEL,
        DecompositionStrategy.HIERARCHICAL,
    ],
)
async def test_execution_strategies_preserve_assignment_and_context_forwarding(
    strategy,
):
    reasoner = EnsembleReasoner(AsyncMock())
    ensemble_task = _build_ensemble_task(strategy)
    expected_results = [
        _build_success_result(sub_task, assignment)
        for sub_task, assignment in zip(
            ensemble_task.sub_tasks,
            ensemble_task.assignments,
            strict=True,
        )
    ]
    events = []

    async def execute(
        sub_task,
        assignment,
        *,
        inherited_requirements,
        inherited_constraints,
    ):
        events.append(
            (
                sub_task.sub_task_id,
                assignment,
                inherited_requirements,
                inherited_constraints,
            )
        )
        return expected_results[len(events) - 1]

    reasoner._execute_single_sub_task = AsyncMock(side_effect=execute)

    results = await reasoner._execute_sub_tasks(ensemble_task)

    assert results[0] is expected_results[0]
    assert results[1] is expected_results[1]
    assert [event[0] for event in events] == ["first", "second"]
    for event, assignment in zip(events, ensemble_task.assignments, strict=True):
        assert event[1] is assignment
        assert event[2] is ensemble_task.original_task.requirements
        assert event[3] is ensemble_task.original_task.constraints


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize(
    "strategy",
    [DecompositionStrategy.PARALLEL, DecompositionStrategy.HIERARCHICAL],
)
async def test_gather_strategies_preserve_exception_result_mapping(
    strategy,
):
    reasoner = EnsembleReasoner(AsyncMock())
    ensemble_task = _build_ensemble_task(strategy)
    successful_result = _build_success_result(
        ensemble_task.sub_tasks[1],
        ensemble_task.assignments[1],
    )

    async def execute(sub_task, assignment, **kwargs):
        if sub_task is ensemble_task.sub_tasks[0]:
            raise FatalSubTaskSignal("fatal first task")
        return successful_result

    reasoner._execute_single_sub_task = AsyncMock(side_effect=execute)

    results = await reasoner._execute_sub_tasks(ensemble_task)

    assert results[0].sub_task is ensemble_task.sub_tasks[0]
    assert results[0].assignment is ensemble_task.assignments[0]
    assert results[0].success is False
    assert results[0].error_message == "fatal first task"
    assert results[1] is successful_result


@pytest.mark.asyncio
@pytest.mark.unit
async def test_sequential_strategy_preserves_critical_failure_break():
    reasoner = EnsembleReasoner(AsyncMock())
    ensemble_task = _build_ensemble_task(
        DecompositionStrategy.SEQUENTIAL,
        first_priority=TaskPriority.CRITICAL,
    )
    failed_result = SubTaskResult(
        sub_task=ensemble_task.sub_tasks[0],
        assignment=ensemble_task.assignments[0],
        result=ProcessingResult(
            task_id="first",
            model_id=ensemble_task.assignments[0].model_id,
        ),
        success=False,
        error_message="ordinary failure",
    )
    reasoner._execute_single_sub_task = AsyncMock(return_value=failed_result)

    results = await reasoner._execute_sequential(ensemble_task)

    assert results == [failed_result]
    reasoner._execute_single_sub_task.assert_awaited_once_with(
        ensemble_task.sub_tasks[0],
        ensemble_task.assignments[0],
        inherited_requirements=ensemble_task.original_task.requirements,
        inherited_constraints=ensemble_task.original_task.constraints,
    )
