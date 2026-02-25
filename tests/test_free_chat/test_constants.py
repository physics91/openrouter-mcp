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
