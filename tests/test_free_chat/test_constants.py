import pytest

from src.openrouter_mcp.config.constants import FreeChatConfig


class TestFreeChatConfig:
    @pytest.mark.unit
    def test_default_cooldown_seconds(self):
        assert FreeChatConfig.DEFAULT_COOLDOWN_SECONDS == 60.0

    @pytest.mark.unit
    def test_max_retry_count(self):
        assert FreeChatConfig.MAX_RETRY_COUNT == 3

    @pytest.mark.unit
    def test_max_tokens(self):
        assert FreeChatConfig.MAX_TOKENS == 4096

    @pytest.mark.unit
    def test_scoring_weights_sum_to_one(self):
        total = (
            FreeChatConfig.CONTEXT_LENGTH_WEIGHT
            + FreeChatConfig.REPUTATION_WEIGHT
            + FreeChatConfig.FEATURES_WEIGHT
        )
        assert abs(total - 1.0) < 1e-9

    @pytest.mark.unit
    def test_model_reputation_has_known_providers(self):
        assert "google" in FreeChatConfig.MODEL_REPUTATION
        assert "meta" in FreeChatConfig.MODEL_REPUTATION

    @pytest.mark.unit
    def test_default_reputation_score(self):
        assert FreeChatConfig.DEFAULT_REPUTATION == 0.5

    @pytest.mark.unit
    def test_adaptive_config_exists(self):
        assert FreeChatConfig.ADAPTIVE_MIN_REQUESTS == 5
        assert FreeChatConfig.ADAPTIVE_MAX_ALPHA == 0.7
        assert FreeChatConfig.ADAPTIVE_RAMP_REQUESTS == 30

    @pytest.mark.unit
    def test_performance_weights_sum_to_one(self):
        total = (
            FreeChatConfig.PERFORMANCE_SUCCESS_WEIGHT
            + FreeChatConfig.PERFORMANCE_LATENCY_WEIGHT
            + FreeChatConfig.PERFORMANCE_THROUGHPUT_WEIGHT
        )
        assert abs(total - 1.0) < 1e-9

    @pytest.mark.unit
    def test_performance_normalization_constants(self):
        assert FreeChatConfig.MAX_LATENCY_MS == 10000
        assert FreeChatConfig.MAX_TOKENS_PER_SECOND == 50

    @pytest.mark.unit
    def test_quota_limits(self):
        assert FreeChatConfig.FREE_DAILY_LIMIT == 50
        assert FreeChatConfig.FREE_MINUTE_LIMIT == 20
