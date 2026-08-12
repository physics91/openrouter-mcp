import asyncio
from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.collective_intelligence.adaptive_router import (
    AdaptiveRouter,
    RoutingStrategy,
)


class FatalEvaluationSignal(BaseException):
    pass


@pytest.mark.asyncio
@pytest.mark.unit
async def test_model_evaluation_propagates_fatal_signal_after_sibling_completion(
    mock_model_provider,
    sample_task,
    sample_models,
):
    router = AdaptiveRouter(mock_model_provider)
    models = sample_models[:2]
    fatal_signal = FatalEvaluationSignal("fatal evaluator state")
    fatal_started = asyncio.Event()
    sibling_started = asyncio.Event()
    release_sibling = asyncio.Event()
    sibling_result = {"model": models[1], "final_score": 0.75}

    async def evaluate(task, model, strategy, **kwargs):
        if model is models[0]:
            fatal_started.set()
            raise fatal_signal

        sibling_started.set()
        await release_sibling.wait()
        return sibling_result

    router._evaluate_single_model = AsyncMock(side_effect=evaluate)
    evaluation_task = asyncio.create_task(
        router._evaluate_models(sample_task, models, RoutingStrategy.ADAPTIVE)
    )

    await fatal_started.wait()
    await sibling_started.wait()
    await asyncio.sleep(0)
    assert not evaluation_task.done()

    release_sibling.set()
    with pytest.raises(FatalEvaluationSignal) as raised:
        await evaluation_task

    assert raised.value is fatal_signal
    assert router._evaluate_single_model.await_count == 2


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize(
    "isolated_failure",
    [
        RuntimeError("ordinary evaluation failure"),
        asyncio.CancelledError("model stopped"),
    ],
)
async def test_model_evaluation_keeps_ordinary_failure_and_cancellation_isolated(
    mock_model_provider,
    sample_task,
    sample_models,
    isolated_failure,
):
    router = AdaptiveRouter(mock_model_provider)
    models = sample_models[:2]
    sibling_result = {"model": models[1], "final_score": 0.75}

    async def evaluate(task, model, strategy, **kwargs):
        if model is models[0]:
            raise isolated_failure
        return sibling_result

    router._evaluate_single_model = AsyncMock(side_effect=evaluate)

    evaluations = await router._evaluate_models(
        sample_task,
        models,
        RoutingStrategy.ADAPTIVE,
    )

    assert evaluations == {models[1].model_id: sibling_result}
