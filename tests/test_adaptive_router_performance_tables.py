"""Regression tests for immutable adaptive-router lookup tables."""

import pytest

from openrouter_mcp.collective_intelligence.adaptive_router import (
    _TASK_TYPE_COMPLEXITY_FACTORS,
    PerformancePredictor,
)
from openrouter_mcp.collective_intelligence.base import TaskContext, TaskType


@pytest.mark.unit
def test_complexity_factors_preserve_all_task_type_results() -> None:
    """Shared factors must preserve the prior values and default handling."""
    predictor = PerformancePredictor()
    expected_factors = {
        TaskType.REASONING: 1.5,
        TaskType.CREATIVE: 1.3,
        TaskType.CODE_GENERATION: 1.4,
        TaskType.ANALYSIS: 1.2,
        TaskType.MATH: 1.3,
        TaskType.FACTUAL: 1.0,
    }

    for task_type in TaskType:
        task = TaskContext(task_type=task_type)
        assert predictor._calculate_complexity_factor(task) == expected_factors.get(
            task_type, 1.0
        )


@pytest.mark.unit
def test_complexity_factor_table_is_immutable() -> None:
    """The shared table must not introduce mutable cross-call state."""
    with pytest.raises(TypeError):
        _TASK_TYPE_COMPLEXITY_FACTORS[TaskType.REASONING] = 9.0
