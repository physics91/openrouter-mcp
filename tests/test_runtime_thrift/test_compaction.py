import pytest

from src.openrouter_mcp.runtime_thrift import (
    get_thrift_metrics_snapshot,
    reset_runtime_thrift_policy,
    reset_thrift_metrics,
)
from src.openrouter_mcp.runtime_thrift.compaction import compact_messages


class TestCompaction:
    @pytest.mark.unit
    def test_compact_messages_preserves_system_and_recent_turns(self):
        messages = [
            {"role": "system", "content": "You are concise and helpful."},
            {"role": "user", "content": "older question one " * 40},
            {"role": "assistant", "content": "same older answer " * 40},
            {"role": "user", "content": "older question two " * 40},
            {"role": "assistant", "content": "same older answer " * 40},
            {"role": "user", "content": "recent question one " * 30},
            {"role": "assistant", "content": "recent answer one " * 30},
            {"role": "user", "content": "recent question two " * 30},
            {"role": "assistant", "content": "recent answer two " * 30},
        ]

        result = compact_messages(
            messages=messages,
            model_id="openai/gpt-4",
            context_window_tokens=160,
            max_completion_tokens=16,
        )

        assert result.was_compacted is True
        assert result.messages[0] == messages[0]
        assert result.messages[1]["role"] == "assistant"
        assert "Conversation summary" in result.messages[1]["content"]
        assert result.messages[1]["content"].count("- Assistant:") == 1
        assert result.messages[2:] == messages[-4:]
        assert result.compacted_prompt_tokens < result.original_prompt_tokens

    @pytest.mark.unit
    def test_compact_messages_skips_when_under_budget(self):
        messages = [
            {"role": "system", "content": "You are concise and helpful."},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "what is 2+2?"},
        ]

        result = compact_messages(
            messages=messages,
            model_id="openai/gpt-4",
            context_window_tokens=4096,
            max_completion_tokens=128,
        )

        assert result.was_compacted is False
        assert result.messages == messages
        assert result.compacted_prompt_tokens == result.original_prompt_tokens

    @pytest.mark.unit
    def test_compact_messages_records_saved_token_metric(self):
        reset_thrift_metrics()
        messages = [
            {"role": "system", "content": "You are concise and helpful."},
            {"role": "user", "content": "older question one " * 40},
            {"role": "assistant", "content": "same older answer " * 40},
            {"role": "user", "content": "older question two " * 40},
            {"role": "assistant", "content": "same older answer " * 40},
            {"role": "user", "content": "recent question one " * 30},
            {"role": "assistant", "content": "recent answer one " * 30},
            {"role": "user", "content": "recent question two " * 30},
            {"role": "assistant", "content": "recent answer two " * 30},
        ]

        result = compact_messages(
            messages=messages,
            model_id="openai/gpt-4",
            context_window_tokens=160,
            max_completion_tokens=16,
        )

        metrics = get_thrift_metrics_snapshot()
        assert result.was_compacted is True
        assert metrics["compacted_tokens"] == result.tokens_saved

    @pytest.mark.unit
    def test_compact_messages_skips_when_policy_disabled(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_THRIFT_ENABLE_CONTEXT_COMPACTION", "false")
        reset_runtime_thrift_policy()
        messages = [
            {"role": "system", "content": "You are concise and helpful."},
            {"role": "user", "content": "older question one " * 40},
            {"role": "assistant", "content": "same older answer " * 40},
            {"role": "user", "content": "older question two " * 40},
            {"role": "assistant", "content": "same older answer " * 40},
            {"role": "user", "content": "recent question one " * 30},
            {"role": "assistant", "content": "recent answer one " * 30},
            {"role": "user", "content": "recent question two " * 30},
            {"role": "assistant", "content": "recent answer two " * 30},
        ]

        result = compact_messages(
            messages=messages,
            model_id="openai/gpt-4",
            context_window_tokens=160,
            max_completion_tokens=16,
        )

        assert result.was_compacted is False
        assert result.messages == messages
