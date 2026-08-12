import pytest

from src.openrouter_mcp.runtime_thrift import (
    get_thrift_metrics_snapshot,
    reset_runtime_thrift_policy,
    reset_thrift_metrics,
)
from src.openrouter_mcp.runtime_thrift.compaction import (
    _calculate_compaction_trigger_threshold,
    _partition_compaction_messages,
    compact_messages,
)
from src.openrouter_mcp.runtime_thrift.policy import RuntimeThriftPolicy


@pytest.mark.unit
@pytest.mark.parametrize(
    (
        "context_window_tokens",
        "max_completion_tokens",
        "trigger_ratio",
        "policy",
        "expected",
    ),
    [
        (8192, None, None, RuntimeThriftPolicy(), 5376),
        (100, None, None, RuntimeThriftPolicy(), 56),
        (100, 20, 0.5, RuntimeThriftPolicy(), 40),
        (
            100,
            20,
            None,
            RuntimeThriftPolicy(max_interactive_prompt_tokens=30),
            22,
        ),
        (100, -10, 0.5, RuntimeThriftPolicy(), 55),
        (
            100,
            20,
            None,
            RuntimeThriftPolicy(max_interactive_prompt_tokens=0),
            1,
        ),
    ],
)
def test_calculate_compaction_trigger_threshold_preserves_budget_arithmetic(
    context_window_tokens,
    max_completion_tokens,
    trigger_ratio,
    policy,
    expected,
):
    assert (
        _calculate_compaction_trigger_threshold(
            context_window_tokens,
            max_completion_tokens,
            trigger_ratio,
            policy,
        )
        == expected
    )


@pytest.mark.unit
def test_explicit_trigger_ratio_skips_policy_ratio_access():
    class ExplicitRatioPolicy:
        max_interactive_prompt_tokens = None

        @property
        def compaction_trigger_ratio(self):
            raise AssertionError("policy ratio must not be read")

    assert (
        _calculate_compaction_trigger_threshold(
            context_window_tokens=100,
            max_completion_tokens=20,
            trigger_ratio=0.5,
            policy=ExplicitRatioPolicy(),
        )
        == 40
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("trigger_ratio", "error_type"),
    [(float("nan"), ValueError), (float("inf"), OverflowError)],
)
def test_calculate_compaction_trigger_threshold_preserves_non_finite_errors(
    trigger_ratio, error_type
):
    with pytest.raises(error_type):
        _calculate_compaction_trigger_threshold(
            context_window_tokens=100,
            max_completion_tokens=20,
            trigger_ratio=trigger_ratio,
            policy=RuntimeThriftPolicy(),
        )


@pytest.mark.unit
def test_partition_compaction_messages_preserves_prefix_and_recent_overlap():
    messages = [
        {"role": "system", "content": "system one"},
        {"role": "system", "content": "system two"},
        {"role": "user", "content": "archived one"},
        {"role": "assistant", "content": "archived two"},
        {"role": "user", "content": "archived three"},
        {"role": "assistant", "content": "recent one"},
        {"role": "user", "content": "recent two"},
    ]

    assert _partition_compaction_messages(messages, 2) == (
        messages[:2],
        messages[2:5],
        messages[5:],
    )


@pytest.mark.unit
@pytest.mark.parametrize("recent_message_count", [2, 0])
def test_partition_compaction_messages_returns_none_without_archived_messages(
    recent_message_count,
):
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "body one"},
        {"role": "assistant", "content": "body two"},
    ]

    assert _partition_compaction_messages(messages, recent_message_count) is None


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
