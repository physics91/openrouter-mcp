from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.openrouter_mcp.models import cache as cache_module
from src.openrouter_mcp.models.cache import ModelCache

pytestmark = pytest.mark.unit


@pytest.fixture
def cache(tmp_path):
    return ModelCache(cache_file=str(tmp_path / "models.json"))


@pytest.mark.asyncio
async def test_store_refreshed_models_updates_memory_then_persists(cache):
    models = [{"id": "model-a"}]
    updated_at = datetime(2026, 8, 12, 12, 34, 56)
    loop = MagicMock()
    loop.run_in_executor = AsyncMock(return_value=None)

    with patch.object(cache_module, "datetime") as datetime_type, patch.object(
        cache_module.asyncio,
        "get_running_loop",
        return_value=loop,
    ) as get_loop, patch.object(cache_module.logger, "info") as log:
        datetime_type.now.return_value = updated_at
        result = await cache._store_refreshed_models(models)

    assert result is models
    assert cache._memory_cache is models
    assert cache._last_update is updated_at
    datetime_type.now.assert_called_once_with()
    get_loop.assert_called_once_with()
    loop.run_in_executor.assert_awaited_once_with(
        cache._executor,
        cache._save_to_file_cache,
        models,
    )
    log.assert_called_once_with("Cache updated with 1 models")


@pytest.mark.asyncio
async def test_store_refreshed_models_keeps_memory_update_on_persistence_failure(cache):
    models = [{"id": "model-a"}]
    updated_at = datetime(2026, 8, 12, 12, 34, 56)
    error = RuntimeError("persistence failed")
    loop = MagicMock()
    loop.run_in_executor = AsyncMock(side_effect=error)

    with patch.object(cache_module, "datetime") as datetime_type, patch.object(
        cache_module.asyncio,
        "get_running_loop",
        return_value=loop,
    ):
        datetime_type.now.return_value = updated_at
        with pytest.raises(RuntimeError) as raised:
            await cache._store_refreshed_models(models)

    assert raised.value is error
    assert cache._memory_cache is models
    assert cache._last_update is updated_at


@pytest.mark.asyncio
async def test_refresh_models_delegates_fetched_models_to_store(cache):
    models = [{"id": "model-a"}]

    with patch.object(
        cache,
        "_fetch_models_from_api",
        return_value=models,
    ) as fetch, patch.object(
        cache,
        "_store_refreshed_models",
        return_value=models,
    ) as store, patch.object(
        cache, "_load_models_from_file_fallback"
    ) as fallback:
        result = await cache._refresh_models()

    assert result is models
    fetch.assert_awaited_once_with()
    store.assert_awaited_once_with(models)
    fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_models_falls_back_with_store_failure(cache):
    models = [{"id": "model-a"}]
    fallback_models = [{"id": "fallback"}]
    error = RuntimeError("store failed")

    with patch.object(
        cache,
        "_fetch_models_from_api",
        return_value=models,
    ), patch.object(
        cache,
        "_store_refreshed_models",
        side_effect=error,
    ), patch.object(
        cache,
        "_load_models_from_file_fallback",
        return_value=fallback_models,
    ) as fallback:
        result = await cache._refresh_models()

    assert result is fallback_models
    fallback.assert_awaited_once_with(error)


@pytest.mark.asyncio
async def test_refresh_models_skips_store_when_fetch_fails(cache):
    fallback_models = [{"id": "fallback"}]
    error = RuntimeError("fetch failed")

    with patch.object(
        cache,
        "_fetch_models_from_api",
        side_effect=error,
    ), patch.object(cache, "_store_refreshed_models") as store, patch.object(
        cache,
        "_load_models_from_file_fallback",
        return_value=fallback_models,
    ) as fallback:
        result = await cache._refresh_models()

    assert result is fallback_models
    store.assert_not_awaited()
    fallback.assert_awaited_once_with(error)
