from copy import deepcopy
from unittest.mock import AsyncMock, Mock, call

import pytest


class TestBuildModelStatus:
    @pytest.mark.unit
    def test_builds_exact_schema_with_rounded_score_and_availability(self, router):
        model = {
            "id": "google/gemma:free",
            "name": "Gemma",
            "context_length": 131072,
            "provider": "google",
        }
        router._score_model = Mock(return_value=0.87654)
        router._is_available = Mock(return_value=False)

        result = router._build_model_status(model)

        assert list(result) == [
            "id",
            "name",
            "context_length",
            "provider",
            "quality_score",
            "available",
        ]
        assert result == {
            "id": "google/gemma:free",
            "name": "Gemma",
            "context_length": 131072,
            "provider": "google",
            "quality_score": 0.877,
            "available": False,
        }
        router._score_model.assert_called_once_with(model)
        router._is_available.assert_called_once_with("google/gemma:free")

    @pytest.mark.unit
    def test_builds_existing_defaults_for_missing_fields(self, router):
        model = {}
        router._score_model = Mock(return_value=0.0)
        router._is_available = Mock(return_value=True)

        result = router._build_model_status(model)

        assert result == {
            "id": "",
            "name": "",
            "context_length": 0,
            "provider": "unknown",
            "quality_score": 0.0,
            "available": True,
        }
        router._score_model.assert_called_once_with(model)
        router._is_available.assert_called_once_with("")


class TestListModelsWithStatus:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_builds_in_input_order_then_stably_sorts_by_quality(self, router):
        models = [
            {"id": "first"},
            {"id": "second"},
            {"id": "third"},
        ]
        original_models = deepcopy(models)
        first_status = {"quality_score": 0.4}
        second_status = {"quality_score": 0.9}
        third_status = {"quality_score": 0.9}
        events = []

        async def ensure_cache_ready():
            events.append("ensure")

        def filter_models(*, free_only):
            events.append(("filter", free_only))
            return models

        def build_status(model):
            events.append(("build", model["id"]))
            return {
                "first": first_status,
                "second": second_status,
                "third": third_status,
            }[model["id"]]

        router._cache.ensure_cache_ready = AsyncMock(side_effect=ensure_cache_ready)
        router._cache.filter_models = Mock(side_effect=filter_models)
        router._build_model_status = Mock(side_effect=build_status)

        result = await router.list_models_with_status()

        assert result == [second_status, third_status, first_status]
        assert result[0] is second_status
        assert result[1] is third_status
        assert result[2] is first_status
        assert events == [
            "ensure",
            ("filter", True),
            ("build", "first"),
            ("build", "second"),
            ("build", "third"),
        ]
        assert router._build_model_status.call_args_list == [
            call(models[0]),
            call(models[1]),
            call(models[2]),
        ]
        assert models == original_models

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stops_building_and_propagates_helper_failure(self, router):
        models = [
            {"id": "first"},
            {"id": "second"},
            {"id": "third"},
        ]
        router._cache.filter_models.return_value = models
        router._build_model_status = Mock(
            side_effect=[
                {"quality_score": 0.4},
                RuntimeError("status failed"),
            ]
        )

        with pytest.raises(RuntimeError, match="status failed"):
            await router.list_models_with_status()

        assert router._build_model_status.call_args_list == [
            call(models[0]),
            call(models[1]),
        ]
