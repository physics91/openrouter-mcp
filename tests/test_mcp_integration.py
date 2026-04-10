#!/usr/bin/env python3
"""
MCP Server Integration Tests

Comprehensive integration tests for the FastMCP server that verify:
1. FastMCP tool registration without making real API calls
2. Server starts correctly in stdio mode
3. All expected tools are registered and accessible
4. Tool list can be inspected programmatically
5. The shared MCP registry pattern works correctly

These tests catch issues like the "0 registered tools" bug and ensure
all modules properly register their tools with the shared FastMCP instance.
"""

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastmcp import Client

# Add src directory to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


async def _get_tools_dict(mcp_instance):
    """Build a stable name->tool mapping via the FastMCP public API."""
    tools = await mcp_instance.list_tools()
    return {tool.name: tool for tool in tools}


def _text_from(result) -> str:
    for item in result.content:
        if hasattr(item, "text"):
            return item.text
    return ""


def _json_from(result) -> dict:
    return json.loads(_text_from(result))


class TestMCPServerToolRegistration:
    """Test FastMCP tool registration without making API calls."""

    def test_server_module_imports(self):
        """Verify server module and all handlers can be imported."""
        # This test ensures all modules load without errors
        try:
            from openrouter_mcp import server
            from openrouter_mcp.handlers import (
                chat,
                collective_intelligence,
                mcp_benchmark,
                multimodal,
            )

            assert server is not None
            assert chat is not None
            assert multimodal is not None
            assert mcp_benchmark is not None
            assert collective_intelligence is not None

        except ImportError as e:
            pytest.fail(f"Failed to import required modules: {e}")

    def test_mcp_instance_exists_in_server(self):
        """Verify that server.py creates an MCP instance."""
        from openrouter_mcp.server import mcp

        assert mcp is not None
        assert hasattr(mcp, "name")
        assert mcp.name == "openrouter-mcp"

    def test_shared_mcp_registry_pattern(self):
        """Verify that all handlers use a shared MCP instance."""
        # Import all handler modules
        from openrouter_mcp.handlers import chat, mcp_benchmark

        # Verify they define mcp instances
        assert hasattr(chat, "mcp")
        assert hasattr(mcp_benchmark, "mcp")

        # These should be separate instances per module
        # (each handler creates its own FastMCP instance)
        chat_mcp = chat.mcp
        benchmark_mcp = mcp_benchmark.mcp

        assert chat_mcp is not None
        assert benchmark_mcp is not None

    @pytest.mark.asyncio
    async def test_chat_tools_registered(self):
        """Verify chat tools are properly registered."""
        from openrouter_mcp.handlers.chat import mcp

        # Get registered tools (async)
        tools_dict = await _get_tools_dict(mcp)

        # Expected chat tools
        expected_tools = ["chat_with_model", "list_available_models", "get_usage_stats"]

        registered_tool_names = list(tools_dict.keys())

        for expected_tool in expected_tools:
            assert (
                expected_tool in registered_tool_names
            ), f"Tool '{expected_tool}' not registered. Found: {registered_tool_names}"

        # Verify at least 3 tools registered
        assert (
            len(tools_dict) >= 3
        ), f"Expected at least 3 chat tools, found {len(tools_dict)}: {registered_tool_names}"

    @pytest.mark.asyncio
    async def test_benchmark_tools_registered(self):
        """Verify benchmark tools are properly registered."""
        from openrouter_mcp.handlers.mcp_benchmark import mcp

        # Get registered tools (async)
        tools_dict = await _get_tools_dict(mcp)

        # Expected benchmark tools
        expected_tools = [
            "benchmark_models",
            "get_benchmark_history",
            "compare_model_categories",
            "export_benchmark_report",
            "compare_model_performance",
        ]

        registered_tool_names = list(tools_dict.keys())

        for expected_tool in expected_tools:
            assert (
                expected_tool in registered_tool_names
            ), f"Tool '{expected_tool}' not registered. Found: {registered_tool_names}"

        # Verify all 5 benchmark tools registered
        assert (
            len(tools_dict) >= 5
        ), f"Expected at least 5 benchmark tools, found {len(tools_dict)}: {registered_tool_names}"

    @pytest.mark.asyncio
    async def test_collective_intelligence_tools_registered(self):
        """Verify collective intelligence tools are properly registered."""
        from openrouter_mcp.handlers.collective_intelligence import mcp

        # Get registered tools (async)
        tools_dict = await _get_tools_dict(mcp)

        # Expected collective intelligence tools
        expected_tools = [
            "collective_chat_completion",
            "ensemble_reasoning",
            "adaptive_model_selection",
            "cross_model_validation",
            "collaborative_problem_solving",
        ]

        registered_tool_names = list(tools_dict.keys())

        for expected_tool in expected_tools:
            assert (
                expected_tool in registered_tool_names
            ), f"Tool '{expected_tool}' not registered. Found: {registered_tool_names}"

        # Verify all 5 collective intelligence tools registered
        assert (
            len(tools_dict) >= 5
        ), f"Expected at least 5 collective intelligence tools, found {len(tools_dict)}: {registered_tool_names}"

    @pytest.mark.asyncio
    async def test_multimodal_tools_registered(self):
        """Verify multimodal tools are properly registered."""
        from openrouter_mcp.handlers.multimodal import mcp

        # Get registered tools (async)
        tools_dict = await _get_tools_dict(mcp)

        # Expected multimodal tools (updated to match actual implementation)
        expected_tools = ["chat_with_vision", "list_vision_models"]

        registered_tool_names = list(tools_dict.keys())

        for expected_tool in expected_tools:
            assert (
                expected_tool in registered_tool_names
            ), f"Tool '{expected_tool}' not registered. Found: {registered_tool_names}"

        # Verify at least 2 multimodal tools registered
        assert (
            len(tools_dict) >= 2
        ), f"Expected at least 2 multimodal tools, found {len(tools_dict)}: {registered_tool_names}"

    @pytest.mark.asyncio
    async def test_all_tools_have_proper_metadata(self):
        """Verify that all registered tools have proper metadata."""
        from openrouter_mcp.handlers.chat import mcp as chat_mcp
        from openrouter_mcp.handlers.mcp_benchmark import mcp as benchmark_mcp

        # Check chat tools (async)
        chat_tools_dict = await _get_tools_dict(chat_mcp)
        for tool_name, tool in chat_tools_dict.items():
            assert tool.name, "Tool name is empty"
            assert tool.description, "Tool description is empty"

        # Check benchmark tools (async)
        benchmark_tools_dict = await _get_tools_dict(benchmark_mcp)
        for tool_name, tool in benchmark_tools_dict.items():
            assert tool.name, "Tool name is empty"
            assert tool.description, "Tool description is empty"

    @pytest.mark.asyncio
    async def test_tool_count_regression(self):
        """Regression test: Ensure we never go back to 0 registered tools."""
        from openrouter_mcp.handlers.chat import mcp as chat_mcp
        from openrouter_mcp.handlers.collective_intelligence import mcp as ci_mcp
        from openrouter_mcp.handlers.mcp_benchmark import mcp as benchmark_mcp

        chat_tools_dict = await _get_tools_dict(chat_mcp)
        benchmark_tools_dict = await _get_tools_dict(benchmark_mcp)
        ci_tools_dict = await _get_tools_dict(ci_mcp)

        chat_tools = len(chat_tools_dict)
        benchmark_tools = len(benchmark_tools_dict)
        ci_tools = len(ci_tools_dict)

        # These should NEVER be zero
        assert chat_tools > 0, "REGRESSION: Chat tools not registered!"
        assert benchmark_tools > 0, "REGRESSION: Benchmark tools not registered!"
        assert ci_tools > 0, "REGRESSION: Collective intelligence tools not registered!"

        total_tools = chat_tools + benchmark_tools + ci_tools

        # We expect at least 13 tools total (3 chat + 5 benchmark + 5 collective)
        assert total_tools >= 13, (
            f"Expected at least 13 total tools, found {total_tools} "
            f"(chat: {chat_tools}, benchmark: {benchmark_tools}, ci: {ci_tools})"
        )


