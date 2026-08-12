from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.openrouter_mcp.models import cache as cache_module
from src.openrouter_mcp.models.cache import ModelCache

pytestmark = pytest.mark.unit


@pytest.fixture
def cache(tmp_path):
    return ModelCache(cache_file=str(tmp_path / "models.json"))


@pytest.mark.asyncio
async def test_enhance_fetched_models_uses_executor_and_preserves_result(cache):
    raw_models = [{"id": "raw"}]
    enhanced_models = [{"id": "enhanced"}]
    loop = MagicMock()
    loop.run_in_executor = AsyncMock(return_value=enhanced_models)

    with patch.object(
        cache_module.asyncio,
        "get_running_loop",
        return_value=loop,
    ) as get_loop, patch.object(cache_module.logger, "info") as log:
        result = await cache._enhance_fetched_models(raw_models)

    assert result is enhanced_models
    get_loop.assert_called_once_with()
    loop.run_in_executor.assert_awaited_once_with(
        cache._executor,
        cache_module.batch_enhance_models,
        raw_models,
    )
    log.assert_called_once_with("Enhanced 1 models with metadata")


@pytest.mark.asyncio
async def test_enhance_fetched_models_logs_before_rejecting_non_list(cache):
    enhanced_models = ({"id": "enhanced"},)
    loop = MagicMock()
    loop.run_in_executor = AsyncMock(return_value=enhanced_models)
    events = []

    with patch.object(
        cache_module.asyncio,
        "get_running_loop",
        return_value=loop,
    ), patch.object(
        cache_module.logger,
        "info",
        side_effect=lambda message: events.append(message),
    ):
        with pytest.raises(ValueError, match="Enhanced model payload must be a list"):
            await cache._enhance_fetched_models([])

    assert events == ["Enhanced 1 models with metadata"]


@pytest.mark.asyncio
async def test_fetch_models_delegates_raw_payload_after_logging(cache):
    raw_models = [{"id": "raw"}]
    enhanced_models = [{"id": "enhanced"}]
    transport = AsyncMock()
    transport.get.return_value = {"data": raw_models}
    cache._transport = transport
    events = []

    async def enhance(received_models):
        events.append("enhance")
        assert received_models is raw_models
        return enhanced_models

    with patch.object(cache, "_ensure_transport") as ensure_transport, patch.object(
        cache,
        "_enhance_fetched_models",
        side_effect=enhance,
    ) as enhance_models, patch.object(
        cache_module.logger,
        "info",
        side_effect=lambda message: events.append(message),
    ):
        result = await cache._fetch_models_from_api()

    assert result is enhanced_models
    ensure_transport.assert_called_once_with()
    transport.get.assert_awaited_once_with("/models")
    enhance_models.assert_awaited_once_with(raw_models)
    assert events == [
        "Fetched 1 models from OpenRouter API (raw)",
        "enhance",
    ]


@pytest.mark.asyncio
async def test_fetch_models_logs_and_propagates_enrichment_failure(cache):
    raw_models = [{"id": "raw"}]
    transport = AsyncMock()
    transport.get.return_value = {"data": raw_models}
    cache._transport = transport
    error = RuntimeError("enrichment failed")

    with patch.object(cache, "_ensure_transport"), patch.object(
        cache,
        "_enhance_fetched_models",
        side_effect=error,
    ), patch.object(cache_module.logger, "error") as log:
        with pytest.raises(RuntimeError) as raised:
            await cache._fetch_models_from_api()

    assert raised.value is error
    log.assert_called_once_with("Failed to fetch models from API: enrichment failed")
