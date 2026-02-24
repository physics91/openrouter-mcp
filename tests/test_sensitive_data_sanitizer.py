"""
Unit tests for SensitiveDataSanitizer class.

Tests verify that sensitive data is properly masked, hashed, and sanitized
before being logged, preventing security leaks.
"""

import pytest
from src.openrouter_mcp.client.openrouter import SensitiveDataSanitizer


class TestMaskApiKey:
    """Tests for API key masking functionality."""

    def test_mask_standard_api_key(self):
        """Test masking of a standard length API key."""
        api_key = "sk-or-v1-1234567890abcdef1234567890abcdef"
        masked = SensitiveDataSanitizer.mask_api_key(api_key)

        assert masked.startswith("sk-o")
        assert "***MASKED***" in masked
        assert "1234567890abcdef" not in masked

    def test_mask_short_api_key(self):
        """Test masking of a short API key."""
        api_key = "abc"
        masked = SensitiveDataSanitizer.mask_api_key(api_key)

        assert masked == "***MASKED***"
        assert "abc" not in masked

    def test_mask_empty_api_key(self):
        """Test masking of an empty API key."""
        masked = SensitiveDataSanitizer.mask_api_key("")

        assert masked == "***MASKED***"

    def test_mask_with_custom_visible_chars(self):
        """Test masking with custom number of visible characters."""
        api_key = "sk-or-v1-1234567890"
        masked = SensitiveDataSanitizer.mask_api_key(api_key, visible_chars=8)

        assert masked.startswith("sk-or-v1")
        assert "***MASKED***" in masked


class TestSanitizeHeaders:
    """Tests for header sanitization functionality."""

    def test_sanitize_authorization_bearer(self):
        """Test sanitization of Authorization header with Bearer token."""
        headers = {
            "Authorization": "Bearer sk-or-v1-1234567890abcdef",
            "Content-Type": "application/json"
        }

        sanitized = SensitiveDataSanitizer.sanitize_headers(headers)

        assert "Bearer" in sanitized["Authorization"]
        assert "sk-o" in sanitized["Authorization"]
        assert "***MASKED***" in sanitized["Authorization"]
        assert "1234567890abcdef" not in sanitized["Authorization"]
        assert sanitized["Content-Type"] == "application/json"

    def test_sanitize_api_key_header(self):
        """Test sanitization of X-API-Key header."""
        headers = {
            "X-API-Key": "secret-key-12345",
            "Content-Type": "application/json"
        }

        sanitized = SensitiveDataSanitizer.sanitize_headers(headers)

        assert "***MASKED***" in sanitized["X-API-Key"]
        assert "secret-key-12345" not in sanitized["X-API-Key"]

    def test_sanitize_case_insensitive(self):
        """Test that header sanitization is case-insensitive."""
        headers = {
            "authorization": "Bearer sk-test-123",
            "AUTHORIZATION": "Bearer sk-test-456"
        }

        sanitized = SensitiveDataSanitizer.sanitize_headers(headers)

        assert "***MASKED***" in sanitized["authorization"]
        assert "***MASKED***" in sanitized["AUTHORIZATION"]

    def test_preserve_non_sensitive_headers(self):
        """Test that non-sensitive headers are preserved."""
        headers = {
            "Content-Type": "application/json",
            "X-Title": "MyApp",
            "HTTP-Referer": "https://example.com"
        }

        sanitized = SensitiveDataSanitizer.sanitize_headers(headers)

        assert sanitized == headers


class TestHashContent:
    """Tests for content hashing functionality."""

    def test_hash_content_sha256(self):
        """Test hashing content with SHA256."""
        content = "This is a sensitive user prompt"
        hashed = SensitiveDataSanitizer.hash_content(content)

        assert hashed.startswith("sha256:")
        assert len(hashed) > len("sha256:")
        assert content not in hashed

    def test_hash_content_deterministic(self):
        """Test that hashing is deterministic (same input -> same output)."""
        content = "Test content"
        hash1 = SensitiveDataSanitizer.hash_content(content)
        hash2 = SensitiveDataSanitizer.hash_content(content)

        assert hash1 == hash2

    def test_hash_different_content(self):
        """Test that different content produces different hashes."""
        hash1 = SensitiveDataSanitizer.hash_content("Content A")
        hash2 = SensitiveDataSanitizer.hash_content("Content B")

        assert hash1 != hash2

    def test_hash_empty_content(self):
        """Test hashing of empty content."""
        hashed = SensitiveDataSanitizer.hash_content("")

        assert hashed == "EMPTY"


