"""Focused regressions for the collective OpenRouter model provider."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest

from openrouter_mcp.collective_intelligence import TaskContext
from openrouter_mcp.config.constants import ModelDefaults
from openrouter_mcp.handlers.collective_intelligence import OpenRouterModelProvider


@pytest.mark.parametrize(
    (
        "requirements",
        "kwargs",
        "expected_messages",
        "expected_temperature",
        "expected_max_tokens",
    ),
    [
        (
            {"system_prompt": "system", "temperature": 0.0, "max_tokens": 111},
            {"temperature": 0.9, "max_tokens": 0},
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "test"},
            ],
            0.0,
            0,
        ),
        (
            {"system_prompt": "", "temperature": None, "max_tokens": 222},
            {"temperature": False, "max_tokens": None},
            [{"role": "user", "content": "test"}],
            False,
            222,
        ),
        (
            {"system_prompt": 0, "temperature": None},
            {"temperature": None},
            [{"role": "user", "content": "test"}],
            ModelDefaults.TEMPERATURE,
            None,
        ),
    ],
)
def test_build_chat_completion_parameters_preserves_precedence_and_inputs(
    requirements,
    kwargs,
    expected_messages,
    expected_temperature,
    expected_max_tokens,
) -> None:
    provider = OpenRouterModelProvider(AsyncMock())
    task = TaskContext(task_id="task-1", content="test", requirements=requirements)
    original_requirements = deepcopy(requirements)
    original_kwargs = deepcopy(kwargs)

    messages, temperature, max_tokens = provider._build_chat_completion_parameters(
        task, kwargs
    )

    assert messages == expected_messages
    assert temperature == expected_temperature
    assert max_tokens == expected_max_tokens
    assert task.requirements == original_requirements
    assert kwargs == original_kwargs


@pytest.mark.asyncio
async def test_process_task_delegates_exact_chat_completion_parameters() -> None:
    client = AsyncMock()
    client.chat_completion.return_value = {"choices": [], "usage": {}}
    provider = OpenRouterModelProvider(client)
    task = TaskContext(task_id="task-1", content="test")
    prepared_messages = [{"role": "user", "content": "prepared"}]
    kwargs = {"temperature": 0.8, "max_tokens": 99, "ignored": True}

    with patch.object(
        provider,
        "_build_chat_completion_parameters",
        return_value=(prepared_messages, 0.25, 17),
    ) as build_parameters, patch.object(
        provider,
        "_estimate_cost",
        new=AsyncMock(return_value=0.0),
    ):
        await provider.process_task(task, "test-model", **kwargs)

    build_parameters.assert_called_once_with(task, kwargs)
    client.chat_completion.assert_awaited_once_with(
        model="test-model",
        messages=prepared_messages,
        temperature=0.25,
        max_tokens=17,
        stream=False,
    )
    assert client.chat_completion.await_args.kwargs["messages"] is prepared_messages


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
