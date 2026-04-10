import pytest

from src.openrouter_mcp.runtime_thrift import get_runtime_thrift_policy, reset_runtime_thrift_policy


class TestRuntimeThriftPolicy:
    @pytest.mark.unit
    def test_runtime_thrift_policy_defaults(self):
        reset_runtime_thrift_policy()

        policy = get_runtime_thrift_policy()

        assert policy.enable_generation_coalescing is True
        assert policy.enable_context_compaction is True
        assert policy.enable_deferred_batch_lane is True
        assert policy.enable_prefix_cache_planner is True
        assert policy.compaction_trigger_ratio == pytest.approx(0.75)
        assert policy.max_interactive_prompt_tokens is None

    @pytest.mark.unit
    def test_runtime_thrift_policy_reads_env_overrides(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_THRIFT_ENABLE_CONTEXT_COMPACTION", "0")
        monkeypatch.setenv("OPENROUTER_THRIFT_ENABLE_PREFIX_CACHE_PLANNER", "false")
        monkeypatch.setenv("OPENROUTER_THRIFT_COMPACTION_TRIGGER_RATIO", "0.9")
        monkeypatch.setenv("OPENROUTER_THRIFT_MAX_INTERACTIVE_PROMPT_TOKENS", "4096")
        monkeypatch.setenv("OPENROUTER_THRIFT_COALESCING_TTL_SECONDS", "45")
        reset_runtime_thrift_policy()

        policy = get_runtime_thrift_policy()

        assert policy.enable_context_compaction is False
        assert policy.enable_prefix_cache_planner is False
        assert policy.compaction_trigger_ratio == pytest.approx(0.9)
        assert policy.max_interactive_prompt_tokens == 4096
        assert policy.coalescing_ttl_seconds == 45

    @pytest.mark.unit
    def test_runtime_thrift_policy_allows_zero_ttl_to_disable_recent_reuse(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_THRIFT_COALESCING_TTL_SECONDS", "0")
        reset_runtime_thrift_policy()

        policy = get_runtime_thrift_policy()

        assert policy.coalescing_ttl_seconds == 0
