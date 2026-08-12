from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.openrouter_mcp.client.openrouter import OpenRouterClient

pytestmark = pytest.mark.unit


class StreamLines:
    def __init__(self, lines):
        self.lines = lines
        self.consumed = []

    async def aiter_lines(self):
        for line in self.lines:
            self.consumed.append(line)
            yield line


@pytest.mark.asyncio
async def test_iter_stream_chunks_preserves_values_and_stops_at_done(mock_api_key):
    logger = Mock()
    client = OpenRouterClient(api_key=mock_api_key, logger=logger, enable_cache=False)
    response = StreamLines(
        [
            "event: message",
            'data: {"index": 1}',
            "data: 42",
            'data: {"index": 2}',
            "data:   [DONE]  ",
            'data: {"index": 3}',
        ]
    )

    chunks = [chunk async for chunk in client._iter_stream_chunks(response)]

    assert chunks == [{"index": 1}, 42, {"index": 2}]
    assert response.consumed == [
        "event: message",
        'data: {"index": 1}',
        "data: 42",
        'data: {"index": 2}',
        "data:   [DONE]  ",
    ]
    logger.debug.assert_any_call("Stream completed after 3 chunks")
    await client.close()


@pytest.mark.asyncio
async def test_iter_stream_chunks_recovers_without_logging_invalid_content(
    mock_api_key,
):
    logger = Mock()
    client = OpenRouterClient(api_key=mock_api_key, logger=logger, enable_cache=False)
    secret = "private-secret-value"
    invalid_line = f'data: {{"secret": "{secret}"'
    response = StreamLines([invalid_line, 'data: {"ok": true}', "data: [DONE]"])

    chunks = [chunk async for chunk in client._iter_stream_chunks(response)]

    assert chunks == [{"ok": True}]
    warning = logger.warning.call_args.args[0]
    assert f"length: {len(invalid_line[6:])}" in warning
    assert secret not in warning
    await client.close()


@pytest.mark.asyncio
async def test_iter_stream_chunks_logs_only_first_and_every_tenth_chunk(mock_api_key):
    logger = Mock()
    client = OpenRouterClient(api_key=mock_api_key, logger=logger, enable_cache=False)
    response = StreamLines([f'data: {{"index": {index}}}' for index in range(1, 12)])

    chunks = [chunk async for chunk in client._iter_stream_chunks(response)]

    assert chunks == [{"index": index} for index in range(1, 12)]
    metadata_logs = [
        call.args[0]
        for call in logger.debug.call_args_list
        if call.args and call.args[0].startswith("Streaming chunk")
    ]
    assert metadata_logs == [
        "Streaming chunk 1 (keys: ['index'])",
        "Streaming chunk 11 (keys: ['index'])",
    ]
    await client.close()


@pytest.mark.asyncio
async def test_stream_request_delegates_response_to_chunk_iterator(mock_api_key):
    client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
    response = AsyncMock()
    response.status_code = 200
    response.raise_for_status = Mock()
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    first = {"index": 1}
    second = {"index": 2}

    async def parsed_chunks(received_response):
        assert received_response is response
        yield first
        yield second

    parse = Mock(side_effect=parsed_chunks)

    with patch.object(client._client, "stream", return_value=response), patch.object(
        client, "_iter_stream_chunks", parse
    ):
        chunks = [
            chunk
            async for chunk in client._stream_request(
                "/chat/completions",
                {"model": "model-a"},
            )
        ]

    assert chunks == [first, second]
    assert chunks[0] is first
    assert chunks[1] is second
    parse.assert_called_once_with(response)
    response.raise_for_status.assert_called_once_with()
    await client.close()