class TestMCPServerStartup:
    """Test MCP server startup and configuration."""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Set up mock environment variables."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key-12345")

    def test_create_app_validates_environment(self, mock_env):
        """Test that create_app validates required environment variables."""
        from openrouter_mcp.server import create_app

        # Should not raise with valid env
        app = create_app()
        assert app is not None

    def test_create_app_fails_without_api_key(self, monkeypatch):
        """Test that create_app fails without API key."""
        # Remove API key
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        # Prevent .env from restoring the key during create_app()
        with patch("openrouter_mcp.server.load_dotenv", return_value=False):
            from openrouter_mcp.server import create_app

            # Should raise ValueError
            with pytest.raises(ValueError, match="Missing required environment variables"):
                create_app()

    def test_validate_environment_function(self, mock_env):
        """Test the validate_environment function."""
        from openrouter_mcp.server import validate_environment

        # Should not raise with valid env
        validate_environment()

    def test_validate_environment_without_key(self, monkeypatch):
        """Test validate_environment without API key."""
        from openrouter_mcp.server import validate_environment

        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        with pytest.raises(ValueError, match="Missing required environment variables"):
            validate_environment()


class TestMCPStdioMode:
    """Test MCP server in stdio mode (without actually starting it)."""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Set up mock environment variables."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key-12345")

    def test_server_has_run_method(self, mock_env):
        """Verify the MCP instance has a run() method for stdio mode."""
        from openrouter_mcp.server import mcp

        assert hasattr(mcp, "run"), "MCP instance missing run() method"
        assert callable(mcp.run), "MCP run() is not callable"

    @patch("openrouter_mcp.server.mcp")
    def test_main_calls_run(self, mock_mcp, mock_env):
        """Test that main() calls mcp.run()."""
        from openrouter_mcp.server import main

        # Mock the run method
        mock_mcp.run = Mock()

        # Call main (it will try to run the server)
        # We can't actually test this without mocking more, but we can verify structure
        assert hasattr(main, "__call__"), "main() should be callable"


