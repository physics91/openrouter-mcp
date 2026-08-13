"""Exact regressions for model version metadata extraction."""

import re
from unittest.mock import Mock, call

import pytest

from openrouter_mcp.utils import metadata
from openrouter_mcp.utils.metadata import get_model_version_info


def test_precompiled_version_patterns_preserve_specs_and_order() -> None:
    assert [pattern.pattern for pattern in metadata._VERSION_PART_PATTERNS] == [
        r"(turbo|preview|beta|alpha|stable)",
        r"(opus|sonnet|haiku)",
        r"(\d{4}-\d{2}-\d{2})|(\d{8})",
        r"v(\d+(?:\.\d+)*)",
        r"(\d+k)",
    ]
    assert [name for name, _ in metadata._MODEL_FAMILY_PATTERNS] == [
        "gpt-4",
        "gpt-3.5",
        "claude-3",
        "claude-2",
        "gemini",
        "llama-3",
        "llama-2",
        "mistral",
        "deepseek",
        "o1",
    ]
    assert metadata._RELEASE_DATE_PATTERN.pattern == r"(\d{4})-?(\d{2})-?(\d{2})"
    ignorecase_flags = re.compile("", re.IGNORECASE).flags
    default_flags = re.compile("").flags
    assert [pattern.flags for pattern in metadata._VERSION_PART_PATTERNS] == [
        ignorecase_flags,
        ignorecase_flags,
        default_flags,
        ignorecase_flags,
        ignorecase_flags,
    ]
    assert [pattern.flags for _, pattern in metadata._MODEL_FAMILY_PATTERNS] == [
        ignorecase_flags
    ] * 10
    assert metadata._RELEASE_DATE_PATTERN.flags == default_flags


def test_version_regex_fallback_preserves_search_order(monkeypatch) -> None:
    search = Mock(return_value=None)
    monkeypatch.setattr(metadata.re, "search", search)

    assert metadata._extract_version_parts("source") == []
    assert metadata._extract_model_family("source") == "unknown"
    assert metadata._extract_release_date("source", 0) is None
    assert search.call_args_list == [
        call(r"(turbo|preview|beta|alpha|stable)", "source", re.IGNORECASE),
        call(r"(opus|sonnet|haiku)", "source", re.IGNORECASE),
        call(r"(\d{4}-\d{2}-\d{2})|(\d{8})", "source"),
        call(r"v(\d+(?:\.\d+)*)", "source", re.IGNORECASE),
        call(r"(\d+k)", "source", re.IGNORECASE),
        call(r"gpt-?4", "source", re.IGNORECASE),
        call(r"gpt-?3\.5", "source", re.IGNORECASE),
        call(r"claude-?3", "source", re.IGNORECASE),
        call(r"claude-?2", "source", re.IGNORECASE),
        call(r"gemini", "source", re.IGNORECASE),
        call(r"llama-?3", "source", re.IGNORECASE),
        call(r"llama-?2", "source", re.IGNORECASE),
        call(r"mistral", "source", re.IGNORECASE),
        call(r"deepseek", "source", re.IGNORECASE),
        call(r"o1", "source", re.IGNORECASE),
        call(r"(\d{4})-?(\d{2})-?(\d{2})", "source"),
    ]


def test_rebound_ignorecase_uses_current_legacy_flag(monkeypatch) -> None:
    monkeypatch.setattr(metadata.re, "IGNORECASE", re.NOFLAG)

    assert metadata._extract_model_family("GPT-4") == "unknown"


def test_rebound_compiled_pattern_container_uses_legacy_patterns(monkeypatch) -> None:
    monkeypatch.setattr(metadata, "_MODEL_FAMILY_PATTERNS", ())

    assert metadata._extract_model_family("gpt-4") == "gpt-4"


@pytest.mark.parametrize("marker", metadata._LATEST_MODEL_MARKERS)
def test_latest_model_markers_preserve_case_insensitive_matches(marker: str) -> None:
    assert metadata._is_latest_model(f"vendor/{marker.upper()}-suffix") is True


def test_latest_model_markers_preserve_order_and_immutability() -> None:
    assert metadata._LATEST_MODEL_MARKERS == (
        "gpt-4-turbo",
        "gpt-4o",
        "o1-preview",
        "o1-mini",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        "gemini-2",
        "gemini-pro",
        "gemini-ultra",
        "llama-3",
        "mistral-large",
        "deepseek-v3",
    )
    assert metadata._LATEST_MODEL_PATTERN.pattern == "|".join(
        re.escape(marker) for marker in metadata._LATEST_MODEL_MARKERS
    )
    assert metadata._LATEST_MODEL_PATTERN.flags == re.compile("").flags


@pytest.mark.parametrize(
    "model_id",
    [
        "vendor/gptx4o",
        "vendor/ordinary.preview",
        "vendor/claude_3_opus",
        "vendor/deepseekxv3",
    ],
)
def test_latest_model_pattern_keeps_literal_substring_semantics(model_id: str) -> None:
    assert metadata._is_latest_model(model_id) is False


def test_rebound_latest_markers_use_legacy_membership(monkeypatch) -> None:
    monkeypatch.setattr(metadata, "_LATEST_MODEL_MARKERS", ("custom-marker",))

    assert metadata._is_latest_model("vendor/custom-marker") is True


def test_rebound_latest_pattern_uses_legacy_membership(monkeypatch) -> None:
    monkeypatch.setattr(metadata, "_LATEST_MODEL_PATTERN", re.compile("ordinary"))

    assert metadata._is_latest_model("vendor/ordinary") is False


def test_latest_model_custom_string_preserves_repeated_normalization() -> None:
    class TrackingString(str):
        lower_calls = 0

        def lower(self) -> str:
            type(self).lower_calls += 1
            return super().lower()

    model_id = TrackingString("vendor/ordinary-model")

    assert metadata._is_latest_model(model_id) is False
    assert TrackingString.lower_calls == len(metadata._LATEST_MODEL_MARKERS)


def test_composite_claude_version_info_preserves_part_order() -> None:
    assert get_model_version_info(
        {
            "id": "anthropic/claude-3-opus-preview-v2.1-200k-20240229",
            "created": 1,
        }
    ) == {
        "version": "preview-opus-2024-02-29-v2.1-200k",
        "release_date": "2024-02-29",
        "is_latest": True,
        "family": "claude-3",
        "full_version": "claude-3-preview-opus-2024-02-29-v2.1-200k",
    }


def test_unknown_version_info_preserves_defaults() -> None:
    assert get_model_version_info({"id": "vendor/model"}) == {
        "version": "unknown",
        "release_date": None,
        "is_latest": False,
        "family": "unknown",
        "full_version": "unknown",
    }


def test_compact_id_date_overrides_invalid_created_timestamp() -> None:
    assert get_model_version_info(
        {"id": "vendor/model-20251231", "created": 10**100}
    ) == {
        "version": "2025-12-31",
        "release_date": "2025-12-31",
        "is_latest": False,
        "family": "unknown",
        "full_version": "2025-12-31",
    }


class RecordingDict(dict):
    """Record get() order without changing dict behavior."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_calls: list[str] = []

    def get(self, key, default=None):
        self.get_calls.append(key)
        return super().get(key, default)


def test_version_info_preserves_initial_field_read_order() -> None:
    model_data = RecordingDict({"id": "vendor/model", "name": "Model", "created": 0})

    get_model_version_info(model_data)

    assert model_data.get_calls == ["id", "name", "created"]
