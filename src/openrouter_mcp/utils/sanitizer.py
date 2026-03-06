"""
Sensitive Data Sanitizer for secure logging.

This module provides utilities to sanitize sensitive data before logging,
preventing security leaks of API keys, authorization tokens, and user content.

Usage:
    from openrouter_mcp.utils.sanitizer import SensitiveDataSanitizer

    # Mask an API key
    masked = SensitiveDataSanitizer.mask_api_key("sk-or-12345...")

    # Sanitize headers
    safe_headers = SensitiveDataSanitizer.sanitize_headers(headers)

    # Sanitize request payload
    safe_payload = SensitiveDataSanitizer.sanitize_payload(payload)
"""

import hashlib
from typing import Any, Dict, List


class SensitiveDataSanitizer:
    """Sanitizes sensitive data from logs to prevent security leaks.

    This class provides methods to mask, truncate, or hash sensitive information
    such as API keys, authorization tokens, and user prompts before logging.
    """

    @staticmethod
    def mask_api_key(api_key: str, visible_chars: int = 4) -> str:
        """Mask API key, showing only first few characters.

        Args:
            api_key: The API key to mask
            visible_chars: Number of characters to show at the start

        Returns:
            Masked API key string
        """
        if not api_key or len(api_key) <= visible_chars:
            return "***MASKED***"
        return f"{api_key[:visible_chars]}...***MASKED***"

    @staticmethod
    def sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize headers by masking sensitive values.

        Args:
            headers: Original headers dictionary

        Returns:
            Sanitized copy of headers with masked sensitive values
        """
        sanitized = headers.copy()
        sensitive_headers = ["authorization", "x-api-key", "api-key"]

        for key in sanitized.keys():
            if key.lower() in sensitive_headers:
                if sanitized[key].lower().startswith("bearer "):
                    api_key = sanitized[key][7:]  # Remove "Bearer " prefix
                    sanitized[key] = f"Bearer {SensitiveDataSanitizer.mask_api_key(api_key)}"
                else:
                    sanitized[key] = SensitiveDataSanitizer.mask_api_key(sanitized[key])

        return sanitized

    @staticmethod
    def hash_content(content: str, algorithm: str = "sha256") -> str:
        """Create a hash of content for safe logging.

        Args:
            content: Content to hash
            algorithm: Hash algorithm to use (sha256, sha1, md5)

        Returns:
            Hexadecimal hash string
        """
        if not content:
            return "EMPTY"

        hasher = hashlib.new(algorithm)
        hasher.update(content.encode("utf-8"))
        return f"{algorithm}:{hasher.hexdigest()[:16]}..."

    @staticmethod
    def truncate_content(content: str, max_length: int = 100) -> str:
        """Truncate content to prevent logging large payloads.

        Args:
            content: Content to truncate
            max_length: Maximum length to preserve

        Returns:
            Truncated content with indicator if truncated
        """
        if not content:
            return "EMPTY"

        if len(content) <= max_length:
            return content

        return f"{content[:max_length]}... [TRUNCATED: {len(content)} chars total]"

    @staticmethod
    def sanitize_messages(
        messages: List[Dict[str, Any]], mode: str = "hash"
    ) -> List[Dict[str, Any]]:
        """Sanitize message content for logging.

        Args:
            messages: List of message dictionaries
            mode: Sanitization mode - 'hash', 'truncate', or 'metadata'

        Returns:
            Sanitized copy of messages
        """
        sanitized = []

        for msg in messages:
            sanitized_msg = {"role": msg.get("role", "unknown")}
            content = msg.get("content", "")

            if mode == "hash":
                if isinstance(content, str):
                    sanitized_msg["content_hash"] = SensitiveDataSanitizer.hash_content(content)
                    sanitized_msg["content_length"] = len(content)
                elif isinstance(content, list):
                    # Multimodal content
                    sanitized_msg["content_type"] = "multimodal"
                    sanitized_msg["content_parts"] = len(content)
            elif mode == "truncate":
                if isinstance(content, str):
                    sanitized_msg["content"] = SensitiveDataSanitizer.truncate_content(content, 50)
                elif isinstance(content, list):
                    sanitized_msg["content_type"] = "multimodal"
                    sanitized_msg["content_parts"] = len(content)
            elif mode == "metadata":
                if isinstance(content, str):
                    sanitized_msg["content_length"] = len(content)
                    sanitized_msg["content_type"] = "text"
                elif isinstance(content, list):
                    sanitized_msg["content_type"] = "multimodal"
                    sanitized_msg["content_parts"] = len(content)

            sanitized.append(sanitized_msg)

        return sanitized

    @staticmethod
    def sanitize_payload(payload: Dict[str, Any], enable_verbose: bool = False) -> Dict[str, Any]:
        """Sanitize request payload for logging.

        Args:
            payload: Original payload dictionary
            enable_verbose: If True, include truncated content; if False, only metadata

        Returns:
            Sanitized copy of payload safe for logging
        """
        sanitized = {
            "model": payload.get("model", "unknown"),
            "temperature": payload.get("temperature"),
            "max_tokens": payload.get("max_tokens"),
            "stream": payload.get("stream", False),
        }

        # Sanitize messages based on verbosity setting
        if "messages" in payload:
            if enable_verbose:
                sanitized["messages"] = SensitiveDataSanitizer.sanitize_messages(
                    payload["messages"], mode="truncate"
                )
            else:
                sanitized["messages"] = SensitiveDataSanitizer.sanitize_messages(
                    payload["messages"], mode="metadata"
                )

        # Include non-sensitive additional parameters
        safe_params = ["top_p", "frequency_penalty", "presence_penalty", "n"]
        for param in safe_params:
            if param in payload:
                sanitized[param] = payload[param]

        return sanitized

    @staticmethod
    def sanitize_response(response: Dict[str, Any], enable_verbose: bool = False) -> Dict[str, Any]:
        """Sanitize API response for logging.

        Args:
            response: Original response dictionary
            enable_verbose: If True, include truncated content; if False, only metadata

        Returns:
            Sanitized copy of response safe for logging
        """
        sanitized = {
            "id": response.get("id", "unknown"),
            "model": response.get("model", "unknown"),
            "created": response.get("created"),
        }

        # Sanitize choices
        if "choices" in response:
            choices = response["choices"]
            sanitized["choices_count"] = len(choices)

            if enable_verbose and choices:
                # Show truncated version of first choice
                first_choice = choices[0]
                message = first_choice.get("message", {})
                content = message.get("content", "")

                sanitized["first_choice"] = {
                    "role": message.get("role", "unknown"),
                    "content": SensitiveDataSanitizer.truncate_content(content, 100),
                    "finish_reason": first_choice.get("finish_reason"),
                }
            else:
                # Only metadata
                if choices:
                    first_choice = choices[0]
                    message = first_choice.get("message", {})
                    content = message.get("content", "")

                    sanitized["first_choice_metadata"] = {
                        "role": message.get("role", "unknown"),
                        "content_length": (len(content) if isinstance(content, str) else 0),
                        "finish_reason": first_choice.get("finish_reason"),
                    }

        # Include usage information (not sensitive)
        if "usage" in response:
            sanitized["usage"] = response["usage"]

        return sanitized


__all__ = ["SensitiveDataSanitizer"]
