from contextlib import nullcontext
from unittest.mock import AsyncMock, MagicMock

import pytest

from openrouter_mcp.handlers import multimodal
from openrouter_mcp.handlers.multimodal import ImageInput, VisionChatRequest

pytestmark = pytest.mark.unit


def _request() -> VisionChatRequest:
    return VisionChatRequest(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": "analyze"}],
        images=[ImageInput(data="https://example.com/image.jpg", type="url")],
        temperature=0.25,
        max_tokens=33,
        stream=False,
    )


@pytest.mark.asyncio
async def test_complete_vision_pipeline_preserves_enrichment_and_event_order(
    monkeypatch,
):
    events = []
    response = {"choices": [{"message": {"content": "image"}}]}
    enriched_response = {"choices": [], "thrift": {"saved_tokens": 3}}
    client = MagicMock()

    async def complete(**kwargs):
        events.append("complete")
        return response

    async def enrich(*args, **kwargs):
        events.append("enrich")
        return enriched_response

    client.chat_completion = AsyncMock(side_effect=complete)
    enrich_response = AsyncMock(side_effect=enrich)
    monkeypatch.setattr(
        multimodal,
        "enrich_response_with_request_thrift_metadata",
        enrich_response,
    )
    monkeypatch.setattr(
        multimodal.logger,
        "info",
        MagicMock(side_effect=lambda message: events.append(f"log:{message}")),
    )
    vision_messages = [{"role": "user", "content": "vision payload"}]

    result = await multimodal._complete_vision_chat_with_thrift_metadata(
        client,
        _request(),
        vision_messages,
    )

    assert result is enriched_response
    client.chat_completion.assert_awaited_once_with(
        model="openai/gpt-4o",
        messages=vision_messages,
        temperature=0.25,
        max_tokens=33,
    )
    enrich_response.assert_awaited_once_with(
        client,
        "openai/gpt-4o",
        response,
        logger=multimodal.logger,
        log_context="vision response",
    )
    assert events == [
        "log:Initiating non-streaming vision chat completion",
        "complete",
        "enrich",
        "log:Vision chat completion successful",
    ]


@pytest.mark.asyncio
async def test_complete_vision_pipeline_rejects_non_dict_before_enrichment(
    monkeypatch,
):
    events = []
    client = MagicMock()

    async def complete(**kwargs):
        events.append("complete")
        return []

    client.chat_completion = AsyncMock(side_effect=complete)
    enrich_response = AsyncMock()
    monkeypatch.setattr(
        multimodal,
        "enrich_response_with_request_thrift_metadata",
        enrich_response,
    )
    monkeypatch.setattr(
        multimodal.logger,
        "info",
        MagicMock(side_effect=lambda message: events.append(f"log:{message}")),
    )

    with pytest.raises(
        ValueError,
        match="Invalid response format from vision chat completion",
    ):
        await multimodal._complete_vision_chat_with_thrift_metadata(
            client,
            _request(),
            [],
        )

    enrich_response.assert_not_awaited()
    assert events == [
        "log:Initiating non-streaming vision chat completion",
        "complete",
    ]


@pytest.mark.asyncio
async def test_complete_vision_pipeline_propagates_enrichment_failure_before_success_log(
    monkeypatch,
):
    events = []
    error = RuntimeError("enrichment failed")
    client = MagicMock()

    async def complete(**kwargs):
        events.append("complete")
        return {"choices": []}

    async def enrich(*args, **kwargs):
        events.append("enrich")
        raise error

    client.chat_completion = AsyncMock(side_effect=complete)
    monkeypatch.setattr(
        multimodal,
        "enrich_response_with_request_thrift_metadata",
        AsyncMock(side_effect=enrich),
    )
    monkeypatch.setattr(
        multimodal.logger,
        "info",
        MagicMock(side_effect=lambda message: events.append(f"log:{message}")),
    )

    with pytest.raises(RuntimeError) as raised:
        await multimodal._complete_vision_chat_with_thrift_metadata(
            client,
            _request(),
            [],
        )

    assert raised.value is error
    assert events == [
        "log:Initiating non-streaming vision chat completion",
        "complete",
        "enrich",
    ]


@pytest.mark.asyncio
async def test_chat_with_vision_delegates_non_streaming_pipeline(monkeypatch):
    client = MagicMock()
    request = _request()
    base_messages = [{"role": "user", "content": "serialized"}]
    vision_messages = [{"role": "user", "content": "vision payload"}]
    enriched_response = {"choices": [], "thrift": {"saved_tokens": 3}}
    complete = AsyncMock(return_value=enriched_response)
    monkeypatch.setattr(
        multimodal,
        "get_openrouter_client",
        AsyncMock(return_value=client),
    )
    monkeypatch.setattr(
        multimodal,
        "serialize_messages",
        MagicMock(return_value=base_messages),
    )
    monkeypatch.setattr(
        multimodal,
        "_build_vision_messages",
        MagicMock(return_value=vision_messages),
    )
    monkeypatch.setattr(
        multimodal,
        "_complete_vision_chat_with_thrift_metadata",
        complete,
        raising=False,
    )
    monkeypatch.setattr(multimodal, "thrift_request_scope", nullcontext)

    result = await multimodal.chat_with_vision(request)

    assert result is enriched_response
    complete.assert_awaited_once_with(client, request, vision_messages)