class TestTruncateContent:
    """Tests for content truncation functionality."""

    def test_truncate_long_content(self):
        """Test truncation of content exceeding max length."""
        content = "A" * 200
        truncated = SensitiveDataSanitizer.truncate_content(content, max_length=50)

        assert len(truncated) < len(content)
        assert truncated.startswith("A" * 50)
        assert "[TRUNCATED:" in truncated
        assert "200 chars total]" in truncated

    def test_truncate_short_content(self):
        """Test that short content is not truncated."""
        content = "Short text"
        truncated = SensitiveDataSanitizer.truncate_content(content, max_length=100)

        assert truncated == content
        assert "[TRUNCATED:" not in truncated

    def test_truncate_empty_content(self):
        """Test truncation of empty content."""
        truncated = SensitiveDataSanitizer.truncate_content("")

        assert truncated == "EMPTY"


class TestSanitizeMessages:
    """Tests for message sanitization functionality."""

    def test_sanitize_messages_hash_mode(self):
        """Test message sanitization in hash mode."""
        messages = [
            {"role": "user", "content": "What is the capital of France?"},
            {"role": "assistant", "content": "The capital of France is Paris."}
        ]

        sanitized = SensitiveDataSanitizer.sanitize_messages(messages, mode="hash")

        assert len(sanitized) == 2
        assert sanitized[0]["role"] == "user"
        assert "content_hash" in sanitized[0]
        assert "content_length" in sanitized[0]
        assert sanitized[0]["content_hash"].startswith("sha256:")
        assert "France" not in str(sanitized)

    def test_sanitize_messages_truncate_mode(self):
        """Test message sanitization in truncate mode."""
        long_content = "A" * 200
        messages = [
            {"role": "user", "content": long_content}
        ]

        sanitized = SensitiveDataSanitizer.sanitize_messages(messages, mode="truncate")

        assert len(sanitized) == 1
        assert sanitized[0]["role"] == "user"
        assert "content" in sanitized[0]
        assert len(sanitized[0]["content"]) < len(long_content)
        assert "[TRUNCATED:" in sanitized[0]["content"]

    def test_sanitize_messages_metadata_mode(self):
        """Test message sanitization in metadata mode."""
        messages = [
            {"role": "user", "content": "Test message"}
        ]

        sanitized = SensitiveDataSanitizer.sanitize_messages(messages, mode="metadata")

        assert len(sanitized) == 1
        assert sanitized[0]["role"] == "user"
        assert "content_length" in sanitized[0]
        assert "content_type" in sanitized[0]
        assert sanitized[0]["content_type"] == "text"
        assert "content" not in sanitized[0]

    def test_sanitize_multimodal_messages(self):
        """Test sanitization of multimodal messages with images."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
                ]
            }
        ]

        sanitized = SensitiveDataSanitizer.sanitize_messages(messages, mode="hash")

        assert len(sanitized) == 1
        assert sanitized[0]["role"] == "user"
        assert sanitized[0]["content_type"] == "multimodal"
        assert sanitized[0]["content_parts"] == 2


class TestSanitizePayload:
    """Tests for payload sanitization functionality."""

    def test_sanitize_payload_basic(self):
        """Test basic payload sanitization."""
        payload = {
            "model": "openai/gpt-4",
            "messages": [
                {"role": "user", "content": "Sensitive user query"}
            ],
            "temperature": 0.7,
            "max_tokens": 100
        }

        sanitized = SensitiveDataSanitizer.sanitize_payload(payload, enable_verbose=False)

        assert sanitized["model"] == "openai/gpt-4"
        assert sanitized["temperature"] == 0.7
        assert sanitized["max_tokens"] == 100
        assert "messages" in sanitized
        # In non-verbose mode, should only have metadata
        assert "content_length" in sanitized["messages"][0]
        assert "Sensitive user query" not in str(sanitized)

    def test_sanitize_payload_verbose(self):
        """Test payload sanitization with verbose mode enabled."""
        payload = {
            "model": "openai/gpt-4",
            "messages": [
                {"role": "user", "content": "A" * 200}
            ],
            "temperature": 0.7
        }

        sanitized = SensitiveDataSanitizer.sanitize_payload(payload, enable_verbose=True)

        assert "messages" in sanitized
        # In verbose mode, should have truncated content
        assert "content" in sanitized["messages"][0]
        assert "[TRUNCATED:" in sanitized["messages"][0]["content"]

    def test_sanitize_payload_preserves_safe_params(self):
        """Test that safe parameters are preserved."""
        payload = {
            "model": "openai/gpt-4",
            "messages": [],
            "top_p": 0.9,
            "frequency_penalty": 0.5,
            "presence_penalty": 0.3,
            "n": 1
        }

        sanitized = SensitiveDataSanitizer.sanitize_payload(payload, enable_verbose=False)

        assert sanitized["top_p"] == 0.9
        assert sanitized["frequency_penalty"] == 0.5
        assert sanitized["presence_penalty"] == 0.3
        assert sanitized["n"] == 1


class TestSanitizeResponse:
    """Tests for response sanitization functionality."""

    def test_sanitize_response_basic(self):
        """Test basic response sanitization."""
        response = {
            "id": "chatcmpl-123",
            "model": "openai/gpt-4",
            "created": 1234567890,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Sensitive AI response content"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }

        sanitized = SensitiveDataSanitizer.sanitize_response(response, enable_verbose=False)

        assert sanitized["id"] == "chatcmpl-123"
        assert sanitized["model"] == "openai/gpt-4"
        assert sanitized["choices_count"] == 1
        assert "usage" in sanitized
        assert "Sensitive AI response content" not in str(sanitized)

    def test_sanitize_response_verbose(self):
        """Test response sanitization with verbose mode enabled."""
        response = {
            "id": "chatcmpl-123",
            "model": "openai/gpt-4",
            "created": 1234567890,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "A" * 200
                    },
                    "finish_reason": "stop"
                }
            ]
        }

        sanitized = SensitiveDataSanitizer.sanitize_response(response, enable_verbose=True)

        assert "first_choice" in sanitized
        assert "content" in sanitized["first_choice"]
        assert "[TRUNCATED:" in sanitized["first_choice"]["content"]
        assert sanitized["first_choice"]["finish_reason"] == "stop"

    def test_sanitize_response_preserves_usage(self):
        """Test that usage statistics are preserved."""
        response = {
            "id": "chatcmpl-123",
            "model": "openai/gpt-4",
            "choices": [],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 100,
                "total_tokens": 150
            }
        }

        sanitized = SensitiveDataSanitizer.sanitize_response(response, enable_verbose=False)

        assert sanitized["usage"]["prompt_tokens"] == 50
        assert sanitized["usage"]["completion_tokens"] == 100
        assert sanitized["usage"]["total_tokens"] == 150


class TestSecurityGuarantees:
    """Integration tests verifying security guarantees."""

    def test_no_api_key_in_sanitized_headers(self):
        """Verify API keys never appear in sanitized headers."""
        secret_key = "sk-or-v1-secret-api-key-do-not-log"
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        }

        sanitized = SensitiveDataSanitizer.sanitize_headers(headers)
        sanitized_str = str(sanitized)

        assert secret_key not in sanitized_str
        assert "secret-api-key-do-not-log" not in sanitized_str

    def test_no_user_prompt_in_sanitized_payload(self):
        """Verify user prompts don't appear in sanitized payloads (non-verbose)."""
        secret_prompt = "My SSN is 123-45-6789 and my password is hunter2"
        payload = {
            "model": "openai/gpt-4",
            "messages": [
                {"role": "user", "content": secret_prompt}
            ]
        }

        sanitized = SensitiveDataSanitizer.sanitize_payload(payload, enable_verbose=False)
        sanitized_str = str(sanitized)

        assert "123-45-6789" not in sanitized_str
        assert "hunter2" not in sanitized_str
        assert secret_prompt not in sanitized_str

    def test_no_ai_response_in_sanitized_response(self):
        """Verify AI responses don't appear in sanitized responses (non-verbose)."""
        secret_response = "The user's credit card number is 4111-1111-1111-1111"
        response = {
            "id": "chatcmpl-123",
            "model": "openai/gpt-4",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": secret_response
                    },
                    "finish_reason": "stop"
                }
            ]
        }

        sanitized = SensitiveDataSanitizer.sanitize_response(response, enable_verbose=False)
        sanitized_str = str(sanitized)

        assert "4111-1111-1111-1111" not in sanitized_str
        assert secret_response not in sanitized_str

    def test_verbose_mode_truncates_pii(self):
        """Verify verbose mode truncates PII but doesn't eliminate all risk."""
        long_secret = "My secret is: " + ("X" * 200)
        payload = {
            "model": "openai/gpt-4",
            "messages": [
                {"role": "user", "content": long_secret}
            ]
        }

        sanitized = SensitiveDataSanitizer.sanitize_payload(payload, enable_verbose=True)
        sanitized_str = str(sanitized)

        # The first 50 chars might be logged, but not the full secret
        assert len(sanitized_str) < len(long_secret)
        assert "[TRUNCATED:" in sanitized_str
