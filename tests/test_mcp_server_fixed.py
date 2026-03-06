#!/usr/bin/env python3
"""
MCP Server Basic Functionality Tests (FIXED VERSION)

This replaces the original test_mcp_server.py which only printed output.
Now includes proper assertions and verification.

Tests verify:
1. Server initializes correctly
2. Tools are registered properly
3. FastMCP instance is accessible
4. Expected tools are present
"""

import asyncio
import logging
import sys
from pathlib import Path

import pytest

# Add src to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _get_tools_dict(mcp_instance):
    """Build a stable name->tool mapping via the FastMCP public API."""
    tools = await mcp_instance.list_tools()
    return {tool.name: tool for tool in tools}


def _get_tools_dict_sync(mcp_instance):
    """Synchronous wrapper for non-async tests."""
    return asyncio.run(_get_tools_dict(mcp_instance))


class TestMCPServerBasicFunctionality:
    """MCP server basic functionality tests with assertions."""

    def test_mcp_server_imports_successfully(self):
        """Test that MCP server module can be imported."""
        try:
            from openrouter_mcp import server

            assert server is not None
        except ImportError as e:
            pytest.fail(f"Failed to import server module: {e}")

    def test_mcp_instance_exists(self):
        """Test that FastMCP instance exists in server module."""
        from openrouter_mcp.server import mcp

        assert mcp is not None, "MCP instance should exist"
        assert hasattr(mcp, "name"), "MCP instance should have a name"
        assert mcp.name == "openrouter-mcp", f"Expected name 'openrouter-mcp', got '{mcp.name}'"

    def test_benchmark_tools_are_registered(self):
        """Test that benchmark tools are registered."""
        from openrouter_mcp.handlers.mcp_benchmark import mcp

        tools = _get_tools_dict_sync(mcp)
        tool_names = list(tools.keys())

        # Expected benchmark tools
        expected_tools = [
            "benchmark_models",
            "get_benchmark_history",
            "compare_model_categories",
            "export_benchmark_report",
            "compare_model_performance",
        ]

        logger.info(f"Registered tools: {tool_names}")

        # Assert each expected tool is registered
        for expected_tool in expected_tools:
            assert (
                expected_tool in tool_names
            ), f"Tool '{expected_tool}' not found in registered tools: {tool_names}"

        # Assert minimum number of tools
        assert (
            len(tool_names) >= 5
        ), f"Expected at least 5 benchmark tools, found {len(tool_names)}: {tool_names}"

        logger.info(f"✓ All {len(expected_tools)} benchmark tools are registered")

    def test_chat_tools_are_registered(self):
        """Test that chat tools are registered."""
        from openrouter_mcp.handlers.chat import mcp

        tools = _get_tools_dict_sync(mcp)
        tool_names = list(tools.keys())

        expected_tools = ["chat_with_model", "list_available_models", "get_usage_stats"]

        logger.info(f"Registered chat tools: {tool_names}")

        for expected_tool in expected_tools:
            assert (
                expected_tool in tool_names
            ), f"Chat tool '{expected_tool}' not found: {tool_names}"

        assert len(tool_names) >= 3, f"Expected at least 3 chat tools, found {len(tool_names)}"

        logger.info(f"✓ All {len(expected_tools)} chat tools are registered")

    def test_collective_intelligence_tools_are_registered(self):
        """Test that collective intelligence tools are registered."""
        from openrouter_mcp.handlers.collective_intelligence import mcp

        tools = _get_tools_dict_sync(mcp)
        tool_names = list(tools.keys())

        expected_tools = [
            "collective_chat_completion",
            "ensemble_reasoning",
            "adaptive_model_selection",
            "cross_model_validation",
            "collaborative_problem_solving",
        ]

        logger.info(f"Registered CI tools: {tool_names}")

        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"CI tool '{expected_tool}' not found: {tool_names}"

        assert len(tool_names) >= 5, f"Expected at least 5 CI tools, found {len(tool_names)}"

        logger.info(f"✓ All {len(expected_tools)} collective intelligence tools are registered")

    def test_no_zero_tools_regression(self):
        """
        REGRESSION TEST: Ensure we never have zero registered tools.

        This specifically tests for the bug where tools weren't being registered
        due to module import issues.
        """
        from openrouter_mcp.handlers.chat import mcp as chat_mcp
        from openrouter_mcp.handlers.collective_intelligence import mcp as ci_mcp
        from openrouter_mcp.handlers.mcp_benchmark import mcp as benchmark_mcp

        chat_tools = len(_get_tools_dict_sync(chat_mcp))
        benchmark_tools = len(_get_tools_dict_sync(benchmark_mcp))
        ci_tools = len(_get_tools_dict_sync(ci_mcp))

        # These assertions should NEVER fail
        assert (
            chat_tools > 0
        ), "REGRESSION: Chat tools count is ZERO! Tools not registered properly."
        assert (
            benchmark_tools > 0
        ), "REGRESSION: Benchmark tools count is ZERO! Tools not registered properly."
        assert (
            ci_tools > 0
        ), "REGRESSION: Collective intelligence tools count is ZERO! Tools not registered properly."

        total = chat_tools + benchmark_tools + ci_tools

        logger.info("✓ Tool registration verified:")
        logger.info(f"  - Chat tools: {chat_tools}")
        logger.info(f"  - Benchmark tools: {benchmark_tools}")
        logger.info(f"  - Collective intelligence tools: {ci_tools}")
        logger.info(f"  - Total tools: {total}")

        assert total >= 13, f"Expected at least 13 total tools, found {total}"

    def test_all_tools_have_descriptions(self):
        """Test that all registered tools have descriptions."""
        from openrouter_mcp.handlers.chat import mcp as chat_mcp
        from openrouter_mcp.handlers.mcp_benchmark import mcp as benchmark_mcp

        chat_tools = _get_tools_dict_sync(chat_mcp)
        benchmark_tools = _get_tools_dict_sync(benchmark_mcp)

        tool_count = 0

        # Check chat tools
        for name, tool in chat_tools.items():
            assert hasattr(tool, "description"), f"Tool '{name}' missing description attribute"
            assert tool.description, f"Tool '{name}' has empty description"
            assert (
                len(tool.description) > 10
            ), f"Tool '{name}' description too short: '{tool.description}'"
            tool_count += 1

        # Check benchmark tools
        for name, tool in benchmark_tools.items():
            assert hasattr(tool, "description"), f"Tool '{name}' missing description attribute"
            assert tool.description, f"Tool '{name}' has empty description"
            assert (
                len(tool.description) > 10
            ), f"Tool '{name}' description too short: '{tool.description}'"
            tool_count += 1

        logger.info(f"✓ All {tool_count} tools have proper descriptions")

    def test_server_can_be_created(self):
        """Test that server app can be created with proper environment."""
        import os

        from openrouter_mcp.server import create_app

        # Set required environment variable
        original_key = os.getenv("OPENROUTER_API_KEY")
        os.environ["OPENROUTER_API_KEY"] = "sk-test-key-for-testing"

        try:
            app = create_app()
            assert app is not None, "create_app() should return an app instance"
            assert hasattr(app, "run"), "App should have a run() method"
            logger.info("✓ Server app created successfully")
        finally:
            # Restore original key
            if original_key:
                os.environ["OPENROUTER_API_KEY"] = original_key
            else:
                del os.environ["OPENROUTER_API_KEY"]

    def test_server_validates_environment(self):
        """Test that server properly validates environment variables."""
        import os

        from openrouter_mcp.server import validate_environment

        # Remove API key temporarily
        original_key = os.getenv("OPENROUTER_API_KEY")
        if "OPENROUTER_API_KEY" in os.environ:
            del os.environ["OPENROUTER_API_KEY"]

        try:
            # Should raise ValueError
            with pytest.raises(ValueError, match="Missing required environment variables"):
                validate_environment()
            logger.info("✓ Environment validation works correctly")
        finally:
            # Restore original key
            if original_key:
                os.environ["OPENROUTER_API_KEY"] = original_key


