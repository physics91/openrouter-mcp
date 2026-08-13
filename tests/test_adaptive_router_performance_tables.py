"""Regression tests for immutable adaptive-router lookup tables."""

import pytest

from openrouter_mcp.collective_intelligence.adaptive_router import (
    _TASK_TYPE_COMPLEXITY_FACTORS,
    _TASK_TYPE_REQUIRED_CAPABILITIES,
    PerformancePredictor,
)
from openrouter_mcp.collective_intelligence.base import (
    ModelCapability,
    ModelInfo,
    TaskContext,
    TaskType,
)


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


@pytest.mark.unit
def test_required_capabilities_preserve_all_task_type_results() -> None:
    """Shared requirements must preserve capability scores and defaults."""
    predictor = PerformancePredictor()
    model = ModelInfo(
        model_id="test-model",
        name="Test Model",
        provider="test",
        capabilities={
            capability: 0.5 + index * 0.05
            for index, capability in enumerate(ModelCapability)
            if index % 2
        },
    )
    expected_requirements = {
        TaskType.REASONING: [ModelCapability.REASONING],
        TaskType.CREATIVE: [ModelCapability.CREATIVITY],
        TaskType.CODE_GENERATION: [ModelCapability.CODE],
        TaskType.ANALYSIS: [ModelCapability.REASONING, ModelCapability.ACCURACY],
        TaskType.MATH: [ModelCapability.MATH],
        TaskType.FACTUAL: [ModelCapability.ACCURACY],
    }

    for task_type in TaskType:
        scores = [
            model.capabilities.get(capability, 0.5)
            for capability in expected_requirements.get(task_type, [])
        ]
        expected = min(1.0, 0.7 + sum(scores) / len(scores) * 0.3) if scores else 0.7
        task = TaskContext(task_type=task_type)
        assert predictor._calculate_capability_match(model, task) == expected


@pytest.mark.unit
def test_required_capability_table_is_immutable() -> None:
    """Shared capability requirements must remain immutable across calls."""
    with pytest.raises(TypeError):
        _TASK_TYPE_REQUIRED_CAPABILITIES[TaskType.REASONING] = ()

    with pytest.raises(TypeError):
        _TASK_TYPE_REQUIRED_CAPABILITIES[TaskType.ANALYSIS][0] = ModelCapability.MATH
