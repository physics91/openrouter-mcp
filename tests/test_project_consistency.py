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
