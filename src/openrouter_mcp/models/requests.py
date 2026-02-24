"""
Base request models for OpenRouter MCP handlers.

This module provides DRY-compliant base classes for all request types,
eliminating field duplication across handlers.

Usage:
    from openrouter_mcp.models.requests import (
        BaseCompletionParams,
        StreamableRequest,
        BaseChatRequest,
        BaseCollectiveRequest,
        ChatMessage,
    )

    class MyRequest(StreamableRequest):
        custom_field: str = Field(...)
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ..config.constants import ModelDefaults, ConsensusDefaults


class ChatMessage(BaseModel):
    """A chat message for completion requests."""
    role: str = Field(..., description="The role of the message sender (system, user, assistant)")
    content: str = Field(..., description="The content of the message")


class BaseCompletionParams(BaseModel):
    """
    Common parameters for all completion requests.

    This base class provides shared fields for temperature and max_tokens,
    ensuring consistent defaults and descriptions across all handlers.
    """
    temperature: float = Field(
        ModelDefaults.TEMPERATURE,
        description="Sampling temperature (0.0 to 2.0)"
    )
    max_tokens: Optional[int] = Field(
        ModelDefaults.MAX_TOKENS,
        description="Maximum number of tokens to generate"
    )


class StreamableRequest(BaseCompletionParams):
    """
    Base for requests that support streaming responses.

    Extends BaseCompletionParams with a stream field.
    """
    stream: bool = Field(
        ModelDefaults.STREAM,
        description="Whether to stream the response"
    )


class BaseChatRequest(StreamableRequest):
    """
    Base class for chat completion requests.

    Provides standard fields for model and messages, plus all streaming
    and completion parameters.
    """
    model: str = Field(..., description="The model to use for completion")
    messages: List[ChatMessage] = Field(..., description="List of messages in the conversation")


class BaseCollectiveRequest(BaseCompletionParams):
    """
    Base class for collective intelligence requests.

    Provides common fields for multi-model operations, including model
    selection and system prompts.
    """
    models: Optional[List[str]] = Field(
        None,
        description="Specific models to use (optional)"
    )
    system_prompt: Optional[str] = Field(
        None,
        description="System prompt for all models"
    )


class BaseConsensusRequest(BaseCollectiveRequest):
    """
    Base class for consensus-based requests.

    Extends BaseCollectiveRequest with consensus-specific parameters.
    """
    min_models: int = Field(
        ConsensusDefaults.MIN_MODELS,
        description="Minimum number of models to use"
    )
    max_models: int = Field(
        ConsensusDefaults.MAX_MODELS,
        description="Maximum number of models to use"
    )
    confidence_threshold: float = Field(
        ConsensusDefaults.CONFIDENCE_THRESHOLD,
        description="Confidence threshold for consensus"
    )


__all__ = [
    "ChatMessage",
    "BaseCompletionParams",
    "StreamableRequest",
    "BaseChatRequest",
    "BaseCollectiveRequest",
    "BaseConsensusRequest",
]
