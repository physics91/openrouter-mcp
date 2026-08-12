"""Characterization tests for unified model-cache filtering."""

from dataclasses import replace
from typing import Any

import pytest

from openrouter_mcp.models.cache import ModelCache, ModelFilter


@pytest.fixture
def model_cache(tmp_path):
    cache = ModelCache(cache_file=str(tmp_path / "models.json"))
    yield cache
    cache.shutdown()


@pytest.fixture
def fully_matching_model() -> dict[str, Any]:
    return {
        "id": "openai/o1-reasoning",
        "provider": "openai",
        "category": "chat",
        "capabilities": {
            "max_tokens": 200_000,
            "supports_tools": True,
            "supports_vision": True,
        },
        "performance_tier": "premium",
        "cost_tier": "paid",
        "quality_score": 0.9,
        "tags": ["reliable", "fast"],
        "description": "Reasoning model",
        "context_length": 200_001,
    }


@pytest.fixture
def fully_matching_filter() -> ModelFilter:
    return ModelFilter(
        provider="OPENAI",
        category="CHAT",
        capabilities={
            "min_context_length": 100_000,
            "supports_tools": True,
        },
        performance_tier="premium",
        cost_tier="paid",
        min_quality_score=0.8,
        tags=["missing", "fast"],
        vision_capable=True,
        reasoning_model=True,
        long_context=True,
        free_only=False,
        min_context=200_000,
    )


def test_matches_filter_accepts_all_populated_constraints(
    model_cache: ModelCache,
    fully_matching_model: dict[str, Any],
    fully_matching_filter: ModelFilter,
) -> None:
    assert model_cache._matches_filter(fully_matching_model, fully_matching_filter)


@pytest.mark.parametrize(
    "filter_update",
    [
        {"provider": "anthropic"},
        {"category": "image"},
        {"capabilities": {"supports_tools": False}},
        {"capabilities": {"min_context_length": 200_001}},
        {"performance_tier": "economy"},
        {"cost_tier": "free"},
        {"min_quality_score": 0.91},
        {"tags": ["missing"]},
        {"vision_capable": False},
        {"reasoning_model": False},
        {"long_context": False},
        {"free_only": True},
        {"min_context": 200_002},
    ],
)
def test_matches_filter_rejects_each_mismatched_constraint(
    model_cache: ModelCache,
    fully_matching_model: dict[str, Any],
    fully_matching_filter: ModelFilter,
    filter_update: dict[str, Any],
) -> None:
    filters = replace(fully_matching_filter, **filter_update)

    assert not model_cache._matches_filter(fully_matching_model, filters)


class RecordingDict(dict):
    """Record get() order without changing dict behavior."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_calls: list[str] = []

    def get(self, key, default=None):
        self.get_calls.append(key)
        return super().get(key, default)


def test_matches_filter_reads_id_before_short_circuiting_provider(
    model_cache: ModelCache,
) -> None:
    model = RecordingDict({"id": "test-model", "provider": "openai"})

    assert not model_cache._matches_filter(model, ModelFilter(provider="anthropic"))
    assert model.get_calls == ["id", "provider"]


def test_matches_filter_without_filters_only_reads_id(model_cache: ModelCache) -> None:
    model = RecordingDict({"id": "test-model"})

    assert model_cache._matches_filter(model, ModelFilter())
    assert model.get_calls == ["id"]
