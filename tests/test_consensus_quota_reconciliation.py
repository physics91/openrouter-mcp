from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from src.openrouter_mcp.collective_intelligence import consensus_engine
from src.openrouter_mcp.collective_intelligence.base import (
    ProcessingResult,
    TaskContext,
)
from src.openrouter_mcp.collective_intelligence.consensus_engine import (
    ConsensusConfig,
    ConsensusEngine,
)
from src.openrouter_mcp.config.constants import PricingDefaults


def _install_operational_mocks(engine, quota_results):
    limiter = SimpleNamespace(
        acquire_model_slot=AsyncMock(return_value=True),
        release_model_slot=Mock(),
    )
    quota_tracker = SimpleNamespace(
        check_and_increment=AsyncMock(side_effect=quota_results),
        reconcile_usage=AsyncMock(return_value=(True, "")),
    )
    cancellation_manager = SimpleNamespace(
        register_task=AsyncMock(),
        unregister_task=AsyncMock(),
    )
    engine.concurrency_limiter = limiter
    engine.quota_tracker = quota_tracker
    engine.cancellation_manager = cancellation_manager
    return limiter, quota_tracker, cancellation_manager


@pytest.mark.asyncio
async def test_model_response_reconciles_actual_quota_and_preserves_cleanup(
    monkeypatch,
):
    result = ProcessingResult(
        task_id="task",
        model_id="model",
        content="answer",
        tokens_used=25,
        cost=0.00075,
    )
    provider = SimpleNamespace(process_task=AsyncMock(return_value=result))
    engine = ConsensusEngine(provider, ConsensusConfig(min_models=1, max_models=1))
    limiter, quota_tracker, cancellation = _install_operational_mocks(
        engine,
        [(True, "estimate accepted")],
    )
    monkeypatch.setattr(consensus_engine, "count_tokens", lambda content, model_id: 10)
    task = TaskContext(task_id="task", content="prompt")
    estimated_cost = 10 * PricingDefaults.ESTIMATED_TOKEN_PRICE

    try:
        responses = await engine._get_model_responses(task, ["model"], "request")
    finally:
        await engine.storage_manager.shutdown()

    assert [response.result for response in responses] == [result]
    assert quota_tracker.check_and_increment.await_args_list == [
        call("request", tokens=10, cost=estimated_cost),
    ]
    quota_tracker.reconcile_usage.assert_awaited_once_with(
        "request", tokens=15, cost=result.cost - estimated_cost
    )
    limiter.release_model_slot.assert_called_once_with()
    cancellation.register_task.assert_awaited_once()
    cancellation.unregister_task.assert_awaited_once()
    registered_task = cancellation.register_task.await_args.args[1]
    assert cancellation.unregister_task.await_args == call("request", registered_task)


@pytest.mark.asyncio
async def test_zero_actual_usage_keeps_estimate_without_reconciliation(monkeypatch):
    result = ProcessingResult(
        task_id="task",
        model_id="model",
        content="answer",
        tokens_used=0,
        cost=0.0,
    )
    provider = SimpleNamespace(process_task=AsyncMock(return_value=result))
    engine = ConsensusEngine(provider, ConsensusConfig(min_models=1, max_models=1))
    limiter, quota_tracker, cancellation = _install_operational_mocks(
        engine, [(True, "estimate accepted")]
    )
    monkeypatch.setattr(consensus_engine, "count_tokens", lambda content, model_id: 10)
    task = TaskContext(task_id="task", content="prompt")
    estimated_cost = 10 * PricingDefaults.ESTIMATED_TOKEN_PRICE

    try:
        responses = await engine._get_model_responses(task, ["model"], "request")
    finally:
        await engine.storage_manager.shutdown()

    assert [response.result for response in responses] == [result]
    quota_tracker.check_and_increment.assert_awaited_once_with(
        "request", tokens=10, cost=estimated_cost
    )
    limiter.release_model_slot.assert_called_once_with()
    cancellation.register_task.assert_awaited_once()
    cancellation.unregister_task.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tokens_used", "actual_cost", "expected_call"),
    [
        (10, 0.1, None),
        (0, 0.5, call("request", tokens=-10, cost=0.4)),
        (-1, -0.1, None),
    ],
)
async def test_reconcile_quota_usage_preserves_boundary_conditions(
    tokens_used, actual_cost, expected_call
):
    engine = object.__new__(ConsensusEngine)
    quota_tracker = SimpleNamespace(reconcile_usage=AsyncMock(return_value=(True, "")))
    engine.quota_tracker = quota_tracker
    result = ProcessingResult(tokens_used=tokens_used, cost=actual_cost)

    await engine._reconcile_quota_usage(
        "request",
        "model",
        result,
        estimated_tokens=10,
        estimated_cost=0.1,
    )

    if expected_call is None:
        quota_tracker.reconcile_usage.assert_not_awaited()
    else:
        assert quota_tracker.reconcile_usage.await_args == expected_call
