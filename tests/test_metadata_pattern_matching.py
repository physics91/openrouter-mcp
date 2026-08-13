from unittest.mock import Mock, call

import pytest

from src.openrouter_mcp.utils import metadata

pytestmark = pytest.mark.unit


def test_find_first_pattern_match_preserves_key_and_pattern_order(monkeypatch):
    events = []
    first_key = object()
    second_key = object()
    pattern_map = {
        first_key: ["first-miss", "first-hit", "first-unused"],
        second_key: ["second-unused"],
    }

    def search(pattern, text):
        events.append((pattern, text))
        return object() if pattern == "first-hit" else None

    monkeypatch.setattr(metadata.re, "search", search)

    result = metadata._find_first_pattern_match("source", pattern_map)

    assert result is first_key
    assert events == [
        ("first-miss", "source"),
        ("first-hit", "source"),
    ]


def test_find_first_pattern_match_returns_none_after_all_patterns(monkeypatch):
    search = Mock(return_value=None)
    monkeypatch.setattr(metadata.re, "search", search)
    pattern_map = {"first": ["one", "two"], "second": ["three"]}

    assert metadata._find_first_pattern_match("source", pattern_map) is None
    assert search.call_args_list == [
        call("one", "source"),
        call("two", "source"),
        call("three", "source"),
    ]


def test_find_first_pattern_match_propagates_search_error_in_order(monkeypatch):
    events = []
    expected_error = RuntimeError("invalid pattern")

    def search(pattern, text):
        events.append((pattern, text))
        if pattern == "broken":
            raise expected_error
        return None

    monkeypatch.setattr(metadata.re, "search", search)

    with pytest.raises(RuntimeError) as exc_info:
        metadata._find_first_pattern_match(
            "source",
            {"first": ["miss", "broken"], "second": ["unused"]},
        )

    assert exc_info.value is expected_error
    assert events == [("miss", "source"), ("broken", "source")]


def test_compiled_pattern_maps_preserve_specs_order_and_flags():
    assert metadata._PROVIDER_PATTERN_SPEC == tuple(
        (key, tuple(patterns)) for key, patterns in metadata.PROVIDER_PATTERNS.items()
    )
    assert metadata._CATEGORY_PATTERN_SPEC == tuple(
        (key, tuple(patterns)) for key, patterns in metadata.CATEGORY_PATTERNS.items()
    )
    assert [
        (key, tuple(pattern.pattern for pattern in patterns))
        for key, patterns in metadata._COMPILED_PROVIDER_PATTERNS
    ] == list(metadata._PROVIDER_PATTERN_SPEC)
    assert [
        (key, tuple(pattern.pattern for pattern in patterns))
        for key, patterns in metadata._COMPILED_CATEGORY_PATTERNS
    ] == list(metadata._CATEGORY_PATTERN_SPEC)
    assert all(
        pattern.flags == metadata.re.compile("").flags
        for compiled_map in (
            metadata._COMPILED_PROVIDER_PATTERNS,
            metadata._COMPILED_CATEGORY_PATTERNS,
        )
        for _, patterns in compiled_map
        for pattern in patterns
    )


@pytest.mark.parametrize(
    "pattern_map,compiled_map",
    [
        (metadata.PROVIDER_PATTERNS, metadata._COMPILED_PROVIDER_PATTERNS),
        (metadata.CATEGORY_PATTERNS, metadata._COMPILED_CATEGORY_PATTERNS),
    ],
)
def test_compiled_pattern_maps_match_every_canonical_pattern(pattern_map, compiled_map):
    for expected_key, patterns in compiled_map:
        for pattern in patterns:
            match_text = pattern.pattern.replace("^", "").replace(r"\d", "3")
            if any(character in match_text for character in "?+*[](){}|"):
                continue
            assert (
                metadata._find_first_pattern_match(match_text, pattern_map)
                is expected_key
            )


def test_in_place_pattern_mutation_uses_legacy_search(monkeypatch):
    patterns = [r"^custom-provider/"]
    monkeypatch.setitem(
        metadata.PROVIDER_PATTERNS, metadata.ModelProvider.OPENAI, patterns
    )

    assert (
        metadata._find_first_pattern_match(
            "custom-provider/model", metadata.PROVIDER_PATTERNS
        )
        is metadata.ModelProvider.OPENAI
    )


def test_rebound_compiled_pattern_map_uses_legacy_search(monkeypatch):
    monkeypatch.setattr(metadata, "_COMPILED_CATEGORY_PATTERNS", ())

    assert (
        metadata._find_first_pattern_match("dall-e", metadata.CATEGORY_PATTERNS)
        is metadata.ModelCategory.IMAGE
    )


