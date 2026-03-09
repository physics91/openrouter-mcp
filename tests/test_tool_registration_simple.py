#!/usr/bin/env python3
"""
Tool Registration & Quality Tests

Verify tool registration, description quality, and parameter schemas
via the public create_app() + list_tools() API.
"""

import os
import sys
from pathlib import Path

import pytest

from tests.test_tool_expectations import (
    BENCHMARK_TOOL_NAMES,
    CHAT_TOOL_NAMES,
    COLLECTIVE_TOOL_NAMES,
)

# Add src to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Ensure a dummy API key is set so create_app() passes validation
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-test-dummy")


@pytest.fixture(scope="module")
def tools():
    """Load all registered tools once via the public API."""
    import asyncio

    from openrouter_mcp.server import create_app

    app = create_app()
    return asyncio.run(app.list_tools())


def _tool_names(tools):
    return [t.name for t in tools]


class TestToolRegistration:
    """Verify expected tools are registered."""

    def test_chat_tools_registered(self, tools):
        names = _tool_names(tools)
        for name in CHAT_TOOL_NAMES:
            assert name in names, f"Tool '{name}' not found. Registered: {names}"

    def test_benchmark_tools_registered(self, tools):
        names = _tool_names(tools)
        for name in BENCHMARK_TOOL_NAMES:
            assert name in names, f"Tool '{name}' not found. Registered: {names}"

    def test_ci_tools_registered(self, tools):
        names = _tool_names(tools)
        for name in COLLECTIVE_TOOL_NAMES:
            assert name in names, f"Tool '{name}' not found. Registered: {names}"

    def test_no_zero_tools_regression(self, tools):
        assert len(tools) >= 13, f"Expected at least 13 tools, got {len(tools)}"


CI_TOOLS = set(COLLECTIVE_TOOL_NAMES)
BENCHMARK_TOOLS = set(BENCHMARK_TOOL_NAMES)


class TestToolDescriptionQuality:
    """Verify tool descriptions are meaningful and in English."""

    def test_all_tools_have_descriptions(self, tools):
        for tool in tools:
            assert tool.description, f"Tool '{tool.name}' has empty description"
            assert len(tool.description) > 20, f"Tool '{tool.name}' description too short"

    def test_ci_tools_no_wrapper_description(self, tools):
        for tool in tools:
            if tool.name in CI_TOOLS:
                assert (
                    "wrapper" not in tool.description.lower()
                ), f"CI tool '{tool.name}' still has 'wrapper' in description"

    def test_benchmark_tools_no_korean(self, tools):
        for tool in tools:
            if tool.name in BENCHMARK_TOOLS:
                has_korean = any("\uac00" <= c <= "\ud7a3" for c in tool.description)
                assert not has_korean, f"Benchmark tool '{tool.name}' has Korean in description"


class TestParameterDescriptions:
    """Verify all tool parameters expose descriptions in the schema."""

    def test_benchmark_params_have_descriptions(self, tools):
        for tool in tools:
            if tool.name not in BENCHMARK_TOOLS:
                continue
            props = tool.parameters.get("properties", {})
            for param_name, param_schema in props.items():
                assert (
                    "description" in param_schema
                ), f"{tool.name}.{param_name} missing description"

    def test_ci_params_have_descriptions(self, tools):
        for tool in tools:
            if tool.name not in CI_TOOLS:
                continue
            # CI tools wrap params in a "request" Pydantic model
            top_props = tool.parameters.get("properties", {})
            if "request" in top_props:
                props = top_props["request"].get("properties", {})
            else:
                props = top_props
            for param_name, param_schema in props.items():
                assert (
                    "description" in param_schema
                ), f"{tool.name}.{param_name} missing description"

    def test_benchmark_metric_has_enum(self, tools):
        tool = next(t for t in tools if t.name == "compare_model_categories")
        metric_schema = tool.parameters["properties"]["metric"]
        assert (
            "enum" in metric_schema or "anyOf" in metric_schema
        ), "compare_model_categories.metric should expose allowed values"

    def test_benchmark_format_has_enum(self, tools):
        tool = next(t for t in tools if t.name == "export_benchmark_report")
        format_schema = tool.parameters["properties"]["format"]
        assert (
            "enum" in format_schema or "anyOf" in format_schema
        ), "export_benchmark_report.format should expose allowed values"

    def test_ci_strategy_has_enum(self, tools):
        tool = next(t for t in tools if t.name == "collective_chat_completion")
        request_props = tool.parameters["properties"]["request"]["properties"]
        strategy_schema = request_props["strategy"]
        assert (
            "enum" in strategy_schema or "anyOf" in strategy_schema
        ), "collective_chat_completion.strategy should expose allowed values"


