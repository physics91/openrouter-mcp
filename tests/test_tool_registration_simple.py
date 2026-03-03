#!/usr/bin/env python3
"""
Simple Tool Registration Tests

These tests verify tool registration WITHOUT async/await complexities.
They directly check the tool manager state.
"""

import sys
from pathlib import Path

import pytest

# Add src to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


class TestToolRegistrationSimple:
    """Simple tests that verify tools are registered."""

    def test_chat_handler_has_tools(self):
        """Verify chat handler registers tools."""
        from openrouter_mcp.handlers.chat import mcp

        # Access the tool manager directly
        assert hasattr(mcp, "_tool_manager")
        tool_manager = mcp._tool_manager

        # Get tool registry
        assert hasattr(tool_manager, "_tools")
        tools = tool_manager._tools

        # Verify tools are registered
        assert len(tools) > 0, "No chat tools registered!"

        # Expected tool names
        expected_tools = ["chat_with_model", "list_available_models", "get_usage_stats"]

        tool_names = list(tools.keys())

        for expected in expected_tools:
            assert (
                expected in tool_names
            ), f"Tool '{expected}' not found. Registered: {tool_names}"

        print(f"[OK] Chat tools registered: {tool_names}")

    def test_benchmark_handler_has_tools(self):
        """Verify benchmark handler registers tools."""
        from openrouter_mcp.handlers.mcp_benchmark import mcp

        tool_manager = mcp._tool_manager
        tools = tool_manager._tools

        assert len(tools) > 0, "No benchmark tools registered!"

        expected_tools = [
            "benchmark_models",
            "get_benchmark_history",
            "compare_model_categories",
            "export_benchmark_report",
            "compare_model_performance",
        ]

        tool_names = list(tools.keys())

        for expected in expected_tools:
            assert (
                expected in tool_names
            ), f"Tool '{expected}' not found. Registered: {tool_names}"

        print(f"[OK] Benchmark tools registered: {tool_names}")

    def test_collective_intelligence_has_tools(self):
        """Verify collective intelligence handler registers tools."""
        from openrouter_mcp.handlers.collective_intelligence import mcp

        tool_manager = mcp._tool_manager
        tools = tool_manager._tools

        assert len(tools) > 0, "No CI tools registered!"

        expected_tools = [
            "collective_chat_completion",
            "ensemble_reasoning",
            "adaptive_model_selection",
            "cross_model_validation",
            "collaborative_problem_solving",
        ]

        tool_names = list(tools.keys())

        for expected in expected_tools:
            assert (
                expected in tool_names
            ), f"Tool '{expected}' not found. Registered: {tool_names}"

        print(f"[OK] Collective intelligence tools registered: {tool_names}")

    def test_no_zero_tools_regression(self):
        """
        CRITICAL REGRESSION TEST

        Ensures we never have zero registered tools.
        This catches the "0 tools" bug that was found in code review.
        """
        from openrouter_mcp.handlers.chat import mcp as chat_mcp
        from openrouter_mcp.handlers.collective_intelligence import mcp as ci_mcp
        from openrouter_mcp.handlers.mcp_benchmark import mcp as benchmark_mcp

        chat_count = len(chat_mcp._tool_manager._tools)
        benchmark_count = len(benchmark_mcp._tool_manager._tools)
        ci_count = len(ci_mcp._tool_manager._tools)

        # CRITICAL: These should NEVER be zero
        assert chat_count > 0, "REGRESSION: Chat tools count is ZERO!"
        assert benchmark_count > 0, "REGRESSION: Benchmark tools count is ZERO!"
        assert ci_count > 0, "REGRESSION: Collective intelligence tools count is ZERO!"

        total = chat_count + benchmark_count + ci_count

        print("\n[OK] Tool counts verified:")
        print(f"  Chat: {chat_count}")
        print(f"  Benchmark: {benchmark_count}")
        print(f"  Collective Intelligence: {ci_count}")
        print(f"  Total: {total}")

        # Verify we have at least the expected minimum
        assert total >= 13, f"Expected at least 13 tools total, got {total}"

    def test_all_tools_have_descriptions(self):
        """Verify all registered tools have non-empty descriptions."""
        from openrouter_mcp.handlers.chat import mcp as chat_mcp
        from openrouter_mcp.handlers.mcp_benchmark import mcp as benchmark_mcp

        # Check chat tools
        for name, tool in chat_mcp._tool_manager._tools.items():
            assert hasattr(tool, "description"), f"Tool '{name}' missing description"
            assert tool.description, f"Tool '{name}' has empty description"
            assert len(tool.description) > 20, f"Tool '{name}' description too short"

        # Check benchmark tools
        for name, tool in benchmark_mcp._tool_manager._tools.items():
            assert hasattr(tool, "description"), f"Tool '{name}' missing description"
            assert tool.description, f"Tool '{name}' has empty description"
            assert len(tool.description) > 20, f"Tool '{name}' description too short"

        print("[OK] All tools have proper descriptions")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
