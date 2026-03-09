"""Canonical MCP tool names for public-surface regression tests."""

CHAT_TOOL_NAMES = [
    "chat_with_model",
    "list_available_models",
    "get_usage_stats",
]

FREE_TOOL_NAMES = [
    "free_chat",
    "list_free_models",
    "get_free_model_metrics",
]

VISION_TOOL_NAMES = [
    "chat_with_vision",
    "list_vision_models",
]

BENCHMARK_TOOL_NAMES = [
    "benchmark_models",
    "get_benchmark_history",
    "compare_model_categories",
    "export_benchmark_report",
    "compare_model_performance",
]

COLLECTIVE_TOOL_NAMES = [
    "collective_chat_completion",
    "ensemble_reasoning",
    "adaptive_model_selection",
    "cross_model_validation",
    "collaborative_problem_solving",
]

ALL_REGISTERED_TOOL_NAMES = sorted(
    CHAT_TOOL_NAMES
    + FREE_TOOL_NAMES
    + VISION_TOOL_NAMES
    + BENCHMARK_TOOL_NAMES
    + COLLECTIVE_TOOL_NAMES
)