class TestCIParameterPassthrough:
    """Verify CI tool parameters are wired through to implementation."""

    def test_max_tokens_in_requirements(self):
        from openrouter_mcp.handlers.collective_intelligence import _build_requirements

        reqs = _build_requirements(max_tokens=512)
        assert reqs["max_tokens"] == 512

    def test_max_tokens_none_omitted(self):
        from openrouter_mcp.handlers.collective_intelligence import _build_requirements

        reqs = _build_requirements(max_tokens=None)
        assert "max_tokens" not in reqs

    def test_system_prompt_in_requirements(self):
        from openrouter_mcp.handlers.collective_intelligence import _build_requirements

        reqs = _build_requirements(extras={"system_prompt": "Be concise"})
        assert reqs["system_prompt"] == "Be concise"

    def test_create_task_context_rejects_invalid_task_type(self):
        from openrouter_mcp.handlers.collective_intelligence import create_task_context

        with pytest.raises(ValueError, match="Invalid task_type"):
            create_task_context(content="test", task_type="invalid_type")

    def test_create_task_context_accepts_valid_task_types(self):
        from openrouter_mcp.handlers.collective_intelligence import create_task_context

        valid_types = [
            "reasoning",
            "analysis",
            "creative",
            "factual",
            "code_generation",
            "summarization",
            "translation",
            "math",
            "classification",
        ]
        for task_type in valid_types:
            ctx = create_task_context(content="test", task_type=task_type)
            assert ctx.task_type.value == task_type

    def test_consensus_config_receives_confidence_threshold(self):
        from openrouter_mcp.collective_intelligence import ConsensusConfig

        config = ConsensusConfig(confidence_threshold=0.95)
        assert config.confidence_threshold == 0.95

    def test_collaborative_solver_reads_max_iterations_from_requirements(self):
        """Verify _solve_iterative reads max_iterations from task.requirements."""
        import ast
        import inspect
        import textwrap

        from openrouter_mcp.collective_intelligence.collaborative_solver import CollaborativeSolver

        source = textwrap.dedent(inspect.getsource(CollaborativeSolver._solve_iterative))
        tree = ast.parse(source)
        # Find the assignment: max_iterations = task.requirements.get("max_iterations", 3)
        found = any(
            "max_iterations" in ast.dump(node) and "requirements" in ast.dump(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
        )
        assert found, "_solve_iterative should read max_iterations from task.requirements"

    def test_validation_threshold_in_requirements(self):
        from openrouter_mcp.handlers.collective_intelligence import _build_requirements

        reqs = _build_requirements(extras={"validation_threshold": 0.85})
        assert reqs["validation_threshold"] == 0.85

    def test_cross_validator_determine_validity_uses_task_threshold(self):
        """Verify _determine_validity respects task-level validation_threshold."""
        from unittest.mock import AsyncMock, MagicMock

        from openrouter_mcp.collective_intelligence.base import TaskContext, TaskType
        from openrouter_mcp.collective_intelligence.cross_validator import (
            CrossValidator,
            ValidationConfig,
            ValidationReport,
        )

        provider = AsyncMock()
        # Config threshold is 0.7 (default), but task says 0.3
        validator = CrossValidator(provider, config=ValidationConfig(confidence_threshold=0.7))

        report = MagicMock(spec=ValidationReport)
        report.issues = []
        report.overall_score = 0.5  # Fails 0.7 config, passes 0.3 task threshold
        report.consensus_level = 1.0
        report.validator_models = []

        task = TaskContext(
            task_type=TaskType.ANALYSIS,
            content="test",
            requirements={"validation_threshold": 0.3},
        )

        # Without task context, should fail (0.5 < 0.7)
        assert validator._determine_validity(report) is False
        # With task context override, should pass (0.5 >= 0.3)
        assert validator._determine_validity(report, task) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
