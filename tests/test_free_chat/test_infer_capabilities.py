"""Tests for capability inference and text extraction helpers."""

import pytest

from src.openrouter_mcp.handlers.free_chat import (
    FreeChatRequest,
    _build_free_chat_messages,
    _extract_text_for_classification,
    _infer_required_capabilities,
)

pytestmark = pytest.mark.unit


class TestBuildFreeChatMessages:
    def test_builds_minimal_string_message(self):
        request = FreeChatRequest(message="hello")

        assert _build_free_chat_messages(request) == [
            {"role": "user", "content": "hello"}
        ]

    def test_preserves_truthy_whitespace_system_prompt(self):
        request = FreeChatRequest(message="hello", system_prompt=" ")

        assert _build_free_chat_messages(request) == [
            {"role": "system", "content": " "},
            {"role": "user", "content": "hello"},
        ]

    def test_preserves_history_and_multimodal_aliasing_without_mutation(self):
        request = FreeChatRequest(
            message=[
                {"type": "text", "text": "describe"},
                {"type": "image_url", "image_url": {"url": "https://example.com/img"}},
            ],
            system_prompt="system",
            conversation_history=[
                {"role": "user", "content": "old question"},
                {"role": "assistant", "content": "old answer"},
            ],
        )
        original_history = list(request.conversation_history)
        request_message = request.message

        messages = _build_free_chat_messages(request)

        assert messages == [
            {"role": "system", "content": "system"},
            *original_history,
            {"role": "user", "content": request_message},
        ]
        assert messages[1] is request.conversation_history[0]
        assert messages[2] is request.conversation_history[1]
        assert messages[-1]["content"] is request_message
        assert request.conversation_history == original_history
        assert all(
            current is original
            for current, original in zip(request.conversation_history, original_history)
        )


class TestExtractTextForClassification:
    def test_string_passthrough(self):
        assert _extract_text_for_classification("hello") == "hello"

    def test_multimodal_extracts_text_parts(self):
        parts = [
            {"type": "text", "text": "Describe"},
            {"type": "image_url", "image_url": {"url": "http://img.png"}},
            {"type": "text", "text": "this image"},
        ]
        result = _extract_text_for_classification(parts)
        assert result == "Describe this image"

    def test_no_text_parts(self):
        parts = [{"type": "image_url", "image_url": {"url": "http://img.png"}}]
        assert _extract_text_for_classification(parts) == ""


class TestInferRequiredCapabilities:
    def test_text_only_returns_none(self):
        messages = [{"role": "user", "content": "Hello"}]
        assert _infer_required_capabilities(messages) is None

    def test_image_url_requires_vision(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is this?"},
                    {"type": "image_url", "image_url": {"url": "http://img.png"}},
                ],
            }
        ]
        result = _infer_required_capabilities(messages)
        assert result == {"supports_vision": True}

    def test_image_in_history(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "http://old.png"}},
                ],
            },
            {"role": "assistant", "content": "I see a cat."},
            {"role": "user", "content": "Tell me more."},
        ]
        result = _infer_required_capabilities(messages)
        assert result == {"supports_vision": True}

    def test_no_image_in_list_content(self):
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Just text"}],
            }
        ]
        assert _infer_required_capabilities(messages) is None


class TestMalformedMultimodalInput:
    """Verify graceful handling of malformed multimodal parts."""

    def test_extract_skips_non_dict_parts(self):
        parts = [
            "not a dict",
            42,
            {"type": "text", "text": "valid"},
        ]
        assert _extract_text_for_classification(parts) == "valid"

    def test_extract_coerces_non_string_text(self):
        parts = [{"type": "text", "text": 123}]
        assert _extract_text_for_classification(parts) == "123"

    def test_infer_skips_non_dict_parts(self):
        messages = [{"role": "user", "content": ["just a string", 42]}]
        assert _infer_required_capabilities(messages) is None
