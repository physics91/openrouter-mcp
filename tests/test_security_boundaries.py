"""Security regressions using real local HTTP, image parsers, and filesystems."""

import asyncio
import base64
import io
import json
import logging
import os
import stat

import pytest
from PIL import Image, UnidentifiedImageError

from src.openrouter_mcp.client.openrouter import OpenRouterClient, OpenRouterError
from src.openrouter_mcp.handlers.multimodal import process_image
from src.openrouter_mcp.models.cache import HTTPTransport
from src.openrouter_mcp.runtime_thrift.batch_lane import (
    DeferredBatchLane,
    DeferredBatchRequest,
)

pytestmark = pytest.mark.security


@pytest.mark.parametrize("factory", [OpenRouterClient, HTTPTransport])
@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.example.com/v1",
        "http://192.168.1.1/v1",
        "http://localhost.example.com/v1",
        "ftp://127.0.0.1/v1",
        "https://user:password@example.com/v1",
        "https://example.com/v1?key=placeholder",
        "https://example.com/v1#fragment",
        "/relative/url",
    ],
)
def test_api_transports_reject_unsafe_base_urls(factory, base_url):
    with pytest.raises(ValueError):
        factory(api_key="audit-placeholder", base_url=base_url)


@pytest.mark.asyncio
@pytest.mark.parametrize("json_body", [True, False])
async def test_provider_error_does_not_expose_secrets(json_body, caplog):
    # The provider is a local echo server; HTTP transport and client are real.
    marker = "audit-placeholder-private-content"
    body = (
        json.dumps({"error": {"message": marker}}).encode()
        if json_body
        else f"<html>{marker}</html>".encode()
    )

    async def handle(reader, writer):
        try:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(
                b"HTTP/1.1 401 Unauthorized\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    caplog.set_level(logging.DEBUG)
    async with server:
        port = server.sockets[0].getsockname()[1]
        async with OpenRouterClient(
            api_key=marker,
            base_url=f"http://127.0.0.1:{port}",
            enable_cache=False,
        ) as client:
            with pytest.raises(OpenRouterError, match="HTTP 401") as error:
                await client.list_models(use_cache=False)
    assert marker not in str(error.value)
    assert marker not in caplog.text


def test_deferred_exports_are_private_and_do_not_overwrite_each_other(tmp_path):
    requests = [
        DeferredBatchRequest(
            model, "/chat/completions", model, {"messages": [{"content": model}]}
        )
        for model in ("provider/model-a", "provider/model_a")
    ]
    lane = DeferredBatchLane(tmp_path)
    first = lane.export_requests(requests, "same batch")
    second = lane.export_requests(requests, "same batch")
    assert first.batch_dir != second.batch_dir
    for exported in (first, second):
        assert len({group["file_name"] for group in exported.groups}) == 2
        for group in exported.groups:
            path = exported.batch_dir / group["file_name"]
            record = json.loads(path.read_text(encoding="utf-8"))
            assert record["custom_id"] == group["model_id"]
            if os.name != "nt":
                assert stat.S_IMODE(path.stat().st_mode) == 0o600
        if os.name != "nt":
            assert stat.S_IMODE(exported.batch_dir.stat().st_mode) == 0o700
            assert stat.S_IMODE(exported.manifest_path.stat().st_mode) == 0o600


@pytest.mark.parametrize("format_name", ["BMP", "TIFF"])
def test_unsupported_image_parsers_are_not_used(format_name):
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2)).save(buffer, format=format_name)
    payload = base64.b64encode(buffer.getvalue()).decode()
    with pytest.raises(UnidentifiedImageError):
        process_image(payload)


@pytest.mark.parametrize("format_name", ["JPEG", "PNG", "WEBP", "GIF"])
def test_supported_image_formats_remain_usable(format_name):
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2)).save(buffer, format=format_name)
    payload = base64.b64encode(buffer.getvalue()).decode()
    assert process_image(payload) == (payload, False)
