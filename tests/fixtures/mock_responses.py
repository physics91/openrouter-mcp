"""
Mock response factories for DRY-compliant test setup.

This module provides factory functions and classes for creating
consistent mock API responses across all test modules.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import Mock

import httpx


def create_mock_response(
    status_code: int = 200,
    json_data: Optional[Dict[str, Any]] = None,
    text_data: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Mock:
    """
    Create a mock HTTP response.

    Args:
        status_code: HTTP status code
        json_data: JSON response body
        text_data: Text response body
        headers: Response headers

    Returns:
        Mock Response object
    """
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = headers or {"content-type": "application/json"}

    if json_data is not None:
        response.json.return_value = json_data

    if text_data is not None:
        response.text = text_data

    response.raise_for_status = Mock()
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "HTTP Error", request=Mock(), response=response
        )

    return response


class ResponseFactory:
    """
    Factory class for creating consistent mock API responses.

    Provides pre-configured response templates for common test scenarios,
    eliminating duplicate response setup across test files.
    """

    @staticmethod
    def models_list(models: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Create a mock models list response.

        Args:
            models: Optional list of model data, uses defaults if not provided

        Returns:
            Models list response dictionary
        """
        if models is None:
            models = [
                {
                    "id": "openai/gpt-4",
                    "name": "GPT-4",
                    "description": "OpenAI's GPT-4 model",
                    "pricing": {"prompt": "0.00003", "completion": "0.00006"},
                    "context_length": 8192,
                    "architecture": {
                        "modality": "text",
                        "tokenizer": "cl100k_base",
                        "instruct_type": None,
                    },
                    "top_provider": {
                        "context_length": 8192,
                        "max_completion_tokens": 4096,
                        "is_moderated": True,
                    },
                    "per_request_limits": None,
                },
                {
                    "id": "anthropic/claude-3-haiku",
                    "name": "Claude 3 Haiku",
                    "description": "Anthropic's fastest model",
                    "pricing": {"prompt": "0.00025", "completion": "0.00125"},
                    "context_length": 200000,
                    "architecture": {
                        "modality": "text",
                        "tokenizer": "claude",
                        "instruct_type": None,
                    },
                    "top_provider": {
                        "context_length": 200000,
                        "max_completion_tokens": 4096,
                        "is_moderated": False,
                    },
                    "per_request_limits": None,
                },
            ]
        return {"data": models}

    @staticmethod
    def chat_completion(
        content: str = "Hello! How can I help you today?",
        model: str = "openai/gpt-4",
        finish_reason: str = "stop",
        prompt_tokens: int = 10,
        completion_tokens: int = 8,
    ) -> Dict[str, Any]:
        """
        Create a mock chat completion response.

        Args:
            content: Response content
            model: Model ID
            finish_reason: Finish reason
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Chat completion response dictionary
        """
        return {
            "id": "gen-1234567890",
            "provider": "OpenAI",
            "model": model,
            "object": "chat.completion",
            "created": 1692901234,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "logprobs": None,
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    @staticmethod
    def streaming_chunks(
        content_parts: Optional[List[str]] = None,
        model: str = "openai/gpt-4",
        prompt_tokens: int = 10,
        completion_tokens: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        Create mock streaming response chunks.

        Args:
            content_parts: List of content strings to stream
            model: Model ID
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            List of streaming chunk dictionaries
        """
        if content_parts is None:
            content_parts = ["Hello", "! How can I help you today?"]

        chunks = []

        # First chunk with role
        chunks.append(
            {
                "id": "gen-1234567890",
                "provider": "OpenAI",
                "model": model,
                "object": "chat.completion.chunk",
                "created": 1692901234,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": content_parts[0]},
                        "logprobs": None,
                        "finish_reason": None,
                    }
                ],
            }
        )

        # Middle chunks with content only
        for content_part in content_parts[1:]:
            chunks.append(
                {
                    "id": "gen-1234567890",
                    "provider": "OpenAI",
                    "model": model,
                    "object": "chat.completion.chunk",
                    "created": 1692901234,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": content_part},
                            "logprobs": None,
                            "finish_reason": None,
                        }
                    ],
                }
            )

        # Final chunk with finish_reason and usage
        chunks.append(
            {
                "id": "gen-1234567890",
                "provider": "OpenAI",
                "model": model,
                "object": "chat.completion.chunk",
                "created": 1692901234,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "logprobs": None,
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            }
        )

        return chunks

    @staticmethod
    def error_response(
        error_type: str = "invalid_request_error",
        error_code: str = "invalid_api_key",
        message: str = "Invalid API key provided",
    ) -> Dict[str, Any]:
        """
        Create a mock error response.

        Args:
            error_type: Error type
            error_code: Error code
            message: Error message

        Returns:
            Error response dictionary
        """
        return {
            "error": {
                "type": error_type,
                "code": error_code,
                "message": message,
            }
        }

    @staticmethod
    def rate_limit_error() -> Dict[str, Any]:
        """Create a mock rate limit error response."""
        return ResponseFactory.error_response(
            error_type="rate_limit_error",
            error_code="rate_limit_exceeded",
            message="Rate limit exceeded. Please try again later.",
        )

    @staticmethod
    def timeout_error() -> Dict[str, Any]:
        """Create a mock timeout error response."""
        return ResponseFactory.error_response(
            error_type="timeout_error",
            error_code="request_timeout",
            message="Request timed out. Please try again.",
        )


__all__ = ["create_mock_response", "ResponseFactory"]
