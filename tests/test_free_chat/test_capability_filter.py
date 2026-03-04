"""Tests for capability-aware model filtering in FreeModelRouter."""

import pytest

from tests.test_free_chat.conftest import _make_mock_cache, make_free_model
from src.openrouter_mcp.free.router import FreeModelRouter

pytestmark = pytest.mark.unit


def _model_with_caps(model_id, caps):
    m = make_free_model(model_id)
    m["capabilities"] = caps
    return m


class TestFilterByCapabilities:
    def test_no_required_returns_all(self):
        models = [make_free_model("a"), make_free_model("b")]
        result = FreeModelRouter._filter_by_capabilities(models, None)
        assert len(result) == 2

    def test_vision_filter_matches(self):
        models = [
            _model_with_caps("a", {"supports_vision": True}),
            _model_with_caps("b", {"supports_vision": False}),
            _model_with_caps("c", {}),
        ]
        result = FreeModelRouter._filter_by_capabilities(
            models, {"supports_vision": True}
        )
        assert [m["id"] for m in result] == ["a"]

    def test_no_match_returns_empty(self):
        models = [
            _model_with_caps("a", {}),
            _model_with_caps("b", {"supports_vision": False}),
        ]
        result = FreeModelRouter._filter_by_capabilities(
            models, {"supports_vision": True}
        )
        assert result == []


class TestSelectModelWithCapabilities:
    @pytest.mark.asyncio
    async def test_vision_model_selected(self):
        vision_model = _model_with_caps("vision:free", {"supports_vision": True})
        text_model = _model_with_caps("text:free", {})
        cache = _make_mock_cache(filter_return=[vision_model, text_model])
        router = FreeModelRouter(cache)

        model_id = await router.select_model(
            required_capabilities={"supports_vision": True}
        )
        assert model_id == "vision:free"

    @pytest.mark.asyncio
    async def test_no_capable_model_raises(self):
        text_model = _model_with_caps("text:free", {})
        cache = _make_mock_cache(filter_return=[text_model])
        router = FreeModelRouter(cache)

        with pytest.raises(RuntimeError, match="capability"):
            await router.select_model(
                required_capabilities={"supports_vision": True}
            )

    @pytest.mark.asyncio
    async def test_no_capability_requirement_selects_normally(self):
        models = [make_free_model("a:free", 131072, "google")]
        cache = _make_mock_cache(filter_return=models)
        router = FreeModelRouter(cache)

        model_id = await router.select_model(required_capabilities=None)
        assert model_id == "a:free"


class TestUsageDecayWithCapabilities:
    @pytest.mark.asyncio
    async def test_decay_does_not_create_negative_counts(self):
        """Usage decay with capability filter must not create negative counts."""
        vision_model = _model_with_caps("vision:free", {"supports_vision": True})
        text_model = _model_with_caps("text:free", {})
        cache = _make_mock_cache(filter_return=[vision_model, text_model])
        router = FreeModelRouter(cache)

        # Simulate high usage on both models
        router._usage_counts = {"vision:free": 10, "text:free": 5}

        # Select with vision filter — only vision:free is a candidate
        model_id = await router.select_model(
            required_capabilities={"supports_vision": True}
        )
        assert model_id == "vision:free"

        # No count should be negative
        for count in router._usage_counts.values():
            assert count >= 0
