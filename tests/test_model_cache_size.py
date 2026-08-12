from datetime import datetime
from unittest.mock import call, patch

import pytest

from src.openrouter_mcp.models import cache as cache_module
from src.openrouter_mcp.models.cache import ModelCache

pytestmark = pytest.mark.unit


@pytest.fixture
def cache(tmp_path):
    instance = ModelCache(cache_file=str(tmp_path / "models.json"))
    yield instance
    instance.shutdown()


def test_calculate_cache_size_mb_serializes_models_and_converts_bytes():
    models = [{"id": "model-a"}]

    with patch.object(
        cache_module.json,
        "dumps",
        return_value="serialized models",
    ) as serialize, patch.object(
        cache_module.sys,
        "getsizeof",
        return_value=2.5 * 1024 * 1024,
    ) as get_size:
        result = ModelCache._calculate_cache_size_mb(models)

    assert result == 2.5
    serialize.assert_called_once_with(models, ensure_ascii=False)
    get_size.assert_called_once_with("serialized models")


def test_calculate_cache_size_mb_logs_and_returns_zero_on_serialization_failure():
    models = [{"id": "model-a"}]
    error = TypeError("not serializable")

    with patch.object(
        cache_module.json,
        "dumps",
        side_effect=error,
    ), patch.object(cache_module.sys, "getsizeof") as get_size, patch.object(
        cache_module.logger,
        "warning",
    ) as warning:
        result = ModelCache._calculate_cache_size_mb(models)

    assert result == 0.0
    get_size.assert_not_called()
    warning.assert_called_once_with("Failed to calculate cache size: not serializable")


def test_get_cache_stats_delegates_size_calculation_in_existing_order(cache):
    models = [{"id": "model-a"}]
    updated_at = datetime(2026, 8, 12, 12, 34, 56)
    cache._memory_cache = models
    cache._last_update = updated_at
    cache.ttl_seconds = 123
    events = []

    with patch.object(
        cache,
        "_summarize_cached_models",
        side_effect=lambda value: events.append(call.summarize(value))
        or (["provider-a"], 2, 3),
    ) as summarize, patch.object(
        cache,
        "_calculate_cache_size_mb",
        side_effect=lambda value: events.append(call.calculate(value)) or 1.23456,
    ) as calculate, patch.object(
        cache,
        "is_expired",
        side_effect=lambda: events.append(call.is_expired()) or True,
    ):
        result = cache.get_cache_stats()

    assert result == {
        "total_models": 1,
        "providers": ["provider-a"],
        "vision_capable_count": 2,
        "reasoning_model_count": 3,
        "cache_size_mb": 1.2346,
        "last_updated": "2026-08-12T12:34:56",
        "is_expired": True,
        "ttl_seconds": 123,
    }
    summarize.assert_called_once_with(models)
    calculate.assert_called_once_with(models)
    assert events == [
        call.summarize(models),
        call.calculate(models),
        call.is_expired(),
    ]
