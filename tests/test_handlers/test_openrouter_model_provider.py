"""Focused regressions for the collective OpenRouter model provider."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from openrouter_mcp.collective_intelligence import TaskContext
from openrouter_mcp.config.constants import ModelDefaults
from openrouter_mcp.handlers import _openrouter_model_provider as provider_module
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


@pytest.mark.asyncio
async def test_build_processing_result_preserves_pipeline_order_and_payloads() -> None:
    events = []

    class RecordingDict(dict):
        def __init__(self, *args, label, **kwargs):
            super().__init__(*args, **kwargs)
            self.label = label

        def get(self, key, default=None):
            events.append(f"get:{self.label}:{key}")
            return super().get(key, default)

    provider = OpenRouterModelProvider(AsyncMock())
    task = TaskContext(task_id="task-1", content="test")
    usage = RecordingDict({"total_tokens": 17}, label="usage")
    response_metadata = object()
    response = RecordingDict(
        {"usage": usage, "model": response_metadata},
        label="response",
    )
    first_choice = {"message": {"content": "answer"}}

    def first_response_choice(received_response):
        events.append("choice")
        assert received_response is response
        return True, first_choice

    def calculate_confidence(received_response, content):
        events.append("confidence")
        assert received_response is response
        assert content == "answer"
        return 0.85

    async def estimate_cost(model_id, received_usage):
        events.append("cost")
        assert model_id == "model-a"
        assert received_usage is usage
        return 0.004

    with patch.object(
        provider_module,
        "_first_response_choice",
        side_effect=first_response_choice,
    ) as get_choice, patch.object(
        provider,
        "_calculate_confidence",
        side_effect=calculate_confidence,
    ) as get_confidence, patch.object(
        provider,
        "_estimate_cost",
        new=AsyncMock(side_effect=estimate_cost),
    ) as get_cost:
        result = await provider._build_processing_result(
            task,
            "model-a",
            response,
            1.25,
        )

    get_choice.assert_called_once_with(response)
    get_confidence.assert_called_once_with(response, "answer")
    get_cost.assert_awaited_once_with("model-a", usage)
    assert result.task_id == "task-1"
    assert result.model_id == "model-a"
    assert result.content == "answer"
    assert result.confidence == 0.85
    assert result.processing_time == 1.25
    assert result.tokens_used == 17
    assert result.cost == 0.004
    assert list(result.metadata) == ["usage", "response_metadata", "finish_reason"]
    assert result.metadata["usage"] is usage
    assert result.metadata["response_metadata"] is response_metadata
    assert events == [
        "choice",
        "confidence",
        "get:response:usage",
        "get:usage:total_tokens",
        "cost",
        "get:response:model",
    ]


@pytest.mark.asyncio
async def test_build_processing_result_preserves_no_choice_defaults() -> None:
    provider = OpenRouterModelProvider(AsyncMock())
    provider._estimate_cost = AsyncMock(return_value=0.0)
    task = TaskContext(task_id="task-1", content="test")
    response = {"choices": [], "usage": {}}

    result = await provider._build_processing_result(
        task,
        "model-a",
        response,
        0.5,
    )

    assert result.content == ""
    assert result.confidence == pytest.approx(0.5)
    assert result.tokens_used == 0
    assert result.metadata == {
        "usage": {},
        "response_metadata": {},
        "finish_reason": None,
    }


@pytest.mark.asyncio
async def test_build_processing_result_preserves_malformed_choice_failure_boundary() -> (
    None
):
    provider = OpenRouterModelProvider(AsyncMock())
    task = TaskContext(task_id="task-1", content="test")
    response = {"choices": [None]}

    with patch.object(
        provider, "_calculate_confidence"
    ) as get_confidence, patch.object(
        provider,
        "_estimate_cost",
        new_callable=AsyncMock,
    ) as get_cost:
        with pytest.raises(TypeError):
            await provider._build_processing_result(
                task,
                "model-a",
                response,
                0.5,
            )

    get_confidence.assert_not_called()
    get_cost.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_task_delegates_response_and_elapsed_time_to_result_builder() -> (
    None
):
    client = AsyncMock()
    response = {"choices": [], "usage": {}}
    client.chat_completion.return_value = response
    provider = OpenRouterModelProvider(client)
    task = TaskContext(task_id="task-1", content="test")
    expected = MagicMock()
    with patch.object(
        provider_module,
        "perf_counter",
        side_effect=[100, 101.25],
    ), patch.object(
        provider,
        "_build_processing_result",
        new=AsyncMock(return_value=expected),
    ) as build_result:
        result = await provider.process_task(task, "model-a")

    assert result is expected
    build_result.assert_awaited_once_with(task, "model-a", response, 1.25)


@pytest.mark.asyncio
async def test_process_task_logs_and_rethrows_result_builder_error() -> None:
    client = AsyncMock()
    client.chat_completion.return_value = {"choices": [], "usage": {}}
    provider = OpenRouterModelProvider(client)
    task = TaskContext(task_id="task-1", content="test")
    error = RuntimeError("result failed")

    with patch.object(
        provider,
        "_build_processing_result",
        new=AsyncMock(side_effect=error),
    ), patch.object(provider_module.logger, "error") as log_error:
        with pytest.raises(RuntimeError) as raised:
            await provider.process_task(task, "model-a")

    assert raised.value is error
    log_error.assert_called_once_with(
        "Task processing failed for model model-a: result failed"
    )


def test_build_model_info_preserves_raw_access_and_helper_order() -> None:
    accesses = []

    class RecordingDict(dict):
        def __getitem__(self, key):
            accesses.append(("item", key))
            return super().__getitem__(key)

        def get(self, key, default=None):
            accesses.append(("get", key))
            return super().get(key, default)

    provider = OpenRouterModelProvider(AsyncMock())
    pricing = {"prompt": "0.1"}
    raw_model = RecordingDict(
        {
            "id": "provider/model",
            "name": None,
            "pricing": pricing,
        }
    )
    original_raw_model = deepcopy(dict(raw_model))
    capabilities = {"capability": 0.9}
    helper_order = []

    with patch.object(
        provider,
        "_extract_cost",
        side_effect=lambda value: helper_order.append(("cost", value)) or 0.25,
    ) as extract_cost, patch.object(
        provider,
        "_estimate_capabilities",
        side_effect=lambda value: helper_order.append(("capabilities", value))
        or capabilities,
    ) as estimate_capabilities:
        model_info = provider._build_model_info(raw_model)

    assert accesses == [
        ("item", "id"),
        ("item", "id"),
        ("get", "name"),
        ("get", "provider"),
        ("get", "context_length"),
        ("get", "pricing"),
    ]
    assert helper_order[0][0] == "cost"
    assert helper_order[0][1] is pricing
    assert helper_order[1][0] == "capabilities"
    assert helper_order[1][1] is raw_model
    extract_cost.assert_called_once_with(pricing)
    estimate_capabilities.assert_called_once_with(raw_model)
    assert model_info.model_id == "provider/model"
    assert model_info.name is None
    assert model_info.provider == "unknown"
    assert model_info.context_length == 4096
    assert model_info.cost_per_token == 0.25
    assert model_info.metadata is raw_model
    assert model_info.capabilities is capabilities
    assert raw_model == original_raw_model


def test_build_model_info_preserves_missing_id_failure_boundary() -> None:
    accesses = []

    class RecordingDict(dict):
        def __getitem__(self, key):
            accesses.append(("item", key))
            return super().__getitem__(key)

    provider = OpenRouterModelProvider(AsyncMock())
    raw_model = RecordingDict({"name": "missing id"})

    with patch.object(provider, "_extract_cost") as extract_cost, patch.object(
        provider, "_estimate_capabilities"
    ) as estimate_capabilities:
        with pytest.raises(KeyError, match="id"):
            provider._build_model_info(raw_model)

    assert accesses == [("item", "id")]
    extract_cost.assert_not_called()
    estimate_capabilities.assert_not_called()


@pytest.mark.asyncio
async def test_get_available_models_delegates_ordered_raw_models() -> None:
    client = AsyncMock()
    first_raw = {"id": "first"}
    second_raw = {"id": "second"}
    client.list_models.return_value = [first_raw, second_raw]
    provider = OpenRouterModelProvider(client)
    first_info = MagicMock()
    second_info = MagicMock()

    with patch.object(
        provider,
        "_build_model_info",
        side_effect=[first_info, second_info],
    ) as build_model_info:
        models = await provider.get_available_models()

    assert models == [first_info, second_info]
    assert models[0] is first_info
    assert models[1] is second_info
    client.list_models.assert_awaited_once_with(use_cache=True)
    assert build_model_info.call_args_list == [call(first_raw), call(second_raw)]


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
