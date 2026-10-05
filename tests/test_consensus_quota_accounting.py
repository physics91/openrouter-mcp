"""Quota reconciliation must count API attempts once and retain observed spend."""

import asyncio

import pytest

from src.openrouter_mcp.collective_intelligence.base import (
    ProcessingResult,
    TaskContext,
)
from src.openrouter_mcp.collective_intelligence.consensus_engine import (
    ConsensusConfig,
    ConsensusEngine,
)
from src.openrouter_mcp.collective_intelligence.operational_controls import (
    OperationalConfig,
    QuotaConfig,
)
from tests.test_cross_validation_acceptance import ReviewProvider

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def test_two_model_requests_fit_a_two_call_quota():
    provider = ReviewProvider({"a": "Answer", "b": "Answer"})
    engine = ConsensusEngine(
        provider,
        ConsensusConfig(
            min_models=2,
            max_models=2,
            operational_config=OperationalConfig(
                quota=QuotaConfig(max_api_calls_per_request=2)
            ),
        ),
    )
    try:
        result = await engine.process(TaskContext(content="Question"))
        assert result.consensus_content == "Answer"
        assert len(provider.tasks) == 2
        assert len(engine.quota_tracker.minute_calls) == 2
    finally:
        await engine.shutdown()


async def test_reconciliation_does_not_consume_a_second_call_and_handles_free_response():
    engine = ConsensusEngine(ReviewProvider({}))
    try:
        await engine.quota_tracker.check_and_increment("request", tokens=20, cost=0.01)
        await engine._reconcile_quota_usage(
            "request",
            "model",
            ProcessingResult(content="Answer", tokens_used=5, cost=0),
            20,
            0.01,
        )
        usage = engine.quota_tracker.get_usage("request")
        assert usage["calls"] == 1
        assert usage["tokens"] == 5
        assert usage["cost"] == 0
        assert usage["minute_calls"] == 1
    finally:
        await engine.shutdown()


async def test_reconciliation_raises_on_overage_and_retains_observed_cost():
    engine = ConsensusEngine(
        ReviewProvider({}),
        ConsensusConfig(
            operational_config=OperationalConfig(
                quota=QuotaConfig(max_cost_per_request=0.1)
            )
        ),
    )
    try:
        await engine.quota_tracker.check_and_increment("request", tokens=20, cost=0.01)
        with pytest.raises(RuntimeError, match="quota|Quota"):
            await engine._reconcile_quota_usage(
                "request",
                "model",
                ProcessingResult(content="Answer", tokens_used=25, cost=0.25),
                20,
                0.01,
            )
        assert engine.quota_tracker.get_usage("request")["cost"] == pytest.approx(0.25)
    finally:
        await engine.shutdown()


async def test_observed_overage_cancels_pending_provider_and_releases_capacity():
    started = asyncio.Event()
    cancelled = asyncio.Event()
    provider = ReviewProvider({"expensive": "", "pending": ""})

    async def respond(task, model_id):
        if model_id == "pending":
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
        await started.wait()
        return ProcessingResult(content="Answer", tokens_used=25, cost=0.25)

    provider.process_task = respond
    engine = ConsensusEngine(
        provider,
        ConsensusConfig(
            min_models=2,
            max_models=2,
            operational_config=OperationalConfig(
                quota=QuotaConfig(max_cost_per_request=0.1)
            ),
        ),
    )
    try:
        with pytest.raises(RuntimeError, match="quota|Quota"):
            await asyncio.wait_for(
                engine.process(TaskContext(content="Question")), timeout=1
            )
        assert cancelled.is_set()
        assert not engine.concurrency_limiter.active_tasks
        for _ in range(engine.operational_config.concurrency.max_concurrent_models):
            assert await asyncio.wait_for(
                engine.concurrency_limiter.acquire_model_slot(), timeout=0.2
            )
        for _ in range(engine.operational_config.concurrency.max_concurrent_models):
            engine.concurrency_limiter.release_model_slot()
    finally:
        await engine.shutdown()
