from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def free_model_google():
    return {
        "id": "google/gemma-3-27b-it:free",
        "name": "Gemma 3 27B",
        "context_length": 131072,
        "cost_tier": "free",
        "provider": "google",
        "capabilities": {
            "supports_vision": True,
            "supports_function_calling": False,
        },
    }


@pytest.fixture
def free_model_meta():
    return {
        "id": "meta-llama/llama-4-scout:free",
        "name": "Llama 4 Scout",
        "context_length": 32768,
        "cost_tier": "free",
        "provider": "meta",
        "capabilities": {
            "supports_vision": False,
            "supports_function_calling": False,
        },
    }


@pytest.fixture
def free_model_unknown():
    return {
        "id": "unknown-org/some-model:free",
        "name": "Some Model",
        "context_length": 8192,
        "cost_tier": "free",
        "provider": "unknown",
        "capabilities": {},
    }


class TestFreeModelRouterScoring:
    @pytest.mark.unit
    def test_score_google_model_higher_than_meta(
        self, router, free_model_google, free_model_meta
    ):
        score_google = router._score_model(free_model_google)
        score_meta = router._score_model(free_model_meta)
        assert score_google > score_meta

    @pytest.mark.unit
    def test_score_meta_higher_than_unknown(
        self, router, free_model_meta, free_model_unknown
    ):
        score_meta = router._score_model(free_model_meta)
        score_unknown = router._score_model(free_model_unknown)
        assert score_meta > score_unknown

    @pytest.mark.unit
    def test_score_range_is_zero_to_one(self, router, free_model_google):
        score = router._score_model(free_model_google)
        assert 0.0 <= score <= 1.0

    @pytest.mark.unit
    def test_score_vision_bonus(self, router, free_model_google):
        score_google = router._score_model(free_model_google)
        no_vision = {
            **free_model_google,
            "capabilities": {
                "supports_vision": False,
                "supports_function_calling": False,
            },
        }
        score_no_vision = router._score_model(no_vision)
        assert score_google > score_no_vision

    @pytest.mark.unit
    def test_score_empty_capabilities(self, router, free_model_unknown):
        score = router._score_model(free_model_unknown)
        assert 0.0 <= score <= 1.0

    @pytest.mark.unit
    def test_available_candidate_scoring_decays_only_active_usage(self, router):
        first = {"id": "first"}
        second = {"id": "second"}
        models = [first, second]
        router._usage_counts = {"first": 3, "second": 1, "inactive": 9}
        router._is_available = Mock(return_value=True)
        router._score_model = Mock(side_effect=[0.9, 0.5])

        candidates = router._score_available_candidates(models, None)

        assert router._usage_counts == {"first": 2, "second": 0, "inactive": 9}
        assert candidates[0][0] is first
        assert candidates[1][0] is second
        assert models == [first, second]

    @pytest.mark.unit
    def test_unavailable_candidate_is_not_scored(self, router):
        unavailable = {"id": "unavailable"}
        available = {"id": "available"}
        router._is_available = Mock(side_effect=[False, True])
        router._score_model = Mock(return_value=0.5)

        candidates = router._score_available_candidates(
            [unavailable, available],
            None,
        )

        assert candidates == [(available, 0.5)]
        router._score_model.assert_called_once_with(available, None)

    @pytest.mark.unit
    def test_available_candidate_ties_preserve_input_identity_and_order(self, router):
        first = {"id": "first"}
        second = {"id": "second"}
        router._is_available = Mock(return_value=True)
        router._score_model = Mock(return_value=0.5)

        candidates = router._score_available_candidates([first, second], None)

        assert candidates[0] == (first, 0.5)
        assert candidates[1] == (second, 0.5)
        assert candidates[0][0] is first
        assert candidates[1][0] is second

    @pytest.mark.unit
    def test_no_available_candidates_preserves_cooldown_message(self, router):
        router._cooldowns = {"first": 110.0, "second": 120.0}
        router._is_available = Mock(return_value=False)
        router._score_model = Mock()

        with patch(
            "src.openrouter_mcp.free.router.time.time", return_value=100.0
        ) as now:
            with pytest.raises(
                RuntimeError,
                match="사용 가능한 free 모델이 없습니다. 10초 후 재시도해주세요.",
            ):
                router._score_available_candidates(
                    [{"id": "first"}, {"id": "second"}],
                    None,
                )

        now.assert_called_once_with()
        router._score_model.assert_not_called()