@pytest.mark.asyncio
async def test_mcp_server_comprehensive():
    """
    Comprehensive MCP server test.

    This is the improved version of the original test_mcp_server.py main function.
    """
    logger.info("=" * 70)
    logger.info("MCP SERVER COMPREHENSIVE TEST")
    logger.info("=" * 70)

    try:
        # Test 1: Import server
        from openrouter_mcp.server import mcp

        assert mcp is not None
        logger.info("✓ Server module imported successfully")

        # Test 2: Check all handler modules
        from openrouter_mcp.handlers import chat, collective_intelligence, mcp_benchmark, multimodal

        assert chat is not None
        assert mcp_benchmark is not None
        assert collective_intelligence is not None
        assert multimodal is not None
        logger.info("✓ All handler modules imported successfully")

        # Test 3: Verify tool counts
        chat_tools = len(await _get_tools_dict(chat.mcp))
        benchmark_tools = len(await _get_tools_dict(mcp_benchmark.mcp))
        ci_tools = len(await _get_tools_dict(collective_intelligence.mcp))
        multimodal_tools = len(await _get_tools_dict(multimodal.mcp))

        assert chat_tools >= 3, f"Expected >= 3 chat tools, got {chat_tools}"
        assert benchmark_tools >= 5, f"Expected >= 5 benchmark tools, got {benchmark_tools}"
        assert ci_tools >= 5, f"Expected >= 5 CI tools, got {ci_tools}"
        assert multimodal_tools >= 2, f"Expected >= 2 multimodal tools, got {multimodal_tools}"

        total_tools = chat_tools + benchmark_tools + ci_tools + multimodal_tools

        logger.info("✓ Tool registration verified:")
        logger.info(f"    Chat tools: {chat_tools}")
        logger.info(f"    Benchmark tools: {benchmark_tools}")
        logger.info(f"    Collective intelligence tools: {ci_tools}")
        logger.info(f"    Multimodal tools: {multimodal_tools}")
        logger.info(f"    TOTAL: {total_tools} tools registered")

        assert total_tools >= 15, f"Expected at least 15 total tools, found {total_tools}"

        # Test 4: Verify specific tools exist
        benchmark_tool_names = list((await _get_tools_dict(mcp_benchmark.mcp)).keys())
        expected_benchmark_tools = [
            "benchmark_models",
            "get_benchmark_history",
            "compare_model_categories",
            "export_benchmark_report",
            "compare_model_performance",
        ]

        for tool in expected_benchmark_tools:
            assert tool in benchmark_tool_names, f"Missing benchmark tool: {tool}"

        logger.info("✓ All expected benchmark tools present")

        # Test 5: Verify CI tools exist
        ci_tool_names = list((await _get_tools_dict(collective_intelligence.mcp)).keys())
        expected_ci_tools = [
            "collective_chat_completion",
            "ensemble_reasoning",
            "adaptive_model_selection",
            "cross_model_validation",
            "collaborative_problem_solving",
        ]

        for tool in expected_ci_tools:
            assert tool in ci_tool_names, f"Missing CI tool: {tool}"

        logger.info("✓ All expected collective intelligence tools present")

        logger.info("=" * 70)
        logger.info("ALL TESTS PASSED!")
        logger.info("=" * 70)
        logger.info("")
        logger.info("OpenRouter MCP Server is properly configured with:")
        logger.info(f"  - {total_tools} total tools registered")
        logger.info("  - Chat completion capabilities")
        logger.info("  - Model benchmarking system")
        logger.info("  - Collective intelligence features")
        logger.info("  - Multimodal support")
        logger.info("")
        logger.info("Ready for Claude Desktop integration!")

        return True

    except AssertionError as e:
        logger.error(f"✗ TEST FAILED: {e}")
        raise
    except Exception as e:
        logger.error(f"✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    # Run pytest
    exit_code = pytest.main([__file__, "-v", "-s"])

    if exit_code == 0:
        print("\n" + "=" * 70)
        print("SUCCESS: All MCP server tests passed!")
        print("=" * 70)

    sys.exit(exit_code)
