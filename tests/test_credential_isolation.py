#!/usr/bin/env python3
"""
Test credential isolation in ModelCache and OpenRouterClient.

Verifies that multiple clients with different credentials don't interfere
with each other, and that credential threading works correctly.
"""

from unittest.mock import patch

import pytest

from src.openrouter_mcp.client.openrouter import OpenRouterClient
from src.openrouter_mcp.models.cache import ModelCache
from tests.fixtures.httpx_mocks import setup_async_client_mock


class TestCredentialIsolation:
    """Test credential isolation between multiple clients and caches."""

    @pytest.fixture
    def mock_models_response(self):
        """Mock API response for models."""
        return {
            "data": [
                {
                    "id": "openai/gpt-4",
                    "name": "GPT-4",
                    "description": "OpenAI GPT-4",
                    "context_length": 8192,
                    "pricing": {"prompt": "0.00003", "completion": "0.00006"},
                    "architecture": {"modality": "text"},
                    "top_provider": {"provider": "OpenAI"},
                }
            ]
        }

    @pytest.mark.unit
    def test_modelcache_accepts_credentials(self):
        """Test that ModelCache accepts api_key and base_url parameters."""
        cache = ModelCache(
            ttl_hours=1,
            api_key="test-api-key",
            base_url="https://test.openrouter.ai/api/v1",
        )

        assert cache._api_key == "test-api-key"
        assert cache._base_url == "https://test.openrouter.ai/api/v1"

    @pytest.mark.unit
    def test_modelcache_credentials_fallback_to_none(self):
        """Test that ModelCache credentials default to None when not provided."""
        cache = ModelCache(ttl_hours=1)

        assert cache._api_key is None
        assert cache._base_url is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_modelcache_uses_provided_credentials(self, mock_models_response):
        """Test that ModelCache uses provided credentials over environment vars."""
        cache = ModelCache(
            ttl_hours=1,
            api_key="cache-specific-key",
            base_url="https://cache-specific.url/api/v1",
        )

        # Set environment variables to different values
        with patch.dict(
            "os.environ",
            {
                "OPENROUTER_API_KEY": "env-key",
                "OPENROUTER_BASE_URL": "https://env.url/api/v1",
            },
        ):
            with patch("httpx.AsyncClient") as mock_httpx_client:
                _, _, captured_headers = setup_async_client_mock(
                    mock_httpx_client,
                    mock_models_response,
                    capture_headers=True,
                )

                # Fetch models
                await cache._fetch_models_from_api()

                # Verify that cache-specific credentials were used, not env vars
                assert captured_headers["Authorization"] == "Bearer cache-specific-key"
                # Verify URL contains cache-specific base URL
                # (checked via the URL passed to httpx, but in this mock we track headers)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_modelcache_falls_back_to_env_credentials(self, mock_models_response):
        """Test that ModelCache falls back to environment variables when credentials not provided."""
        cache = ModelCache(ttl_hours=1)

        with patch.dict(
            "os.environ",
            {
                "OPENROUTER_API_KEY": "env-fallback-key",
                "OPENROUTER_BASE_URL": "https://env-fallback.url/api/v1",
            },
        ):
            with patch("httpx.AsyncClient") as mock_httpx_client:
                _, _, captured_headers = setup_async_client_mock(
                    mock_httpx_client,
                    mock_models_response,
                    capture_headers=True,
                )

                await cache._fetch_models_from_api()

                # Verify environment credentials were used
                assert captured_headers["Authorization"] == "Bearer env-fallback-key"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_modelcache_raises_error_without_credentials(self):
        """Test that ModelCache raises error when no credentials are available."""
        cache = ModelCache(ttl_hours=1)

        # Clear environment variables
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="API key is required"):
                await cache._fetch_models_from_api()

    @pytest.mark.unit
    def test_openrouter_client_passes_credentials_to_cache(self):
        """Test that OpenRouterClient passes its credentials to ModelCache."""
        client = OpenRouterClient(
            api_key="client-api-key",
            base_url="https://client.url/api/v1",
            enable_cache=True,
        )

        assert client._model_cache is not None
        assert client._model_cache._api_key == "client-api-key"
        assert client._model_cache._base_url == "https://client.url/api/v1"

    @pytest.mark.unit
    def test_openrouter_client_cache_disabled(self):
        """Test that OpenRouterClient doesn't create cache when disabled."""
        client = OpenRouterClient(api_key="client-api-key", enable_cache=False)

        assert client._model_cache is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multiple_clients_credential_isolation(self, mock_models_response):
        """Test that multiple OpenRouterClients with different credentials are isolated."""
        client1 = OpenRouterClient(
            api_key="client1-key",
            base_url="https://client1.url/api/v1",
            enable_cache=True,
        )

        client2 = OpenRouterClient(
            api_key="client2-key",
            base_url="https://client2.url/api/v1",
            enable_cache=True,
        )

        # Verify each client has its own cache with its own credentials
        assert client1._model_cache._api_key == "client1-key"
        assert client1._model_cache._base_url == "https://client1.url/api/v1"

        assert client2._model_cache._api_key == "client2-key"
        assert client2._model_cache._base_url == "https://client2.url/api/v1"

        # Verify they are different instances
        assert client1._model_cache is not client2._model_cache

        await client1.close()
        await client2.close()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_programmatic_credential_passing(self, mock_models_response):
        """Test that credentials can be passed programmatically without environment."""
        # Clear environment to ensure no fallback
        with patch.dict("os.environ", {}, clear=True):
            client = OpenRouterClient(
                api_key="programmatic-key",
                base_url="https://programmatic.url/api/v1",
                enable_cache=True,
            )

            # Verify cache has the programmatic credentials
            assert client._model_cache._api_key == "programmatic-key"
            assert client._model_cache._base_url == "https://programmatic.url/api/v1"

            # Mock the API call
            with patch("httpx.AsyncClient") as mock_httpx_client:
                _, _, captured_headers = setup_async_client_mock(
                    mock_httpx_client,
                    mock_models_response,
                    capture_headers=True,
                )

                # Trigger cache refresh
                await client._model_cache.get_models(force_refresh=True)

                # Verify programmatic credentials were used
                assert captured_headers["Authorization"] == "Bearer programmatic-key"

            await client.close()

    @pytest.mark.unit
    def test_backward_compatibility_without_credentials(self):
        """Test backward compatibility - ModelCache works without explicit credentials."""
        # This should not raise an error during initialization
        cache = ModelCache(ttl_hours=1)

        # Credentials should be None
        assert cache._api_key is None
        assert cache._base_url is None

        # The cache will fall back to environment variables when fetching

    @pytest.mark.unit
    def test_openrouter_client_from_env_backward_compatible(self):
        """Test that OpenRouterClient.from_env() still works and passes credentials to cache."""
        with patch.dict(
            "os.environ",
            {
                "OPENROUTER_API_KEY": "env-test-key",
                "OPENROUTER_BASE_URL": "https://env-test.url/api/v1",
            },
        ):
            client = OpenRouterClient.from_env()

            # Client should have env credentials
            assert client.api_key == "env-test-key"
            assert client.base_url == "https://env-test.url/api/v1"

            # Cache should have the same credentials
            assert client._model_cache._api_key == "env-test-key"
            assert client._model_cache._base_url == "https://env-test.url/api/v1"


class TestTestIsolation:
    """Test that tests can use different credentials without process environment pollution."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_isolation_scenario_1(self, mock_models_response):
        """Test scenario 1 with specific credentials."""
        cache = ModelCache(
            ttl_hours=1, api_key="test1-key", base_url="https://test1.url/api/v1"
        )

        assert cache._api_key == "test1-key"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_isolation_scenario_2(self, mock_models_response):
        """Test scenario 2 with different credentials - should not affect scenario 1."""
        cache = ModelCache(
            ttl_hours=1, api_key="test2-key", base_url="https://test2.url/api/v1"
        )

        assert cache._api_key == "test2-key"
        # This test should pass regardless of what test_isolation_scenario_1 did

    @pytest.fixture
    def mock_models_response(self):
        """Mock API response for models."""
        return {
            "data": [
                {
                    "id": "openai/gpt-4",
                    "name": "GPT-4",
                    "description": "OpenAI GPT-4",
                    "context_length": 8192,
                    "pricing": {"prompt": "0.00003", "completion": "0.00006"},
                    "architecture": {"modality": "text"},
                    "top_provider": {"provider": "OpenAI"},
                }
            ]
        }
