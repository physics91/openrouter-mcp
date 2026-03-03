"""
Token counting utilities for accurate cost estimation.

This module provides token counting functionality using tiktoken,
enabling accurate cost estimation for API requests across different models.
"""

import logging
from typing import Any, Dict, List, Optional

import tiktoken

logger = logging.getLogger(__name__)


# Model family to encoding mapping
# Based on OpenAI's tiktoken documentation
MODEL_ENCODING_MAP = {
    # GPT-4 family
    "gpt-4": "cl100k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4o": "o200k_base",
    "gpt-5": "o200k_base",
    # GPT-3.5 family
    "gpt-3.5": "cl100k_base",
    # Claude family (approximation using cl100k_base)
    "claude": "cl100k_base",
    # Gemini family (approximation)
    "gemini": "cl100k_base",
    # Llama family (approximation)
    "llama": "cl100k_base",
    # Mistral family
    "mistral": "cl100k_base",
    # DeepSeek family
    "deepseek": "cl100k_base",
    # Default
    "default": "cl100k_base",
}


class TokenCounter:
    """
    Token counter for accurate cost estimation.

    Uses tiktoken for accurate token counting across different model families.
    Falls back to conservative character-based estimation when tiktoken fails.
    """

    def __init__(self):
        """Initialize token counter with encoding cache."""
        self._encoding_cache: Dict[str, tiktoken.Encoding] = {}

    def _get_encoding_for_model(self, model_id: str) -> tiktoken.Encoding:
        """
        Get tiktoken encoding for a specific model.

        Args:
            model_id: Full model identifier (e.g., "openai/gpt-4")

        Returns:
            tiktoken.Encoding instance
        """
        # Check cache first
        if model_id in self._encoding_cache:
            return self._encoding_cache[model_id]

        # Determine encoding based on model family
        model_lower = model_id.lower()
        encoding_name = "cl100k_base"  # default

        for family, enc_name in MODEL_ENCODING_MAP.items():
            if family in model_lower:
                encoding_name = enc_name
                break

        try:
            encoding = tiktoken.get_encoding(encoding_name)
            self._encoding_cache[model_id] = encoding
            return encoding
        except Exception as e:
            logger.warning(
                f"Failed to get tiktoken encoding '{encoding_name}' for model {model_id}: {e}. "
                f"Using default cl100k_base encoding."
            )
            # Fallback to default
            encoding = tiktoken.get_encoding("cl100k_base")
            self._encoding_cache[model_id] = encoding
            return encoding

    def count_tokens(self, text: str, model_id: str = "default") -> int:
        """
        Count tokens in text for a specific model.

        Args:
            text: Text to count tokens for
            model_id: Model identifier for encoding selection

        Returns:
            Number of tokens
        """
        if not text:
            return 0

        try:
            encoding = self._get_encoding_for_model(model_id)
            tokens = encoding.encode(text)
            return len(tokens)
        except Exception as e:
            logger.warning(
                f"Failed to count tokens with tiktoken for model {model_id}: {e}. "
                f"Using character-based estimation."
            )
            # Fallback to conservative character-based estimation
            # Average ~4 characters per token for most models
            return max(1, len(text) // 4)

    def count_message_tokens(
        self, messages: List[Dict[str, Any]], model_id: str = "default"
    ) -> int:
        """
        Count tokens in a list of chat messages.

        Accounts for message formatting overhead based on the chat format.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model_id: Model identifier for encoding selection

        Returns:
            Total number of tokens including formatting overhead
        """
        if not messages:
            return 0

        try:
            encoding = self._get_encoding_for_model(model_id)

            # Token counting logic based on OpenAI's cookbook
            # https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb

            tokens_per_message = (
                3  # Every message follows <|start|>{role/name}\n{content}<|end|>\n
            )
            tokens_per_name = 1  # If there's a name, add 1 token

            num_tokens = 0

            for message in messages:
                num_tokens += tokens_per_message

                for key, value in message.items():
                    if isinstance(value, str):
                        num_tokens += len(encoding.encode(value))
                    elif isinstance(value, list):
                        # Handle multimodal content (e.g., vision)
                        for item in value:
                            if isinstance(item, dict) and "text" in item:
                                num_tokens += len(encoding.encode(item["text"]))
                            # Image tokens are handled separately by the API

                    if key == "name":
                        num_tokens += tokens_per_name

            num_tokens += 3  # Every reply is primed with <|start|>assistant<|message|>

            return num_tokens

        except Exception as e:
            logger.warning(
                f"Failed to count message tokens with tiktoken: {e}. "
                f"Using fallback estimation."
            )
            # Fallback: sum character counts and divide by 4
            total_chars = 0
            for message in messages:
                content = message.get("content", "")
                if isinstance(content, str):
                    total_chars += len(content)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            total_chars += len(item["text"])

            return max(1, total_chars // 4)

    def estimate_completion_tokens(
        self,
        prompt_tokens: int,
        max_tokens: Optional[int] = None,
        typical_ratio: float = 0.5,
    ) -> int:
        """
        Estimate completion tokens based on prompt and constraints.

        Args:
            prompt_tokens: Number of tokens in the prompt
            max_tokens: Maximum tokens requested (if specified)
            typical_ratio: Typical completion/prompt ratio (default 0.5)

        Returns:
            Estimated completion tokens
        """
        if max_tokens:
            # Use the smaller of max_tokens or estimated typical length
            estimated = int(prompt_tokens * typical_ratio)
            return min(max_tokens, estimated)
        else:
            # Use typical ratio
            return int(prompt_tokens * typical_ratio)


# Global singleton instance
_token_counter: Optional[TokenCounter] = None


def get_token_counter() -> TokenCounter:
    """
    Get the global TokenCounter instance.

    Returns:
        TokenCounter singleton
    """
    global _token_counter
    if _token_counter is None:
        _token_counter = TokenCounter()
    return _token_counter


def count_tokens(text: str, model_id: str = "default") -> int:
    """
    Convenience function to count tokens in text.

    Args:
        text: Text to count tokens for
        model_id: Model identifier for encoding selection

    Returns:
        Number of tokens
    """
    counter = get_token_counter()
    return counter.count_tokens(text, model_id)


def count_message_tokens(
    messages: List[Dict[str, Any]], model_id: str = "default"
) -> int:
    """
    Convenience function to count tokens in messages.

    Args:
        messages: List of message dictionaries
        model_id: Model identifier for encoding selection

    Returns:
        Total number of tokens
    """
    counter = get_token_counter()
    return counter.count_message_tokens(messages, model_id)
