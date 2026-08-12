"""Exact regressions for model version metadata extraction."""

from openrouter_mcp.utils.metadata import get_model_version_info


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
