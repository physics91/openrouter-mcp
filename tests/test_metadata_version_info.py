"""Exact regressions for model version metadata extraction."""

import pytest

from openrouter_mcp.utils import metadata
from openrouter_mcp.utils.metadata import get_model_version_info


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
