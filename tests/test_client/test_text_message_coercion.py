from unittest.mock import Mock

import pytest

from openrouter_mcp.client import openrouter
from openrouter_mcp.client.openrouter import OpenRouterClient

pytestmark = pytest.mark.unit


class RecordingDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_calls = []

    def get(self, key, default=None):
        self.get_calls.append(key)
        return super().get(key, default)


def test_coerce_text_messages_preserves_two_pass_access_and_copies_values():
    first = RecordingDict({"role": "system", "content": "rules", "extra": 1})
    second = RecordingDict({"role": "user", "content": "hello", "extra": 2})

    result = openrouter._coerce_text_messages([first, second])

    assert result == [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "hello"},
    ]
    assert result[0] is not first
    assert result[1] is not second
    assert first.get_calls == ["content", "role", "content"]
    assert second.get_calls == ["content", "role", "content"]


def test_coerce_text_messages_stops_initial_scan_at_first_non_text_content():
    first = RecordingDict({"role": "user", "content": "hello"})
    second = RecordingDict({"role": "user", "content": ["image"]})
    unread = RecordingDict({"role": "user", "content": "later"})

    assert openrouter._coerce_text_messages([first, second, unread]) is None
    assert first.get_calls == ["content"]
    assert second.get_calls == ["content"]
    assert unread.get_calls == []


def test_coerce_text_messages_stops_second_pass_after_non_string_role():
    first = RecordingDict({"role": 1, "content": "hello"})
    second = RecordingDict({"role": "user", "content": "later"})

    assert openrouter._coerce_text_messages([first, second]) is None
    assert first.get_calls == ["content", "role", "content"]
    assert second.get_calls == ["content"]


def test_coerce_text_messages_keeps_empty_input_as_bypass():
    assert openrouter._coerce_text_messages([]) is None


def test_coerce_text_messages_propagates_mapping_access_failure():
    expected_error = RuntimeError("mapping failed")
    message = RecordingDict({"role": "user", "content": "hello"})

    def fail_get(key, default=None):
        raise expected_error

    message.get = fail_get

    with pytest.raises(RuntimeError) as raised:
        openrouter._coerce_text_messages([message])

    assert raised.value is expected_error


def test_validate_messages_if_text_delegates_coerced_messages(monkeypatch):
    original_messages = [{"opaque": "input"}]
    coerced_messages = [{"role": "user", "content": "hello"}]
    coerce = Mock(return_value=coerced_messages)
    client = Mock()
    monkeypatch.setattr(
        openrouter,
        "_coerce_text_messages",
        coerce,
        raising=False,
    )

    OpenRouterClient._validate_messages_if_text(client, original_messages)

    coerce.assert_called_once_with(original_messages)
    client._validate_messages.assert_called_once_with(coerced_messages)


def test_validate_messages_if_text_skips_validation_when_coercion_bypasses(
    monkeypatch,
):
    original_messages = [{"role": "user", "content": "hello"}]
    coerce = Mock(return_value=None)
    client = Mock()
    monkeypatch.setattr(
        openrouter,
        "_coerce_text_messages",
        coerce,
        raising=False,
    )

    OpenRouterClient._validate_messages_if_text(client, original_messages)

    coerce.assert_called_once_with(original_messages)
    client._validate_messages.assert_not_called()
