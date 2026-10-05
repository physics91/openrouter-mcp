from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from src.openrouter_mcp.client import openrouter
from src.openrouter_mcp.client.openrouter import OpenRouterClient

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("pricing", "normalized", "expected"),
    [
        (
            {"prompt": 0.00001},
            {"prompt": 0.00001, "completion": 0.0},
            {"prompt": 0.00001, "completion": 0.00001},
        ),
        (
            {"completion": 0.00002},
            {"prompt": 0.0, "completion": 0.00002},
            {"prompt": 0.00002, "completion": 0.00002},
        ),
        (
            {"prompt": 0.0, "completion": 0.0},
            {"prompt": 0.0, "completion": 0.0},
            {"prompt": 0.0, "completion": 0.0},
        ),
    ],
)
def test_build_model_pricing_result_preserves_available_price_policy(
    monkeypatch,
    pricing,
    normalized,
    expected,
):
    normalize = Mock(return_value=dict(normalized))
    monkeypatch.setattr(openrouter, "normalize_pricing", normalize)

    result = openrouter._build_model_pricing_result(
        pricing,
        pricing_available=True,
        fallback_used=False,
        source="api",
    )

    assert result == {
        **expected,
        "_meta": {
            "pricing_available": True,
            "fallback_used": False,
            "source": "api",
        },
    }
    assert normalize.call_args_list == [
        call(pricing, normalize_units=False, fill_missing=False)
    ]
    assert normalize.call_args.args[0] is pricing


def test_build_model_pricing_result_forces_fallback_policy(monkeypatch):
    pricing = {}
    normalized = {"prompt": "0.00003", "completion": 0.00004}
    normalize = Mock(return_value=normalized)
    monkeypatch.setattr(openrouter, "normalize_pricing", normalize)

    result = openrouter._build_model_pricing_result(
        pricing,
        pricing_available=False,
        fallback_used=False,
        source="cache",
    )

    assert result == {
        "prompt": 0.00003,
        "completion": 0.00004,
        "_meta": {
            "pricing_available": False,
            "fallback_used": True,
            "source": "fallback",
        },
    }
    assert normalize.call_args_list == [call(pricing)]


def test_build_model_pricing_result_propagates_normalization_error(monkeypatch):
    expected_error = RuntimeError("normalization failed")
    monkeypatch.setattr(
        openrouter,
        "normalize_pricing",
        Mock(side_effect=expected_error),
    )

    with pytest.raises(RuntimeError) as exc_info:
        openrouter._build_model_pricing_result(
            {"prompt": 1},
            pricing_available=True,
            fallback_used=False,
            source="api",
        )

    assert exc_info.value is expected_error


@pytest.mark.asyncio
async def test_get_model_pricing_delegates_api_pricing_to_result_builder(mock_api_key):
    client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
    pricing = {"prompt": 0.0, "completion": 0.0}
    built_result = {"built": True}
    build_result = Mock(return_value=built_result)

    with patch.object(
        client,
        "get_model_info",
        new=AsyncMock(return_value={"pricing": pricing}),
    ), patch.object(openrouter, "_build_model_pricing_result", build_result):
        result = await client.get_model_pricing("openai/gpt-4")

    assert result is built_result
    build_result.assert_called_once_with(
        pricing,
        pricing_available=True,
        fallback_used=False,
        source="api",
    )
    assert build_result.call_args.args[0] is pricing
    await client.close()


@pytest.mark.asyncio
async def test_get_model_pricing_delegates_cache_failure_state(mock_api_key):
    logger = Mock()
    client = OpenRouterClient(api_key=mock_api_key, logger=logger)
    expected_error = RuntimeError("cache failed")
    built_result = {"built": True}
    build_result = Mock(return_value=built_result)

    with patch.object(
        client._model_cache,
        "get_model_info",
        new=AsyncMock(side_effect=expected_error),
    ), patch.object(openrouter, "_build_model_pricing_result", build_result):
        result = await client.get_model_pricing("openai/gpt-4")

    assert result is built_result
    build_result.assert_called_once_with(
        {},
        pricing_available=False,
        fallback_used=True,
        source="cache",
    )
    logger.warning.assert_called_once_with(
        "Failed to fetch pricing for model openai/gpt-4: cache failed"
    )
    await client.close()
