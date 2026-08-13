"""Regression tests for prepared ModelCache identity filters."""

import threading
from typing import Any, Dict, List

import pytest

from openrouter_mcp.models.cache import ModelCache, ModelFilter


class RecordingDict(dict):
    """Record key access without changing dictionary behavior."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.get_calls: List[str] = []

    def get(self, key: str, default: Any = None) -> Any:
        self.get_calls.append(key)
        return super().get(key, default)


class TrackingValue:
    """Count normalizations to prove custom filter values use the legacy path."""

    str_calls = 0

    def __str__(self) -> str:
        type(self).str_calls += 1
        return "openai"


def make_cache(models: List[Dict[str, Any]]) -> ModelCache:
    """Create a minimal cache without file, executor, or network side effects."""
    cache = object.__new__(ModelCache)
    cache._cache_lock = threading.RLock()
    cache._memory_cache = models
    return cache


@pytest.mark.parametrize(
    "filters",
    [
        ModelFilter(),
        ModelFilter(provider="OpenAI"),
        ModelFilter(provider="OpenAI", category="chat"),
        ModelFilter(
            provider="OpenAI",
            category="chat",
            capabilities={"streaming": True},
            performance_tier="premium",
            min_quality_score=0.8,
            tags=["fast"],
            vision_capable=True,
            long_context=True,
            min_context=120_000,
        ),
    ],
)
def test_prepared_filters_match_canonical_pipeline(filters: ModelFilter) -> None:
    models = [
        {
            "id": "openai/gpt-vision",
            "provider": "OPENAI",
            "category": "CHAT",
            "capabilities": {"streaming": True, "supports_vision": True},
            "performance_tier": "premium",
            "quality_score": 0.9,
            "tags": ["fast", "vision"],
            "context_length": 128_000,
        },
        {
            "id": "openai/gpt-small",
            "provider": "openai",
            "category": "chat",
            "capabilities": {"streaming": False},
            "performance_tier": "economy",
            "quality_score": 0.6,
            "tags": ["cheap"],
            "context_length": 16_000,
        },
        {
            "id": "anthropic/claude",
            "provider": "anthropic",
            "category": "chat",
            "capabilities": {"streaming": True},
            "performance_tier": "premium",
            "quality_score": 0.95,
            "tags": ["fast"],
            "context_length": 200_000,
        },
    ]
    cache = make_cache(models)
    expected = [model for model in models if cache._matches_filter(model, filters)]

    actual = cache._filter_models_internal(filters)

    assert len(actual) == len(expected)
    assert all(result is reference for result, reference in zip(actual, expected))


def test_prepared_filters_preserve_model_get_order() -> None:
    model = RecordingDict(id="test/model", provider="anthropic", category="chat")
    cache = make_cache([model])

    assert cache._filter_models_internal(ModelFilter(provider="openai")) == []
    assert model.get_calls == ["id", "provider"]


def test_empty_cache_does_not_normalize_filter() -> None:
    class ExplodingString(str):
        def lower(self) -> str:
            raise AssertionError("empty caches must not normalize filters")

    cache = make_cache([])

    assert (
        cache._filter_models_internal(ModelFilter(provider=ExplodingString("x"))) == []
    )


def test_custom_filter_value_uses_legacy_normalization_frequency() -> None:
    TrackingValue.str_calls = 0
    models = [
        {"id": "one", "provider": "openai"},
        {"id": "two", "provider": "openai"},
    ]
    cache = make_cache(models)

    assert (
        cache._filter_models_internal(
            ModelFilter(provider=TrackingValue())  # type: ignore[arg-type]
        )
        == models
    )
    assert TrackingValue.str_calls == len(models)


def test_instance_filter_hook_uses_legacy_pipeline() -> None:
    models = [{"id": "one"}, {"id": "two"}]
    cache = make_cache(models)
    seen: List[Dict[str, Any]] = []

    def matches_filter(model: Dict[str, Any], filters: ModelFilter) -> bool:
        seen.append(model)
        return model["id"] == "two"

    cache._matches_filter = matches_filter  # type: ignore[method-assign]

    assert cache._filter_models_internal(ModelFilter()) == [models[1]]
    assert seen == models


def test_cache_subclass_uses_overridden_filter_pipeline() -> None:
    class CustomModelCache(ModelCache):
        def _matches_filter(self, model: Dict[str, Any], filters: ModelFilter) -> bool:
            return model["id"] == "custom"

    models = [{"id": "canonical"}, {"id": "custom"}]
    cache = object.__new__(CustomModelCache)
    cache._cache_lock = threading.RLock()
    cache._memory_cache = models

    assert cache._filter_models_internal(ModelFilter()) == [models[1]]
