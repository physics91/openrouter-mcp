"""Simulated responses prove provenance handling, not live answer quality."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.collective_intelligence.base import TaskContext
from src.openrouter_mcp.collective_intelligence.collaborative_solver import (
    CollaborativeSolver,
)
from src.openrouter_mcp.collective_intelligence.consensus_engine import (
    ConsensusConfig,
    ConsensusEngine,
)
from src.openrouter_mcp.collective_intelligence.ensemble_reasoning import (
    EnsembleReasoner,
)
from src.openrouter_mcp.handlers._collective_serialization import (
    _serialize_consensus_result,
    _serialize_ensemble_result,
)
from tests.test_cross_validation_acceptance import ReviewProvider

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def test_explicit_model_quorums_are_request_local():
    provider = ReviewProvider({"a": "Answer", "b": "Answer", "c": "Answer"})
    provider.process_task = AsyncMock(wraps=provider.process_task)
    solver = CollaborativeSolver(provider)
    minimum = solver.consensus_engine.config.min_models
    try:
        results = await asyncio.gather(
            *(
                solver._consensus_for_task(
                    TaskContext(
                        content="Question", requirements={"preferred_models": models}
                    )
                )
                for models in (["a", "b"], ["c"])
            )
        )
        assert [set(result.participating_models) for result in results] == [
            {"a", "b"},
            {"c"},
        ]
        assert solver.consensus_engine.config.min_models == minimum
        for call in provider.process_task.call_args_list:
            assert call.args[1] in call.args[0].requirements["preferred_models"]
    finally:
        await solver.shutdown()


async def test_consensus_heuristics_are_not_reported_as_measured_answer_quality():
    engine = ConsensusEngine(
        ReviewProvider(
            {"a": "Wrong but fluent answer", "b": "Wrong but fluent answer"}
        ),
        ConsensusConfig(min_models=2, max_models=2),
    )
    try:
        payload = _serialize_consensus_result(
            await engine.process(TaskContext(content="Question"))
        )
        assert payload["quality_metrics"] is None
        assert payload["quality_evaluation"] == "not_evaluated"
        assert payload["confidence_basis"] == "response_heuristic"
    finally:
        await engine.shutdown()


async def test_ensemble_heuristics_are_not_reported_as_measured_answer_quality():
    result = await EnsembleReasoner(
        ReviewProvider({"a": "Wrong but fluent answer"})
    ).process(TaskContext(content="Question"))
    payload = _serialize_ensemble_result(result)
    assert payload["reasoning_quality"] is None
    assert payload["quality_evaluation"] == "not_evaluated"
