"""
Tests for test fixture factories.

Ensures fixture factories work correctly and produce valid test data.
"""

from unittest.mock import AsyncMock

import pytest

from .ci_fixtures import (
    ConsensusConfigFactory,
    MockModelProviderFactory,
    OperationalConfigFactory,
    create_processing_results,
    create_sample_models,
    create_sample_task,
)
from .mock_clients import MockClientFactory, MockEnvFactory
from .mock_responses import ResponseFactory, create_mock_response


class TestMockClientFactory:
    """Tests for MockClientFactory."""

    def test_create_httpx_client(self):
        """Should create a valid httpx AsyncMock."""
        client = MockClientFactory.create_httpx_client()
        assert isinstance(client, AsyncMock)

    def test_create_openrouter_client(self):
        """Should create a mock OpenRouter client with correct attributes."""
        client = MockClientFactory.create_openrouter_client()

        assert client.api_key == "sk-or-test-key-123456789"
        assert client.base_url == "https://openrouter.ai/api/v1"
        assert client.timeout == 30.0
        assert client._initialized is True

    def test_create_openrouter_client_custom(self):
        """Should accept custom configuration."""
        client = MockClientFactory.create_openrouter_client(
            api_key="custom-key",
            base_url="https://custom.url",
            timeout=60.0,
        )

        assert client.api_key == "custom-key"
        assert client.base_url == "https://custom.url"
        assert client.timeout == 60.0


class TestMockEnvFactory:
    """Tests for MockEnvFactory."""

    def test_standard_env(self):
        """Should return standard environment variables."""
        env = MockEnvFactory.standard_env()

        assert "OPENROUTER_API_KEY" in env
        assert "OPENROUTER_BASE_URL" in env
        assert "OPENROUTER_APP_NAME" in env
        assert "OPENROUTER_HTTP_REFERER" in env

    def test_minimal_env(self):
        """Should return minimal environment (API key only)."""
        env = MockEnvFactory.minimal_env()

        assert "OPENROUTER_API_KEY" in env
        assert len(env) == 1

    def test_custom_env(self):
        """Should create custom environment configuration."""
        env = MockEnvFactory.custom_env(
            api_key="custom-key",
            base_url="https://custom.url",
            app_name="my-app",
        )

        assert env["OPENROUTER_API_KEY"] == "custom-key"
        assert env["OPENROUTER_BASE_URL"] == "https://custom.url"
        assert env["OPENROUTER_APP_NAME"] == "my-app"


class TestResponseFactory:
    """Tests for ResponseFactory."""

    def test_models_list(self):
        """Should create valid models list response."""
        response = ResponseFactory.models_list()

        assert "data" in response
        assert len(response["data"]) >= 2
        assert "id" in response["data"][0]
        assert "name" in response["data"][0]

    def test_chat_completion(self):
        """Should create valid chat completion response."""
        response = ResponseFactory.chat_completion()

        assert "choices" in response
        assert len(response["choices"]) == 1
        assert "message" in response["choices"][0]
        assert "usage" in response

    def test_chat_completion_custom(self):
        """Should accept custom content and model."""
        response = ResponseFactory.chat_completion(
            content="Custom response",
            model="anthropic/claude-3",
        )

        assert response["choices"][0]["message"]["content"] == "Custom response"
        assert response["model"] == "anthropic/claude-3"

    def test_streaming_chunks(self):
        """Should create valid streaming chunks."""
        chunks = ResponseFactory.streaming_chunks()

        assert len(chunks) >= 3  # At least first, middle, final
        assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
        assert "usage" in chunks[-1]

    def test_error_response(self):
        """Should create valid error response."""
        response = ResponseFactory.error_response()

        assert "error" in response
        assert "type" in response["error"]
        assert "code" in response["error"]
        assert "message" in response["error"]

    def test_rate_limit_error(self):
        """Should create rate limit error response."""
        response = ResponseFactory.rate_limit_error()

        assert response["error"]["type"] == "rate_limit_error"


