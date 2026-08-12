from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.openrouter_mcp.collective_intelligence import (
    collaborative_solver as solver_module,
)
from src.openrouter_mcp.collective_intelligence.collaborative_solver import (
    CollaborativeSolver,
    SolvingSession,
    SolvingStrategy,
)

pytestmark = pytest.mark.unit


def test_solving_result_delegates_default_quality_metrics():
    solver = object.__new__(CollaborativeSolver)
    timestamp = datetime(2026, 8, 13, 12, 34, 56)
    session = SolvingSession(
        session_id="session",
        original_task=Mock(),
        strategy=SolvingStrategy.SEQUENTIAL,
        components_used=["router"],
        intermediate_results=[],
        start_time=timestamp,
        end_time=timestamp,
    )
    quality_metrics = Mock()
    quality_metrics.overall_score.return_value = 0.42

    with patch.object(
        solver_module,
        "build_quality_metrics",
        return_value=quality_metrics,
    ) as build:
        result = solver._create_solving_result(session, "final content")

    assert list(build.call_args.kwargs) == [
        "accuracy",
        "consistency",
        "completeness",
        "relevance",
        "confidence",
        "coherence",
    ]
    build.assert_called_once_with(
        accuracy=0.8,
        consistency=0.8,
        completeness=0.8,
        relevance=0.8,
        confidence=0.8,
        coherence=0.8,
    )
    quality_metrics.overall_score.assert_called_once_with()
    assert result.quality_assessment is quality_metrics
    assert result.confidence_score == 0.42
