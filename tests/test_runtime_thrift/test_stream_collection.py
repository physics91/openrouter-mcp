from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.runtime_thrift import response_metadata as metadata_module

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_collect_stream_enriches_only_after_collection(monkeypatch):
    events = []
    chunks = [{"chunk": 1}, {"chunk": 2}]
    enriched = [{"chunk": 1}, {"chunk": 2, "thrift": {}}]
    client = object()

    async def stream():
        events.append("stream start")
        for chunk in chunks:
            events.append(("yield", chunk))
            yield chunk
        events.append("stream end")

    async def collect(iterable):
        events.append("collect start")
        result = [item async for item in iterable]
        events.append(("collect end", result))
        return result

    async def enrich(*args, **kwargs):
        events.append(("enrich", args, kwargs))
        return enriched

    monkeypatch.setattr(
        metadata_module,
        "collect_async_iterable",
        AsyncMock(side_effect=collect),
        raising=False,
    )
    enrich_chunks = AsyncMock(side_effect=enrich)
    monkeypatch.setattr(
        metadata_module,
        "enrich_final_stream_chunk_with_request_thrift_metadata",
        enrich_chunks,
    )

    result = await metadata_module.collect_stream_with_request_thrift_metadata(
        client,
        "openai/gpt-4",
        stream(),
        logger=None,
        log_context="chat response",
    )

    assert result is enriched
    assert events == [
        "collect start",
        "stream start",
        ("yield", chunks[0]),
        ("yield", chunks[1]),
        "stream end",
        ("collect end", chunks),
        (
            "enrich",
            (client, "openai/gpt-4", chunks),
            {"logger": None, "log_context": "chat response"},
        ),
    ]


@pytest.mark.asyncio
async def test_collect_stream_skips_enrichment_when_collection_fails(monkeypatch):
    error = RuntimeError("stream failed")
    collect = AsyncMock(side_effect=error)
    enrich = AsyncMock()
    monkeypatch.setattr(
        metadata_module,
        "collect_async_iterable",
        collect,
        raising=False,
    )
    monkeypatch.setattr(
        metadata_module,
        "enrich_final_stream_chunk_with_request_thrift_metadata",
        enrich,
    )

    with pytest.raises(RuntimeError) as raised:
        await metadata_module.collect_stream_with_request_thrift_metadata(
            object(),
            "openai/gpt-4",
            AsyncMock(),
        )

    assert raised.value is error
    enrich.assert_not_awaited()


@pytest.mark.asyncio
async def test_collect_empty_stream_still_delegates_enrichment(monkeypatch):
    client = object()
    chunks = []
    monkeypatch.setattr(
        metadata_module,
        "collect_async_iterable",
        AsyncMock(return_value=chunks),
        raising=False,
    )
    enrich = AsyncMock(return_value=chunks)
    monkeypatch.setattr(
        metadata_module,
        "enrich_final_stream_chunk_with_request_thrift_metadata",
        enrich,
    )

    result = await metadata_module.collect_stream_with_request_thrift_metadata(
        client,
        "openai/gpt-4o",
        AsyncMock(),
        log_context="vision response",
    )

    assert result is chunks
    enrich.assert_awaited_once_with(
        client,
        "openai/gpt-4o",
        chunks,
        logger=None,
        log_context="vision response",
    )