class TestCreateMockResponse:
    """Tests for create_mock_response function."""

    def test_success_response(self):
        """Should create successful response with JSON data."""
        response = create_mock_response(
            status_code=200,
            json_data={"result": "success"},
        )

        assert response.status_code == 200
        assert response.json() == {"result": "success"}
        response.raise_for_status()  # Should not raise

    def test_error_response(self):
        """Should create error response that raises on raise_for_status."""
        import httpx

        response = create_mock_response(status_code=400)

        assert response.status_code == 400
        with pytest.raises(httpx.HTTPStatusError):
            response.raise_for_status()


class TestCIFixtures:
    """Tests for collective intelligence fixtures."""

    def test_create_sample_models(self):
        """Should create requested number of models."""
        models = create_sample_models(3)

        assert len(models) == 3
        for model in models:
            assert model.model_id
            assert model.name
            assert model.provider

    def test_create_sample_models_many(self):
        """Should generate additional models if needed."""
        models = create_sample_models(10)

        assert len(models) == 10

    def test_create_sample_task(self):
        """Should create valid task context."""
        task = create_sample_task()

        assert task.task_id == "test_task_001"
        assert task.content
        assert task.task_type

    def test_create_sample_task_custom(self):
        """Should accept custom parameters."""
        task = create_sample_task(
            task_id="custom-123",
            content="Custom content",
            priority=10,
        )

        assert task.task_id == "custom-123"
        assert task.content == "Custom content"
        assert task.priority == 10

    def test_create_processing_results(self):
        """Should create valid processing results."""
        results = create_processing_results()

        assert len(results) > 0
        for result in results:
            assert result.task_id
            assert result.model_id
            assert result.content
            assert result.confidence >= 0


class TestMockModelProviderFactory:
    """Tests for MockModelProviderFactory."""

    def test_standard_provider(self):
        """Should create standard mock provider."""
        provider = MockModelProviderFactory.standard()

        assert isinstance(provider, AsyncMock)

    @pytest.mark.asyncio
    async def test_standard_provider_get_models(self):
        """Should return models from standard provider."""
        provider = MockModelProviderFactory.standard()
        models = await provider.get_available_models()

        assert len(models) > 0

    def test_failing_provider(self):
        """Should create failing mock provider."""
        provider = MockModelProviderFactory.failing()

        assert isinstance(provider, AsyncMock)

    def test_performance_provider(self):
        """Should create performance mock provider."""
        provider = MockModelProviderFactory.performance(model_count=20)

        assert isinstance(provider, AsyncMock)


class TestConsensusConfigFactory:
    """Tests for ConsensusConfigFactory."""

    def test_majority_vote(self):
        """Should create majority vote config."""
        from openrouter_mcp.collective_intelligence.consensus_engine import (
            ConsensusStrategy,
        )

        config = ConsensusConfigFactory.majority_vote()

        assert config.strategy == ConsensusStrategy.MAJORITY_VOTE
        assert config.min_models == 3
        assert config.max_models == 5

    def test_weighted_average(self):
        """Should create weighted average config."""
        from openrouter_mcp.collective_intelligence.consensus_engine import (
            ConsensusStrategy,
        )

        config = ConsensusConfigFactory.weighted_average()

        assert config.strategy == ConsensusStrategy.WEIGHTED_AVERAGE

    def test_confidence_threshold(self):
        """Should create confidence threshold config."""
        from openrouter_mcp.collective_intelligence.consensus_engine import (
            ConsensusStrategy,
        )

        config = ConsensusConfigFactory.confidence_threshold()

        assert config.strategy == ConsensusStrategy.CONFIDENCE_THRESHOLD


class TestOperationalConfigFactory:
    """Tests for OperationalConfigFactory."""

    def test_conservative(self):
        """Should create conservative config."""
        config = OperationalConfigFactory.conservative()

        assert config.concurrency.max_concurrent_tasks <= 5
        assert config.quota.max_cost_per_request <= 1.0

    def test_aggressive(self):
        """Should create aggressive config."""
        config = OperationalConfigFactory.aggressive()

        assert config.concurrency.max_concurrent_tasks >= 5

    def test_test_minimal(self):
        """Should create minimal config for testing."""
        config = OperationalConfigFactory.test_minimal()

        assert config.enable_monitoring is False
        assert config.enable_alerting is False
        assert config.storage.enable_auto_cleanup is False