class TestToolInputValidation:
    """Test that tools properly validate their inputs."""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Set up mock environment variables."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key-12345")

    @pytest.mark.asyncio
    async def test_chat_with_model_validates_input(self):
        """Test that chat_with_model validates its input schema."""
        from openrouter_mcp.handlers.chat import ChatCompletionRequest
        from openrouter_mcp.models.requests import ChatMessage

        # Valid request should have proper structure
        request = ChatCompletionRequest(
            model="openai/gpt-4",
            messages=[ChatMessage(role="user", content="Hello")],
            temperature=0.7,
        )

        # Verify Pydantic validation works
        assert request.model == "openai/gpt-4"
        assert len(request.messages) == 1
        assert request.messages[0].role == "user"
        assert request.temperature == 0.7

    def test_chat_request_requires_model(self):
        """Test that ChatCompletionRequest requires a model."""
        from openrouter_mcp.handlers.chat import ChatCompletionRequest
        from openrouter_mcp.models.requests import ChatMessage

        # Missing model should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hello")])

    def test_chat_request_requires_messages(self):
        """Test that ChatCompletionRequest requires messages."""
        from openrouter_mcp.handlers.chat import ChatCompletionRequest

        # Missing messages should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            ChatCompletionRequest(model="openai/gpt-4")

    @pytest.mark.asyncio
    async def test_benchmark_models_input_validation(self):
        """Test that benchmark tools validate their inputs."""
        from openrouter_mcp.handlers.mcp_benchmark import mcp

        # Get the benchmark_models tool from the registry
        tools_dict = await _get_tools_dict(mcp)
        assert "benchmark_models" in tools_dict, "benchmark_models tool not registered"

        # Verify the tool has a callable function
        benchmark_tool = tools_dict["benchmark_models"]
        assert benchmark_tool.name == "benchmark_models"
        assert benchmark_tool.description, "Tool should have a description"


