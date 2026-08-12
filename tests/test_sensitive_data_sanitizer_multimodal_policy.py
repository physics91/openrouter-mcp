from unittest.mock import patch

import pytest

from src.openrouter_mcp.utils.sanitizer import SensitiveDataSanitizer

pytestmark = pytest.mark.unit


def test_multimodal_metadata_preserves_schema_and_key_order():
    content = [{"type": "text"}, {"type": "image_url"}]

    sanitized = SensitiveDataSanitizer._sanitize_multimodal_content(content)

    assert list(sanitized) == ["content_type", "content_parts"]
    assert sanitized == {
        "content_type": "multimodal",
        "content_parts": 2,
    }


@pytest.mark.parametrize(
    "sanitize_name",
    [
        "_sanitize_hashed_message_content",
        "_sanitize_truncated_message_content",
        "_sanitize_message_content_metadata",
    ],
)
def test_message_modes_delegate_multimodal_policy(sanitize_name):
    content = [{"type": "text"}]
    expected = {"content_type": "delegated", "content_parts": 1}

    with patch.object(
        SensitiveDataSanitizer,
        "_sanitize_multimodal_content",
        return_value=expected,
    ) as sanitize_multimodal:
        sanitized = getattr(SensitiveDataSanitizer, sanitize_name)(content)

    assert sanitized is expected
    sanitize_multimodal.assert_called_once_with(content)


@pytest.mark.parametrize(
    "sanitize_name",
    [
        "_sanitize_hashed_message_content",
        "_sanitize_truncated_message_content",
        "_sanitize_message_content_metadata",
    ],
)
def test_message_modes_propagate_multimodal_policy_failure(sanitize_name):
    content = []

    with patch.object(
        SensitiveDataSanitizer,
        "_sanitize_multimodal_content",
        side_effect=RuntimeError("multimodal sanitization failed"),
    ), pytest.raises(RuntimeError, match="multimodal sanitization failed"):
        getattr(SensitiveDataSanitizer, sanitize_name)(content)
