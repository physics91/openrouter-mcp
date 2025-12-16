"""
Mock client factories for DRY-compliant test setup.

This module provides factory classes for creating consistent mock clients
and API stubs across all test modules.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock

import httpx


class MockClientFactory:
    """
    Factory for creating mock HTTP and API clients.

    Provides consistent mock client setup for OpenRouter API testing,
    eliminating duplicate mock configuration across test files.
    """

    @staticmethod
    def create_httpx_client() -> AsyncMock:
        """Create a mock httpx.AsyncClient."""
        return AsyncMock(spec=httpx.AsyncClient)

    @staticmethod
    def create_openrouter_client(
        api_key: str = "sk-or-test-key-123456789",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 30.0,
    ) -> Mock:
        """
        Create a mock OpenRouterClient with common default configuration.

        Args:
            api_key: Mock API key
            base_url: Mock base URL
            timeout: Mock timeout value

        Returns:
            Mock client with standard configuration
        """
        client = AsyncMock()
        client.api_key = api_key
        client.base_url = base_url
        client.timeout = timeout
        client._initialized = True

        # Standard async methods
        client.list_models = AsyncMock(return_value=[])
        client.chat_completion = AsyncMock(return_value={})
        client.stream_chat_completion = AsyncMock()
        client.close = AsyncMock()

        return client

    @staticmethod
    def create_model_provider_mock(
        models: Optional[List[Any]] = None,
        process_results: Optional[Dict[str, Any]] = None,
    ) -> AsyncMock:
        """
        Create a mock ModelProvider for collective intelligence tests.

        Args:
            models: List of ModelInfo objects to return from get_available_models
            process_results: Dict mapping model_id to ProcessingResult

        Returns:
            Mock ModelProvider with configured behavior
        """
        from openrouter_mcp.collective_intelligence.base import ModelProvider

        provider = AsyncMock(spec=ModelProvider)
        provider.get_available_models.return_value = models or []

        if process_results:
            async def mock_process_task(task, model_id, **kwargs):
                if model_id in process_results:
                    result = process_results[model_id]
                    result.task_id = task.task_id
                    return result
                raise ValueError(f"Model {model_id} not found in mock results")

            provider.process_task.side_effect = mock_process_task
        else:
            provider.process_task.return_value = None

        return provider

    @staticmethod
    def create_failing_model_provider() -> AsyncMock:
        """
        Create a mock ModelProvider that simulates failures.

        Useful for testing error handling and circuit breaker behavior.

        Returns:
            Mock ModelProvider that raises errors
        """
        import asyncio
        from openrouter_mcp.collective_intelligence.base import ModelProvider

        provider = AsyncMock(spec=ModelProvider)
        provider.get_available_models.return_value = []

        async def mock_failing_process_task(task, model_id, **kwargs):
            if "timeout" in model_id:
                raise asyncio.TimeoutError("Model timeout")
            elif "error" in model_id:
                raise ValueError("Invalid request")
            else:
                raise Exception("Unexpected error")

        provider.process_task.side_effect = mock_failing_process_task
        return provider


class MockEnvFactory:
    """
    Factory for mock environment variable configurations.

    Provides consistent environment setup for testing different
    configuration scenarios.
    """

    @staticmethod
    def standard_env() -> Dict[str, str]:
        """Get standard environment variables for testing."""
        return {
            "OPENROUTER_API_KEY": "sk-or-test-key-123456789",
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
            "OPENROUTER_APP_NAME": "test-app",
            "OPENROUTER_HTTP_REFERER": "https://test.com",
        }

    @staticmethod
    def minimal_env() -> Dict[str, str]:
        """Get minimal environment variables (API key only)."""
        return {
            "OPENROUTER_API_KEY": "sk-or-test-key-123456789",
        }

    @staticmethod
    def custom_env(
        api_key: str = "sk-or-custom-key",
        base_url: Optional[str] = None,
        app_name: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Create custom environment variable configuration.

        Args:
            api_key: Custom API key
            base_url: Optional custom base URL
            app_name: Optional custom app name

        Returns:
            Environment variables dictionary
        """
        env = {"OPENROUTER_API_KEY": api_key}
        if base_url:
            env["OPENROUTER_BASE_URL"] = base_url
        if app_name:
            env["OPENROUTER_APP_NAME"] = app_name
        return env


__all__ = ["MockClientFactory", "MockEnvFactory"]
