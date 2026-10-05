"""Boundary regressions, with mocked HTTP/model responses explicitly scoped locally."""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.openrouter_mcp.client.openrouter import OpenRouterClient, OpenRouterError
from src.openrouter_mcp.handlers._collective_requests import (
    CollectiveChatRequest,
    CrossValidationRequest,
)
from src.openrouter_mcp.handlers.benchmark import (
    BenchmarkHandler,
    EnhancedBenchmarkHandler,
    _calculate_enhanced_optional_averages,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field", ["total_tokens", "prompt_tokens", "completion_tokens"]
)
@pytest.mark.parametrize("value", [-1, float("nan"), "5", True])
async def test_provider_rejects_invalid_token_accounting(field, value):
    from src.openrouter_mcp.collective_intelligence.base import TaskContext
    from src.openrouter_mcp.handlers._openrouter_model_provider import (
        OpenRouterModelProvider,
    )

    provider = OpenRouterModelProvider(AsyncMock())
    response = {
        "choices": [{"message": {"content": "Answer"}, "finish_reason": "stop"}],
        "usage": {"cost": 0, field: value},
    }
    with pytest.raises(ValueError, match="token"):
        await provider._build_processing_result(TaskContext(), "model", response, 0.1)


@pytest.mark.parametrize(
    "overrides",
    [
        {"temperature": float("nan")},
        {"temperature": -0.1},
        {"temperature": 2.1},
        {"max_tokens": 0},
        {"max_tokens": -1},
        {"max_tokens": True},
        {"models": ["same", "same"]},
        {"models": [""]},
        {"validation_criteria": ["accuracy", "accuracy"]},
        {"validation_criteria": [" "]},
        {"content": " "},
    ],
)
def test_invalid_review_inputs_are_rejected(overrides):
    with pytest.raises(ValidationError):
        CrossValidationRequest(**{"content": "Claim", **overrides})


@pytest.mark.parametrize(
    "overrides",
    [
        {"min_models": 0},
        {"min_models": 5, "max_models": 2},
        {"confidence_threshold": float("nan")},
        {"confidence_threshold": -1},
    ],
)
def test_invalid_consensus_inputs_are_rejected(overrides):
    with pytest.raises(ValidationError):
        CollectiveChatRequest(prompt="Question", **overrides)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value", ["unknown", None, -1, True, float("nan"), float("inf")]
)
async def test_invalid_remote_spending_is_not_reported_as_a_valid_total(value):
    async with OpenRouterClient(api_key="test-key", enable_cache=False) as client:
        client._make_request = AsyncMock(return_value={"data": {"usage": value}})
        with pytest.raises(OpenRouterError, match="usage"):
            await client.track_usage()


def test_enhanced_benchmark_cost_uses_catalog_per_token_units():
    handler = object.__new__(EnhancedBenchmarkHandler)
    assert handler._calculate_cost_enhanced(
        {"pricing": {"prompt": "0.000002", "completion": "0.000006"}},
        1000,
        500,
        1500,
    ) == pytest.approx(0.005)
    assert (
        handler._calculate_cost_enhanced(
            {"pricing": {"prompt": "0", "completion": "0"}},
            1000,
            500,
            1500,
        )
        == 0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("handler_type", [BenchmarkHandler, EnhancedBenchmarkHandler])
@pytest.mark.parametrize("reported_cost", [0.0, 0.123])
async def test_benchmark_prefers_reported_cost_and_survives_clock_rollback(
    tmp_path, handler_type, reported_cost
):
    client = AsyncMock()
    cache = AsyncMock()
    client.chat_completion.return_value = {
        "choices": [{"message": {"content": "Answer"}, "finish_reason": "stop"}],
        "usage": {
            "total_tokens": 1500,
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "cost": reported_cost,
        },
    }
    if handler_type is EnhancedBenchmarkHandler:
        handler = handler_type(
            client=client, model_cache=cache, results_dir=str(tmp_path)
        )
    else:
        handler = handler_type(
            client=client, model_cache=cache, cache_dir=str(tmp_path)
        )
    with patch(
        "src.openrouter_mcp.handlers.benchmark.time.time", side_effect=[100, 99]
    ):
        result = await handler.benchmark_model("model", "Question")
    assert result.error is None
    assert result.cost == reported_cost
    assert result.response_time_ms >= 0
    cache.get_model_info.assert_not_awaited()
    if isinstance(handler, EnhancedBenchmarkHandler):
        handler.shutdown()


def test_enhanced_averages_include_real_zero_samples():
    from types import SimpleNamespace

    samples = [
        SimpleNamespace(
            prompt_tokens=value,
            completion_tokens=value,
            tokens_used=value,
            quality_score=None,
            throughput_tokens_per_second=value,
        )
        for value in (0, 20)
    ]
    assert _calculate_enhanced_optional_averages(samples) == (10, 10, 10, None, 10)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {"models": []},
        {"models": ["same", "same"]},
        {"runs": 0},
        {"delay_seconds": -1},
        {"delay_seconds": float("nan")},
    ],
)
async def test_invalid_benchmark_jobs_are_rejected_before_handler_creation(arguments):
    from src.openrouter_mcp.handlers.benchmark import BenchmarkError
    from src.openrouter_mcp.handlers.mcp_benchmark import benchmark_models

    with patch(
        "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler",
        new_callable=AsyncMock,
    ) as handler:
        with pytest.raises(BenchmarkError):
            await benchmark_models(**{"models": ["model"], **arguments})
        handler.assert_not_awaited()
