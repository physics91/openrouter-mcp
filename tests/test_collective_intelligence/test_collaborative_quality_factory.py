from datetime import datetime
from unittest.mock import Mock

import pytest

from src.openrouter_mcp.collective_intelligence.collaborative_solver import (
    CollaborativeSolver,
    SolvingSession,
    SolvingStrategy,
)

pytestmark = pytest.mark.unit


def test_solving_result_does_not_create_default_quality_metrics():
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
    result = solver._create_solving_result(session, "final content")
    assert result.quality_assessment is None
    assert result.confidence_score is None
    assert result.metadata["validation_status"] == "not_evaluated"
