"""Environment variable helpers for OpenRouter MCP."""
from __future__ import annotations

import os
from typing import Optional


def get_env_value(name: str, default: Optional[str] = None) -> Optional[str]:
    """Return a stripped env var value or a default when missing/blank."""
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if not value:
        return default
    return value


def get_required_env(name: str, error_message: Optional[str] = None) -> str:
    """Return a required env var value or raise a ValueError."""
    value = get_env_value(name)
    if value is None:
        raise ValueError(error_message or f"{name} environment variable is required")
    return value


__all__ = ["get_env_value", "get_required_env"]
