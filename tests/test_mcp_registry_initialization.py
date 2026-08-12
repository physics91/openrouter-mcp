import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.openrouter_mcp import mcp_registry as registry
from src.openrouter_mcp.client import openrouter as openrouter_module
from src.openrouter_mcp.config.constants import APIConfig, CacheConfig, EnvVars

pytestmark = pytest.mark.unit


def _reset_client_state(monkeypatch):
    monkeypatch.setattr(registry, "_client_instance", None)
    monkeypatch.setattr(registry, "_client_initialized", False)
    monkeypatch.setattr(registry, "_client_loop", None)


@pytest.mark.asyncio
async def test_initialize_shared_client_preserves_construction_and_state_order(
    monkeypatch,
):
    _reset_client_state(monkeypatch)
    current_loop = asyncio.get_running_loop()
    client = MagicMock()

    async def enter_client():
        assert registry._client_instance is client
        assert registry._client_initialized is False
        assert registry._client_loop is None
        return client

    client.__aenter__ = AsyncMock(side_effect=enter_client)
    values = {
        EnvVars.BASE_URL: "https://example.test/api/v1",
        EnvVars.APP_NAME: "test-app",
        EnvVars.HTTP_REFERER: "https://example.test",
    }

    with patch.object(
        openrouter_module,
        "OpenRouterClient",
        return_value=client,
    ) as constructor, patch.object(
        registry,
        "get_env_value",
        side_effect=lambda name, default=None: values.get(name, default),
    ) as get_env, patch.object(
        registry, "get_required_env"
    ) as get_required:
        result = await registry._initialize_shared_client(current_loop, "env-key")

    assert result is client
    constructor.assert_called_once_with(
        api_key="env-key",
        base_url="https://example.test/api/v1",
        app_name="test-app",
        http_referer="https://example.test",
        enable_cache=True,
        cache_ttl=CacheConfig.DEFAULT_TTL_SECONDS,
    )
    get_env.assert_has_calls(
        [
            call(EnvVars.BASE_URL, APIConfig.BASE_URL),
            call(EnvVars.APP_NAME),
            call(EnvVars.HTTP_REFERER),
        ]
    )
    assert get_env.call_count == 3
    get_required.assert_not_called()
    client.__aenter__.assert_awaited_once_with()
    assert registry._client_instance is client
    assert registry._client_initialized is True
    assert registry._client_loop is current_loop


@pytest.mark.asyncio
async def test_initialize_shared_client_preserves_partial_state_on_enter_failure(
    monkeypatch,
):
    _reset_client_state(monkeypatch)
    current_loop = asyncio.get_running_loop()
    error = RuntimeError("enter failed")
    client = MagicMock()
    client.__aenter__ = AsyncMock(side_effect=error)

    with patch.object(
        openrouter_module,
        "OpenRouterClient",
        return_value=client,
    ), patch.object(
        registry,
        "get_env_value",
        return_value=None,
    ):
        with pytest.raises(RuntimeError) as raised:
            await registry._initialize_shared_client(current_loop, "env-key")

    assert raised.value is error
    assert registry._client_instance is client
    assert registry._client_initialized is False
    assert registry._client_loop is None


@pytest.mark.asyncio
async def test_initialize_shared_client_resolves_required_key_when_snapshot_missing(
    monkeypatch,
):
    _reset_client_state(monkeypatch)
    current_loop = asyncio.get_running_loop()
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)

    with patch.object(
        openrouter_module,
        "OpenRouterClient",
        return_value=client,
    ) as constructor, patch.object(
        registry,
        "get_env_value",
        return_value=None,
    ), patch.object(
        registry,
        "get_required_env",
        return_value="required-key",
    ) as get_required:
        result = await registry._initialize_shared_client(current_loop, None)

    assert result is client
    get_required.assert_called_once_with(EnvVars.API_KEY)
    assert constructor.call_args.kwargs["api_key"] == "required-key"


@pytest.mark.asyncio
async def test_get_shared_client_delegates_slow_path_initialization(monkeypatch):
    _reset_client_state(monkeypatch)
    current_loop = asyncio.get_running_loop()
    client = MagicMock()
    initialize = AsyncMock(return_value=client)
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    monkeypatch.setattr(registry, "_client_lock", asyncio.Lock())

    with patch.object(registry, "_initialize_shared_client", initialize):
        result = await registry.get_shared_client()

    assert result is client
    initialize.assert_awaited_once_with(current_loop, "env-key")
