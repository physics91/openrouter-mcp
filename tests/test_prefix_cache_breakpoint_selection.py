from copy import deepcopy
from unittest.mock import Mock, call

import pytest

from src.openrouter_mcp.runtime_thrift import prefix_cache
from src.openrouter_mcp.runtime_thrift.policy import reset_runtime_thrift_policy

pytestmark = pytest.mark.unit


def test_select_prefix_cache_breakpoint_preserves_scan_order_and_latest_match(
    monkeypatch,
):
    messages = [
        {"role": "system", "content": "first"},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "third"},
        {"role": "user", "content": "last"},
    ]
    original = deepcopy(messages)
    events = []

    def count(candidate, model_id):
        events.append(("count", len(candidate), model_id))
        assert all(
            received is expected for received, expected in zip(candidate, messages)
        )
        return len(candidate) * 10

    def probe(message):
        index = messages.index(message)
        events.append(("probe", index))
        return {"eligible": index} if index in {1, 2} else None

    monkeypatch.setattr(prefix_cache, "count_message_tokens", count)
    monkeypatch.setattr(prefix_cache, "_apply_breakpoint_to_message", probe)

    result = prefix_cache._select_prefix_cache_breakpoint(
        messages,
        "anthropic/model",
        minimum_tokens=20,
    )

    assert result == (2, 30)
    assert events == [
        ("count", 1, "anthropic/model"),
        ("count", 2, "anthropic/model"),
        ("probe", 1),
        ("count", 3, "anthropic/model"),
        ("probe", 2),
    ]
    assert messages == original


def test_select_prefix_cache_breakpoint_never_probes_below_minimum(monkeypatch):
    messages = [
        {"content": "first"},
        {"content": "second"},
        {"content": "last"},
    ]
    count = Mock(side_effect=[1, 2])
    probe = Mock(side_effect=AssertionError("probe must not run"))
    monkeypatch.setattr(prefix_cache, "count_message_tokens", count)
    monkeypatch.setattr(prefix_cache, "_apply_breakpoint_to_message", probe)

    assert prefix_cache._select_prefix_cache_breakpoint(messages, "model", 3) == (
        None,
        0,
    )
    assert count.call_args_list == [
        call([messages[0]], "model"),
        call(messages[:2], "model"),
    ]
    probe.assert_not_called()


def test_select_prefix_cache_breakpoint_returns_none_for_ineligible_candidates(
    monkeypatch,
):
    messages = [{"content": "first"}, {"content": "last"}]
    monkeypatch.setattr(prefix_cache, "count_message_tokens", Mock(return_value=10))
    monkeypatch.setattr(
        prefix_cache,
        "_apply_breakpoint_to_message",
        Mock(return_value=None),
    )

    assert prefix_cache._select_prefix_cache_breakpoint(messages, "model", 10) == (
        None,
        0,
    )


def test_select_prefix_cache_breakpoint_propagates_failure_in_scan_order(monkeypatch):
    messages = [
        {"content": "first"},
        {"content": "second"},
        {"content": "last"},
    ]
    expected_error = RuntimeError("count failed")
    count = Mock(side_effect=[10, expected_error])
    probe = Mock(return_value={"eligible": True})
    monkeypatch.setattr(prefix_cache, "count_message_tokens", count)
    monkeypatch.setattr(prefix_cache, "_apply_breakpoint_to_message", probe)

    with pytest.raises(RuntimeError) as exc_info:
        prefix_cache._select_prefix_cache_breakpoint(messages, "model", 10)

    assert exc_info.value is expected_error
    assert count.call_count == 2
    probe.assert_called_once_with(messages[0])


def test_apply_prefix_cache_planner_delegates_selection_on_copied_messages(
    monkeypatch,
):
    reset_runtime_thrift_policy()
    messages = [
        {"role": "system", "content": "stable"},
        {"role": "user", "content": "latest"},
    ]
    original = deepcopy(messages)
    updated = {"role": "system", "content": [{"cache_control": {"type": "ephemeral"}}]}
    received_messages = None

    def select(candidate_messages, model_id, minimum_tokens):
        nonlocal received_messages
        received_messages = candidate_messages
        assert candidate_messages == messages
        assert candidate_messages is not messages
        assert all(
            received is not source
            for received, source in zip(candidate_messages, messages)
        )
        assert model_id == "anthropic/claude-sonnet-4"
        assert minimum_tokens == 1024
        return 0, 1234

    apply_breakpoint = Mock(return_value=updated)
    monkeypatch.setattr(prefix_cache, "_select_prefix_cache_breakpoint", select)
    monkeypatch.setattr(
        prefix_cache,
        "_apply_breakpoint_to_message",
        apply_breakpoint,
    )

    plan = prefix_cache.apply_prefix_cache_planner(
        messages,
        "anthropic/claude-sonnet-4",
    )

    assert received_messages is not None
    apply_breakpoint.assert_called_once_with(received_messages[0])
    assert plan == prefix_cache.PrefixCachePlan(
        messages=[updated, received_messages[1]],
        applied=True,
        provider="anthropic",
        breakpoint_message_index=0,
        cacheable_prompt_tokens=1234,
        minimum_cacheable_tokens=1024,
    )
    assert messages == original