def test_canonical_pattern_map_preserves_search_monkeypatch(monkeypatch):
    search = Mock(
        side_effect=lambda pattern, text: object() if pattern == r"dall-?e" else None
    )
    monkeypatch.setattr(metadata.re, "search", search)

    assert (
        metadata._find_first_pattern_match("source", metadata.CATEGORY_PATTERNS)
        is metadata.ModelCategory.IMAGE
    )
    search.assert_called_once_with(r"dall-?e", "source")


def test_extract_provider_prefix_precedence_skips_pattern_helper(monkeypatch):
    find_match = Mock(side_effect=AssertionError("pattern helper must not run"))
    monkeypatch.setattr(metadata, "_find_first_pattern_match", find_match)

    assert (
        metadata.extract_provider_from_id("OpenAI/gpt-4")
        is metadata.ModelProvider.OPENAI
    )
    find_match.assert_not_called()


def test_provider_prefix_map_preserves_all_direct_mappings():
    expected = {
        "openai": metadata.ModelProvider.OPENAI,
        "anthropic": metadata.ModelProvider.ANTHROPIC,
        "google": metadata.ModelProvider.GOOGLE,
        "meta-llama": metadata.ModelProvider.META,
        "meta": metadata.ModelProvider.META,
        "mistralai": metadata.ModelProvider.MISTRAL,
        "deepseek": metadata.ModelProvider.DEEPSEEK,
        "xai": metadata.ModelProvider.XAI,
        "cohere": metadata.ModelProvider.COHERE,
        "perplexity": metadata.ModelProvider.PERPLEXITY,
        "fireworks": metadata.ModelProvider.FIREWORKS,
        "togethercomputer": metadata.ModelProvider.TOGETHER,
        "together": metadata.ModelProvider.TOGETHER,
        "huggingface": metadata.ModelProvider.HUGGINGFACE,
        "ai21": metadata.ModelProvider.AI21,
        "inflection": metadata.ModelProvider.INFLECTION,
        "nvidia": metadata.ModelProvider.NVIDIA,
    }

    assert dict(metadata._PROVIDER_PREFIX_MAP) == expected
    for prefix, provider in expected.items():
        assert metadata.extract_provider_from_id(f"{prefix.upper()}/model") is provider


def test_provider_prefix_map_is_immutable():
    with pytest.raises(TypeError):
        metadata._PROVIDER_PREFIX_MAP["new"] = metadata.ModelProvider.UNKNOWN


def test_extract_provider_delegates_normalized_id_to_pattern_helper(monkeypatch):
    find_match = Mock(return_value=metadata.ModelProvider.XAI)
    monkeypatch.setattr(metadata, "_find_first_pattern_match", find_match)

    assert metadata.extract_provider_from_id("GROK-Beta") is metadata.ModelProvider.XAI
    find_match.assert_called_once_with("grok-beta", metadata.PROVIDER_PATTERNS)


def test_provider_patterns_keep_first_match_for_overlapping_model_id():
    assert (
        metadata.extract_provider_from_id("gpt-llama-3")
        is metadata.ModelProvider.OPENAI
    )


def test_category_modality_precedence_skips_pattern_helper(monkeypatch):
    find_match = Mock(side_effect=AssertionError("pattern helper must not run"))
    monkeypatch.setattr(metadata, "_find_first_pattern_match", find_match)

    result = metadata.determine_model_category(
        {"id": "model", "architecture": {"modality": "TEXT->IMAGE"}}
    )

    assert result is metadata.ModelCategory.IMAGE
    find_match.assert_not_called()


def test_category_patterns_keep_first_match_for_overlapping_model_data():
    result = metadata.determine_model_category(
        {
            "id": "vendor/vision-image",
            "name": "Vision Image",
            "architecture": {"modality": "text"},
        }
    )

    assert result is metadata.ModelCategory.IMAGE


def test_category_pattern_result_precedes_later_fallbacks(monkeypatch):
    find_match = Mock(return_value=metadata.ModelCategory.CODE)
    monkeypatch.setattr(metadata, "_find_first_pattern_match", find_match)

    result = metadata.determine_model_category(
        {
            "id": "vendor/embedding-model",
            "name": "Embedding Model",
            "architecture": {"modality": "text"},
        }
    )

    assert result is metadata.ModelCategory.CODE
    find_match.assert_called_once_with(
        "vendor/embedding-model embedding model text",
        metadata.CATEGORY_PATTERNS,
    )
