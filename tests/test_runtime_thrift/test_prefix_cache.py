import pytest

from src.openrouter_mcp.runtime_thrift import (
    apply_prefix_cache_planner,
    reset_runtime_thrift_policy,
)


class TestPrefixCachePlanner:
    @pytest.mark.unit
    def test_marks_latest_cacheable_prefix_for_anthropic(self):
        reset_runtime_thrift_policy()
        messages = [
            {"role": "system", "content": "stable instruction block " * 1500},
            {"role": "user", "content": "latest question"},
        ]

        plan = apply_prefix_cache_planner(
            messages=messages,
            model_id="anthropic/claude-sonnet-4",
        )

        assert plan.applied is True
        assert plan.provider == "anthropic"
        assert plan.breakpoint_message_index == 0
        assert isinstance(plan.messages[0]["content"], list)
        assert plan.messages[0]["content"][-1]["cache_control"] == {"type": "ephemeral"}
        assert plan.messages[1] == messages[1]

    @pytest.mark.unit
    def test_skips_models_with_implicit_caching(self):
        messages = [
            {"role": "system", "content": "stable instruction block " * 1500},
            {"role": "user", "content": "latest question"},
        ]

        plan = apply_prefix_cache_planner(
            messages=messages,
            model_id="openai/gpt-4o",
        )

        assert plan.applied is False
        assert plan.messages == messages

    @pytest.mark.unit
    def test_skips_when_explicit_prefix_is_below_minimum(self):
        messages = [
            {"role": "system", "content": "tiny prefix"},
            {"role": "user", "content": "latest question"},
        ]

        plan = apply_prefix_cache_planner(
            messages=messages,
            model_id="anthropic/claude-sonnet-4",
        )

        assert plan.applied is False
        assert plan.messages == messages

    @pytest.mark.unit
    def test_skips_when_policy_disabled(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_THRIFT_ENABLE_PREFIX_CACHE_PLANNER", "false")
        reset_runtime_thrift_policy()
        messages = [
            {"role": "system", "content": "stable instruction block " * 1500},
            {"role": "user", "content": "latest question"},
        ]

        plan = apply_prefix_cache_planner(
            messages=messages,
            model_id="anthropic/claude-sonnet-4",
        )

        assert plan.applied is False
        assert plan.messages == messages
