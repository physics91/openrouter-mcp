#!/usr/bin/env python3
"""
Models module for OpenRouter MCP Server.

This module provides:
- Dynamic model caching and management functionality
- Base request models for DRY-compliant handler development
"""

from .cache import ModelCache
from .requests import (
    BaseChatRequest,
    BaseCollectiveRequest,
    BaseCompletionParams,
    BaseConsensusRequest,
    ChatMessage,
    StreamableRequest,
)

__all__ = [
    # Cache
    "ModelCache",
    # Request models
    "ChatMessage",
    "BaseCompletionParams",
    "StreamableRequest",
    "BaseChatRequest",
    "BaseCollectiveRequest",
    "BaseConsensusRequest",
]
