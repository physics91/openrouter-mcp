import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.openrouter_mcp.collective_intelligence.base import TaskContext, TaskType
from src.openrouter_mcp.collective_intelligence.collaborative_solver import (
    SolvingStrategy,
    _parse_solving_strategy,
)
from src.openrouter_mcp.collective_intelligence.cross_validator import (
    CrossValidator,
    ValidationConfig,
)
from src.openrouter_mcp.handlers._collective_requests import create_task_context

pytestmark = pytest.mark.unit


def test_invalid_solving_strategy_preserves_enum_error_as_direct_cause():
    value = "not-a-strategy"
    valid = ", ".join(sorted(strategy.value for strategy in SolvingStrategy))

    with pytest.raises(ValueError) as error:
        _parse_solving_strategy(value)

    assert str(error.value) == f"Invalid strategy '{value}'. Valid: {valid}"
    assert isinstance(error.value.__cause__, ValueError)


def test_invalid_task_type_preserves_enum_error_as_direct_cause():
    value = "not-a-task"
    valid = ", ".join(sorted(task_type.value for task_type in TaskType))

    with pytest.raises(ValueError) as error:
        create_task_context("content", task_type=value)

    assert str(error.value) == f"Invalid task_type '{value}'. Valid: {valid}"
    assert isinstance(error.value.__cause__, ValueError)


@pytest.mark.asyncio
async def test_validation_timeout_preserves_timeout_as_direct_cause():
    cause = asyncio.TimeoutError()
    provider = MagicMock()
    provider.process_task = AsyncMock(side_effect=cause)
    validator = CrossValidator(provider, ValidationConfig(timeout_seconds=1.0))
    task = TaskContext(task_type=TaskType.ANALYSIS, content="validate")

    with pytest.raises(Exception) as error:
        await validator._execute_validation_task("model-a", task)

    assert type(error.value) is Exception
    assert str(error.value) == "Validation task timed out for model model-a"
    assert error.value.__cause__ is cause
