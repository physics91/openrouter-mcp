"""Execution and spending boundaries reproduced during live feature evaluation."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.openrouter_mcp.client.openrouter import OpenRouterClient
from src.openrouter_mcp.collective_intelligence.base import TaskContext
from src.openrouter_mcp.collective_intelligence.consensus_engine import (
    ConsensusConfig,
    ConsensusEngine,
)
from src.openrouter_mcp.collective_intelligence.ensemble_reasoning import (
    EnsembleReasoner,
)
from src.openrouter_mcp.handlers._openrouter_model_provider import (
    OpenRouterModelProvider,
)
from src.openrouter_mcp.handlers.benchmark import BenchmarkError
from src.openrouter_mcp.handlers.mcp_benchmark import (
    _extract_prompt_price,
    _extract_response_time_seconds,
    _selection_score,
    compare_model_categories,
    compare_model_performance,
)
from tests.test_cross_validation_acceptance import ReviewProvider

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def test_disabled_decomposition_executes_the_original_task_once():
    provider = ReviewProvider({"a": "4", "b": "4"})
    task = TaskContext(content="What is 2 + 2?", requirements={"max_tokens": 64})
    result = await EnsembleReasoner(provider).process(task, decompose=False)
    assert len(provider.tasks) == 1
    assert provider.tasks[0].content == task.content
    assert provider.tasks[0].requirements["max_tokens"] == 64
    assert len(result.sub_task_results) == 1
    assert result.final_content == "4"
    assert result.decomposition_strategy.value == "none"


async def test_insufficient_available_models_fail_before_generation():
    provider = ReviewProvider({"only": "Answer"})
    engine = ConsensusEngine(provider, ConsensusConfig(min_models=2, max_models=2))
    try:
        with pytest.raises(ValueError, match="Insufficient"):
            await engine.process(TaskContext(content="Question"))
        assert provider.tasks == []
        assert not engine.concurrency_limiter.active_tasks
    finally:
        await engine.shutdown()


@pytest.mark.parametrize("prices", [(0, 0), (0, 0.002), (0.002, 0.003)])
async def test_catalog_pricing_stays_per_token_in_collective_cost_estimates(prices):
    prompt_price, completion_price = prices
    async with OpenRouterClient(api_key="test-key", enable_cache=False) as client:
        client.get_model_info = AsyncMock(
            return_value={
                "pricing": {"prompt": prompt_price, "completion": completion_price}
            }
        )
        provider = OpenRouterModelProvider(client)
        cost = await provider._estimate_cost(
            "model",
            {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        )
        assert cost == pytest.approx(1000 * prompt_price + 500 * completion_price)
        assert (
            provider._extract_cost(
                {"prompt": prompt_price, "completion": completion_price}
            )
            == completion_price
        )


@pytest.mark.parametrize("models", [[], ["same", "same"], [""]])
async def test_invalid_comparison_models_fail_before_handler_creation(models):
    with patch(
        "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler",
        new_callable=AsyncMock,
    ) as handler:
        with pytest.raises(BenchmarkError):
            await compare_model_performance(models)
        handler.assert_not_awaited()


@pytest.mark.parametrize("top_n", [0, -1, True])
async def test_invalid_category_counts_fail_before_handler_creation(top_n):
    with patch(
        "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler",
        new_callable=AsyncMock,
    ) as handler:
        with pytest.raises(BenchmarkError):
            await compare_model_categories(top_n=top_n)
        handler.assert_not_awaited()


@pytest.mark.parametrize("value", [-1, "unknown", float("nan"), float("inf"), True])
async def test_invalid_catalog_metrics_cannot_be_treated_as_free_or_fast(value):
    model = {
        "pricing": {"prompt": value},
        "avg_response_time": value,
        "quality_score": 10,
    }
    assert _extract_prompt_price(model) is None
    assert _extract_response_time_seconds(model) is None
    measured = {"pricing": {"prompt": 0.1}, "avg_response_time": 1, "quality_score": 1}
    assert _selection_score(model, "cost") < _selection_score(measured, "cost")
    assert _selection_score(model, "speed") < _selection_score(measured, "speed")


async def test_cost_selection_prioritizes_price_over_unmeasured_quality():
    cheap = {"pricing": {"prompt": 0.0000001}, "quality_score": 1}
    expensive = {"pricing": {"prompt": 0.00003}, "quality_score": 10}
    assert _selection_score(cheap, "cost") > _selection_score(expensive, "cost")


@pytest.mark.parametrize("tool", ["category", "performance"])
async def test_failed_comparisons_preserve_the_provider_error(tool):
    results = {
        "blocked": SimpleNamespace(
            success=False, error_message="HTTP 429: Too Many Requests"
        )
    }
    handler = SimpleNamespace(
        model_cache=SimpleNamespace(
            get_models=AsyncMock(
                return_value=[
                    {
                        "id": "blocked",
                        "category": "chat",
                        "pricing": {"prompt": "0", "completion": "0"},
                    }
                ]
            )
        ),
        benchmark_models=AsyncMock(return_value=results),
    )
    with patch(
        "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler",
        AsyncMock(return_value=handler),
    ):
        if tool == "category":
            result = await compare_model_categories(categories=["chat"], top_n=1)
        else:
            result = await compare_model_performance(["blocked"])
    assert result["benchmark_status"] == "failed"
    assert result["failed_models"] == {"blocked": "HTTP 429: Too Many Requests"}