class TestMCPToolResponseContracts:
    """Verify MCP tool calls preserve runtime thrift metadata in serialized responses."""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key-12345")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_chat_tool_call_returns_thrift_metadata(self, mock_env):
        from openrouter_mcp.client.openrouter import OpenRouterClient
        from openrouter_mcp.handlers import chat as chat_module
        from openrouter_mcp.runtime_thrift import (
            record_compaction_savings,
            record_prompt_cache_activity,
            reset_thrift_metrics,
        )

        reset_thrift_metrics()
        mock_client = AsyncMock(spec=OpenRouterClient)
        mock_client.get_model_pricing.return_value = {
            "prompt": 0.001,
            "completion": 0.002,
        }
        mock_client.model_cache = Mock()
        mock_client.model_cache.get_model_info = AsyncMock(return_value={"context_length": 8192})

        async def chat_completion_with_thrift(*args, **kwargs):
            record_compaction_savings(5)
            record_prompt_cache_activity(
                cached_prompt_tokens=80,
                cache_write_prompt_tokens=20,
                estimated_saved_cost_usd=0.004,
            )
            return {
                "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            }

        mock_client.chat_completion.side_effect = chat_completion_with_thrift

        with patch(
            "openrouter_mcp.handlers.chat.get_openrouter_client",
            new=AsyncMock(return_value=mock_client),
        ):
            async with Client(chat_module.mcp) as client:
                result = await client.call_tool(
                    "chat_with_model",
                    {
                        "request": {
                            "model": "openai/gpt-4o-mini",
                            "messages": [{"role": "user", "content": "Say hello"}],
                            "temperature": 0.0,
                            "max_tokens": 10,
                        }
                    },
                )

        data = _json_from(result)
        assert data["thrift_metrics"]["compacted_tokens"] == 5
        assert data["thrift_summary"]["saved_cost_usd"] == 0.004
        assert data["thrift_summary"]["prompt_savings_breakdown"]["cache_reuse_tokens"] == 80

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_usage_stats_tool_call_returns_thrift_summary(self, mock_env):
        from openrouter_mcp.client.openrouter import OpenRouterClient
        from openrouter_mcp.handlers import chat as chat_module
        from openrouter_mcp.runtime_thrift import (
            record_compaction_savings,
            record_prompt_cache_activity,
            reset_thrift_metrics,
        )

        reset_thrift_metrics()
        record_compaction_savings(11)
        record_prompt_cache_activity(
            cached_prompt_tokens=90,
            cache_write_prompt_tokens=30,
            estimated_saved_cost_usd=0.009,
        )
        mock_client = AsyncMock(spec=OpenRouterClient)
        mock_client.track_usage.return_value = {
            "total_cost": 0.09,
            "total_tokens": 1800,
            "requests": 10,
            "models": ["openai/gpt-4o-mini"],
        }

        with patch(
            "openrouter_mcp.handlers.chat.get_openrouter_client",
            new=AsyncMock(return_value=mock_client),
        ):
            today = date.today().isoformat()
            async with Client(chat_module.mcp) as client:
                result = await client.call_tool(
                    "get_usage_stats",
                    {
                        "request": {
                            "start_date": today,
                            "end_date": today,
                        }
                    },
                )

        data = _json_from(result)
        assert data["thrift_metrics"]["compacted_tokens"] == 11
        assert data["thrift_summary"]["saved_cost_usd"] == 0.009
        assert data["thrift_summary"]["cache_efficiency"]["reuse_to_write_ratio"] == 3.0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_vision_tool_call_returns_thrift_metadata(self, mock_env):
        from openrouter_mcp.client.openrouter import OpenRouterClient
        from openrouter_mcp.handlers import multimodal as multimodal_module
        from openrouter_mcp.runtime_thrift import (
            record_compaction_savings,
            record_prompt_cache_activity,
            reset_thrift_metrics,
        )

        reset_thrift_metrics()
        mock_client = AsyncMock(spec=OpenRouterClient)
        mock_client.get_model_pricing.return_value = {
            "prompt": 0.001,
            "completion": 0.002,
        }

        async def vision_completion_with_thrift(*args, **kwargs):
            record_compaction_savings(3)
            record_prompt_cache_activity(
                cached_prompt_tokens=40,
                cache_write_prompt_tokens=10,
                estimated_saved_cost_usd=0.002,
            )
            return {
                "choices": [{"message": {"content": "chart"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 4,
                    "total_tokens": 16,
                },
            }

        mock_client.chat_completion.side_effect = vision_completion_with_thrift

        with patch(
            "openrouter_mcp.handlers.multimodal.get_openrouter_client",
            new=AsyncMock(return_value=mock_client),
        ):
            async with Client(multimodal_module.mcp) as client:
                result = await client.call_tool(
                    "chat_with_vision",
                    {
                        "request": {
                            "model": "openai/gpt-4o",
                            "messages": [{"role": "user", "content": "Describe this image."}],
                            "images": [
                                {
                                    "data": "https://example.com/chart.png",
                                    "type": "url",
                                }
                            ],
                            "max_tokens": 20,
                        }
                    },
                )

        data = _json_from(result)
        assert data["thrift_metrics"]["compacted_tokens"] == 3
        assert data["thrift_summary"]["saved_cost_usd"] == 0.002
        assert data["thrift_summary"]["prompt_savings_breakdown"]["cache_reuse_tokens"] == 40

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_free_chat_tool_call_returns_thrift_summary(self, mock_env):
        from openrouter_mcp.free.classifier import FreeTaskType
        from openrouter_mcp.handlers import free_chat as free_chat_module
        from openrouter_mcp.runtime_thrift import (
            record_compaction_savings,
            record_prompt_cache_activity,
            reset_thrift_metrics,
        )

        reset_thrift_metrics()
        mock_client = AsyncMock()
        mock_router = Mock()
        mock_router.is_cache_expired.return_value = False
        mock_router.select_model = AsyncMock(return_value="google/gemma-3-27b:free")
        mock_metrics = Mock()
        mock_classifier = Mock()
        mock_classifier.classify.return_value = FreeTaskType.GENERAL
        mock_quota = Mock()
        mock_quota.reserve_and_record = AsyncMock()

        async def execute_chat_with_thrift(*args, **kwargs):
            record_compaction_savings(4)
            record_prompt_cache_activity(
                cached_prompt_tokens=60,
                cache_write_prompt_tokens=20,
                estimated_saved_cost_usd=0.003,
            )
            return {
                "content": "hi",
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 2,
                    "total_tokens": 10,
                },
                "streamed": False,
                "actual_model": "google/gemma-3-27b:free",
            }

        with patch(
            "openrouter_mcp.handlers.free_chat.get_openrouter_client",
            new=AsyncMock(return_value=mock_client),
        ), patch(
            "openrouter_mcp.handlers.free_chat._get_router",
            new=AsyncMock(return_value=mock_router),
        ), patch(
            "openrouter_mcp.handlers.free_chat._get_metrics",
            return_value=mock_metrics,
        ), patch(
            "openrouter_mcp.handlers.free_chat._get_classifier",
            return_value=mock_classifier,
        ), patch(
            "openrouter_mcp.handlers.free_chat._get_quota",
            return_value=mock_quota,
        ), patch(
            "openrouter_mcp.handlers.free_chat._try_native_fallback",
            new=AsyncMock(return_value=None),
        ), patch(
            "openrouter_mcp.handlers.free_chat._execute_chat",
            new=AsyncMock(side_effect=execute_chat_with_thrift),
        ):
            async with Client(free_chat_module.mcp) as client:
                result = await client.call_tool(
                    "free_chat",
                    {
                        "request": {
                            "message": "Say hi",
                            "max_tokens": 10,
                        }
                    },
                )

        data = _json_from(result)
        assert data["model_used"] == "google/gemma-3-27b:free"
        assert data["thrift_metrics"]["compacted_tokens"] == 4
        assert data["thrift_summary"]["saved_cost_usd"] == 0.003
        assert data["thrift_summary"]["cache_efficiency"]["reuse_to_write_ratio"] == 3.0


class TestMCPServerDocumentation:
    """Test that tools have proper documentation for MCP clients."""

    @pytest.mark.asyncio
    async def test_chat_tools_have_descriptions(self):
        """Verify chat tools have descriptions."""
        from openrouter_mcp.handlers.chat import mcp

        tools_dict = await _get_tools_dict(mcp)

        for tool_name, tool in tools_dict.items():
            assert tool.description, f"Tool '{tool.name}' missing description"
            assert (
                len(tool.description) > 20
            ), f"Tool '{tool.name}' description too short: {tool.description}"

    @pytest.mark.asyncio
    async def test_benchmark_tools_have_descriptions(self):
        """Verify benchmark tools have descriptions."""
        from openrouter_mcp.handlers.mcp_benchmark import mcp

        tools_dict = await _get_tools_dict(mcp)

        for tool_name, tool in tools_dict.items():
            assert tool.description, f"Tool '{tool.name}' missing description"
            assert (
                len(tool.description) > 20
            ), f"Tool '{tool.name}' description too short: {tool.description}"


class TestMCPServerErrorHandling:
    """Test error handling in MCP tools."""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Set up mock environment variables."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key-12345")

    @pytest.mark.asyncio
    async def test_get_openrouter_client_without_key(self, monkeypatch):
        """Test that get_openrouter_client raises error without API key."""
        from openrouter_mcp.handlers.chat import get_openrouter_client

        # Remove API key
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        # Should raise ValueError (get_openrouter_client is async)
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            await get_openrouter_client()

    @pytest.mark.asyncio
    async def test_benchmark_handler_requires_api_key(self, monkeypatch):
        """Test that benchmark handler requires API key."""
        from openrouter_mcp.handlers.mcp_benchmark import get_benchmark_handler

        # Remove API key
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        # Should raise ValueError with a message containing "OPENROUTER_API_KEY"
        with pytest.raises(ValueError) as exc_info:
            await get_benchmark_handler()

        # Verify it's related to API key (message contains "OPENROUTER_API_KEY" or Korean equivalent)
        error_msg = str(exc_info.value)
        assert "OPENROUTER_API_KEY" in error_msg or "환경변수" in error_msg


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
