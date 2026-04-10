#!/usr/bin/env python3
"""Project consistency checks for docs and package metadata."""

import json
from pathlib import Path

import pytest

from tests.test_tool_expectations import ALL_REGISTERED_TOOL_NAMES

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent


def _read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _load_package_json() -> dict:
    return json.loads(_read_text("package.json"))


def test_package_metadata_has_no_placeholders() -> None:
    package = _load_package_json()

    values_to_check = [
        package["author"],
        package["homepage"],
        package["repository"]["url"],
        package["bugs"]["url"],
    ]

    placeholder_markers = ("Your Name", "your.email@example.com", "yourusername")
    offenders = [
        value for value in values_to_check if any(marker in value for marker in placeholder_markers)
    ]

    assert not offenders, f"Placeholder package metadata remains: {offenders}"


def test_api_docs_cover_all_registered_tools() -> None:
    api_doc = _read_text("docs/API.md")
    missing = [name for name in ALL_REGISTERED_TOOL_NAMES if name not in api_doc]

    assert not missing, f"API docs are missing registered tools: {missing}"


def test_api_docs_use_raw_mcp_name_field() -> None:
    api_doc = _read_text("docs/API.md")

    assert '"method": "tools/call"' in api_doc
    assert '"params": {' in api_doc
    assert '"name": "chat_with_model"' in api_doc
    assert '"name": "chat_with_vision"' in api_doc
    assert '"name": "compare_model_performance"' in api_doc
    assert '"tool":' not in api_doc


def test_docs_describe_runtime_thrift_response_metadata() -> None:
    api_doc = _read_text("docs/API.md")
    faq_doc = _read_text("docs/FAQ.md")

    assert "thrift_metrics" in api_doc
    assert "thrift_summary" in api_doc
    assert "routing_metrics.thrift_feedback" in api_doc
    assert "constraints_applied" in api_doc
    assert "constraints_unmet" in api_doc
    assert "filtered_candidates" in api_doc
    assert "performance_weights" in api_doc
    assert "preference_matches" in api_doc
    assert "preferred_provider" in api_doc
    assert "preferred_model_family" in api_doc
    assert "max_cost" in api_doc
    assert "min_context_length" in api_doc
    assert "adaptive_model_selection" in api_doc
    assert "lookback_days" in api_doc
    assert "bucket_summary" in api_doc
    assert "prompt_savings_breakdown" in api_doc
    assert "recent_reuse_prompt_tokens" in api_doc
    assert "request_savings_breakdown" in api_doc
    assert "cache_efficiency" in api_doc
    assert "cache_hit_requests" in api_doc
    assert "cache_write_requests" in api_doc
    assert "cache_hit_request_rate_pct" in api_doc
    assert "cache_write_request_rate_pct" in api_doc
    assert "cache_efficiency_by_provider" in api_doc
    assert "cache_efficiency_by_model" in api_doc
    assert "cache_hotspots" in api_doc
    assert "cache_deadspots" in api_doc
    assert '"reason"' in api_doc
    assert "persisted daily rollups" in api_doc
    assert "local calendar day" in api_doc
    assert "chat_with_model" in api_doc
    assert "chat_with_vision" in api_doc
    assert "free_chat" in api_doc
    assert "get_usage_stats" in api_doc
    assert "thrift_summary" in faq_doc


