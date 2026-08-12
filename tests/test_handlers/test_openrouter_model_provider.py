"""Focused regressions for the collective OpenRouter model provider."""

from unittest.mock import AsyncMock

import pytest

from openrouter_mcp.collective_intelligence import TaskContext
from openrouter_mcp.handlers.collective_intelligence import OpenRouterModelProvider


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"choices": None},
        {"choices": []},
    ],
)
@pytest.mark.asyncio
async def test_process_task_handles_responses_without_choices(response: dict) -> None:
    client = AsyncMock()
    client.chat_completion.return_value = response
    client.get_model_pricing.return_value = {"prompt": 0.0, "completion": 0.0}
    provider = OpenRouterModelProvider(client)

    result = await provider.process_task(
        TaskContext(task_id="task-1", content="test"),
        "test-model",
    )

    assert result.task_id == "task-1"
    assert result.model_id == "test-model"
    assert result.content == ""
    assert result.confidence == pytest.approx(0.5)
    assert result.tokens_used == 0
    assert result.cost == 0.0


@pytest.mark.asyncio
async def test_process_task_preserves_malformed_nonempty_choice_error() -> None:
    client = AsyncMock()
    client.chat_completion.return_value = {"choices": [None]}
    provider = OpenRouterModelProvider(client)

    with pytest.raises(TypeError):
        await provider.process_task(
            TaskContext(task_id="task-1", content="test"),
            "test-model",
        )
