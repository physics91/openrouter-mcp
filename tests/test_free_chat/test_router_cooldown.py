import time

import pytest


class TestCooldownManagement:
    @pytest.mark.unit
    def test_model_available_by_default(self, router):
        assert router._is_available("google/gemma-3:free") is True

    @pytest.mark.unit
    def test_report_rate_limit_makes_unavailable(self, router):
        router.report_rate_limit("google/gemma-3:free")
        assert router._is_available("google/gemma-3:free") is False

    @pytest.mark.unit
    def test_cooldown_expires(self, router):
        router.report_rate_limit("google/gemma-3:free", cooldown_seconds=0.1)
        assert router._is_available("google/gemma-3:free") is False
        time.sleep(0.15)
        assert router._is_available("google/gemma-3:free") is True

    @pytest.mark.unit
    def test_cleanup_expired_cooldowns(self, router):
        router.report_rate_limit("model-a", cooldown_seconds=0.1)
        router.report_rate_limit("model-b", cooldown_seconds=10.0)
        time.sleep(0.15)
        router._cleanup_expired_cooldowns()
        assert "model-a" not in router._cooldowns
        assert "model-b" in router._cooldowns

    @pytest.mark.unit
    def test_multiple_rate_limits(self, router):
        router.report_rate_limit("model-a")
        router.report_rate_limit("model-b")
        assert router._is_available("model-a") is False
        assert router._is_available("model-b") is False
        assert router._is_available("model-c") is True