def test_troubleshooting_covers_runtime_thrift_interpretation() -> None:
    troubleshooting_doc = _read_text("docs/TROUBLESHOOTING.md")

    assert "thrift_summary" in troubleshooting_doc
    assert "routing_metrics.thrift_feedback" in troubleshooting_doc
    assert "constraints_applied" in troubleshooting_doc
    assert "constraints_unmet" in troubleshooting_doc
    assert "filtered_candidates" in troubleshooting_doc
    assert "performance_weights" in troubleshooting_doc
    assert "preference_matches" in troubleshooting_doc
    assert "preferred_provider" in troubleshooting_doc
    assert "preferred_model_family" in troubleshooting_doc
    assert "Adaptive Router Keeps Picking Cache Deadspots" in troubleshooting_doc
    assert "source" in troubleshooting_doc
    assert "penalty" in troubleshooting_doc
    assert "lookback_days" in troubleshooting_doc
    assert "bucket_summary" in troubleshooting_doc
    assert "saved_cost_usd" in troubleshooting_doc
    assert "effective_cost_reduction_pct" in troubleshooting_doc
    assert "prompt_savings_breakdown" in troubleshooting_doc
    assert "recent_reuse_prompt_tokens" in troubleshooting_doc
    assert "request_savings_breakdown" in troubleshooting_doc
    assert "cache_efficiency" in troubleshooting_doc
    assert "cache_hit_request_rate_pct" in troubleshooting_doc
    assert "cache_write_request_rate_pct" in troubleshooting_doc
    assert "cache_efficiency_by_provider" in troubleshooting_doc
    assert "cache_hotspots" in troubleshooting_doc
    assert "cache_deadspots" in troubleshooting_doc
    assert "reason" in troubleshooting_doc
    assert "local calendar day" in troubleshooting_doc
    assert "get_usage_stats" in troubleshooting_doc


def test_korean_usage_guide_covers_runtime_thrift_summary() -> None:
    usage_guide = _read_text("docs/USAGE_GUIDE_KR.md")

    assert "get_usage_stats" in usage_guide
    assert "thrift_summary" in usage_guide
    assert "saved_cost_usd" in usage_guide
    assert "prompt_savings_breakdown" in usage_guide
    assert "recent_reuse_prompt_tokens" in usage_guide
    assert "request_savings_breakdown" in usage_guide
    assert "cache_efficiency" in usage_guide
    assert "cache_hit_request_rate_pct" in usage_guide
    assert "cache_write_request_rate_pct" in usage_guide
    assert "cache_efficiency_by_provider" in usage_guide
    assert "cache_hotspots" in usage_guide
    assert "cache_deadspots" in usage_guide
    assert "reason" in usage_guide
    assert "로컬 날짜" in usage_guide


def test_docs_show_usage_stats_request_and_response_examples() -> None:
    api_doc = _read_text("docs/API.md")
    usage_guide = _read_text("docs/USAGE_GUIDE_KR.md")

    assert '"name": "get_usage_stats"' in api_doc
    assert "Example MCP Response" in api_doc
    assert "Claude 출력 예시" in usage_guide
    assert "이번 달 OpenRouter 사용량" in usage_guide


@pytest.mark.parametrize(
    ("relative_path", "banned_snippet"),
    [
        (
            "docs/MULTIMODAL_GUIDE.md",
            '{"data": "/path/to/image.jpg", "type": "path"}',
        ),
        (
            "docs/MULTIMODAL_GUIDE.md",
            "Try downloading and using file path instead",
        ),
        (
            "docs/USAGE_GUIDE_KR.md",
            '"OPENROUTER_API_KEY": "sk-or-v1-your-key-here"',
        ),
        (
            "docs/USAGE_GUIDE_KR.md",
            'img = ImageInput(data="/path/to/image.jpg", type="path")',
        ),
        (
            "docs/INSTALLATION.md",
            "OPENROUTER_API_KEY=sk-or-v1-your-key-here",
        ),
        (
            "docs/FAQ.md",
            '{"data": "/path/to/image.jpg", "type": "path"}',
        ),
        (
            "docs/CLAUDE_CODE_SETUP_KR.md",
            '"OPENROUTER_API_KEY":',
        ),
        (
            "docs/CLAUDE_CODE_GUIDE.md",
            '"OPENROUTER_API_KEY":',
        ),
    ],
)
def test_docs_do_not_contain_removed_or_insecure_examples(
    relative_path: str, banned_snippet: str
) -> None:
    content = _read_text(relative_path)

    assert banned_snippet not in content, f"{relative_path} still contains: {banned_snippet}"


def test_changelog_has_no_placeholder_repo_links() -> None:
    changelog = _read_text("CHANGELOG.md")

    assert "yourusername/openrouter-mcp" not in changelog
