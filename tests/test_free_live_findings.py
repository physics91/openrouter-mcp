"""Regressions for free routing and media boundaries observed in real API calls."""

import base64
import io
from unittest.mock import AsyncMock, Mock

import pytest
from PIL import Image
from pydantic import ValidationError

from src.openrouter_mcp.client.openrouter import OpenRouterError
from src.openrouter_mcp.free.classifier import FreeTaskType
from src.openrouter_mcp.free.router import FreeModelRouter
from src.openrouter_mcp.handlers.free_chat import FreeChatRequest, _build_result
from src.openrouter_mcp.handlers.multimodal import ImageInput, _build_vision_messages
from src.openrouter_mcp.utils.metadata import determine_cost_tier

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "pricing",
    [
        None,
        {},
        {"prompt": "0"},
        {"prompt": "-1", "completion": "-1"},
        {"prompt": "invalid", "completion": "0"},
        {"prompt": "NaN", "completion": "0"},
        {"prompt": "0", "completion": "0", "audio": "0.1"},
    ],
)
def test_unknown_dynamic_or_non_token_prices_are_not_free(pricing):
    assert determine_cost_tier({"pricing": pricing}) != "free"


@pytest.mark.asyncio
async def test_free_routes_and_listing_exclude_audio_and_unknown_pricing():
    cache = Mock()
    cache.ensure_cache_ready = AsyncMock()
    cache.filter_models.return_value = [
        {
            "id": "audio",
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {"output_modalities": ["text", "audio"]},
        },
        {"id": "dynamic", "pricing": {"prompt": "-1", "completion": "-1"}},
        {"id": "missing"},
        {
            "id": "text",
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {"output_modalities": ["text"]},
        },
    ]
    router = FreeModelRouter(cache)
    assert await router.select_model(preferred_models=["audio", "dynamic"]) == "text"
    assert await router.select_models(3, preferred_models=["audio", "dynamic"]) == [
        "text"
    ]
    assert [item["id"] for item in await router.list_models_with_status()] == ["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["", "\n", None])
async def test_empty_free_output_is_not_recorded_as_success(content):
    metrics = Mock()
    with pytest.raises(OpenRouterError, match="text"):
        await _build_result(
            AsyncMock(),
            "free",
            {"content": content, "usage": {}, "streamed": False},
            FreeTaskType.GENERAL,
            metrics,
            1.0,
        )
    metrics.record_success.assert_not_called()


@pytest.mark.asyncio
async def test_a_reported_charge_cannot_be_presented_as_free():
    metrics = Mock()
    with pytest.raises(RuntimeError, match="cost|charge"):
        await _build_result(
            AsyncMock(),
            "free",
            {"content": "Answer", "usage": {"cost": 0.01}, "streamed": False},
            FreeTaskType.GENERAL,
            metrics,
            1.0,
        )
    metrics.record_success.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_tokens": 0},
        {"max_tokens": True},
        {"temperature": -1},
        {"temperature": float("nan")},
    ],
)
def test_free_generation_bounds(overrides):
    with pytest.raises(ValidationError):
        FreeChatRequest(message="Question", **overrides)


@pytest.mark.parametrize(
    "fmt,mime", [("PNG", "image/png"), ("GIF", "image/gif"), ("WEBP", "image/webp")]
)
def test_vision_payload_declares_the_actual_encoded_image_format(fmt, mime):
    data = io.BytesIO()
    Image.new("RGB", (64, 64), (255, 0, 0)).save(data, format=fmt)
    encoded = base64.b64encode(data.getvalue()).decode()
    messages = _build_vision_messages(
        [{"role": "user", "content": "Name the color."}],
        [ImageInput(type="base64", data=encoded)],
    )
    url = messages[0]["content"][1]["image_url"]["url"]
    assert url == f"data:{mime};base64,{encoded}"
