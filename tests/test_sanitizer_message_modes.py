from unittest.mock import Mock

import pytest

from src.openrouter_mcp.utils.sanitizer import SensitiveDataSanitizer


@pytest.mark.parametrize(
    ("mode", "content", "expected"),
    [
        (
            "hash",
            "secret-value",
            {
                "role": "user",
                "content_hash": "sha256:31160254d1297393...",
                "content_length": 12,
            },
        ),
        (
            "hash",
            ["secret-value", {"type": "image_url"}],
            {"role": "user", "content_type": "multimodal", "content_parts": 2},
        ),
        ("hash", 42, {"role": "user"}),
        (
            "truncate",
            "x" * 60,
            {
                "role": "user",
                "content": "x" * 50 + "... [TRUNCATED: 60 chars total]",
            },
        ),
        (
            "truncate",
            ["secret-value", {"type": "image_url"}],
            {"role": "user", "content_type": "multimodal", "content_parts": 2},
        ),
        ("truncate", 42, {"role": "user"}),
        (
            "metadata",
            "secret-value",
            {"role": "user", "content_length": 12, "content_type": "text"},
        ),
        (
            "metadata",
            ["secret-value", {"type": "image_url"}],
            {"role": "user", "content_type": "multimodal", "content_parts": 2},
        ),
        ("metadata", 42, {"role": "user"}),
    ],
)
def test_sanitize_messages_preserves_mode_content_matrix(mode, content, expected):
    sanitized = SensitiveDataSanitizer.sanitize_messages(
        [{"role": "user", "content": content}], mode=mode
    )

    assert sanitized == [expected]
    assert list(sanitized[0]) == list(expected)


def test_sanitize_messages_preserves_invalid_mode_and_missing_field_defaults():
    assert SensitiveDataSanitizer.sanitize_messages(
        [{"role": "user", "content": "secret-value"}], mode="invalid"
    ) == [{"role": "user"}]
    assert SensitiveDataSanitizer.sanitize_messages([{}], mode="hash") == [
        {"role": "unknown", "content_hash": "EMPTY", "content_length": 0}
    ]


def test_sanitize_messages_preserves_role_then_content_access_order():
    calls = []

    class RecordingDict(dict):
        def get(self, key, default=None):
            calls.append((key, default))
            return super().get(key, default)

    messages = [RecordingDict(role="user", content="secret-value")]

    SensitiveDataSanitizer.sanitize_messages(messages, mode="metadata")

    assert calls == [("role", "unknown"), ("content", "")]


def test_sanitize_messages_keeps_public_hash_hook(monkeypatch):
    hash_content = Mock(return_value="safe-hash")
    monkeypatch.setattr(SensitiveDataSanitizer, "hash_content", hash_content)

    sanitized = SensitiveDataSanitizer.sanitize_messages(
        [{"role": "user", "content": "secret-value"}], mode="hash"
    )

    assert sanitized == [
        {"role": "user", "content_hash": "safe-hash", "content_length": 12}
    ]
    hash_content.assert_called_once_with("secret-value")


@pytest.mark.parametrize("mode", ["hash", "metadata"])
def test_sanitize_messages_does_not_expose_content_in_non_verbose_modes(mode):
    secret = "fake-secret-do-not-log"
    sanitized = SensitiveDataSanitizer.sanitize_messages(
        [
            {"role": "user", "content": secret},
            {"role": "user", "content": [{"type": "text", "text": secret}]},
        ],
        mode=mode,
    )

    assert secret not in repr(sanitized)
