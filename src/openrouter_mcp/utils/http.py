"""HTTP utilities for OpenRouter MCP."""

from __future__ import annotations

from typing import Dict, Optional

from ..config.constants import EnvVars
from .env import get_env_value


def build_openrouter_headers(
    api_key: str,
    app_name: Optional[str] = None,
    http_referer: Optional[str] = None,
    *,
    fallback_to_env: bool = True,
) -> Dict[str, str]:
    """Build OpenRouter request headers with optional tracking metadata."""
    if fallback_to_env:
        if app_name is None:
            app_name = get_env_value(EnvVars.APP_NAME)
        if http_referer is None:
            http_referer = get_env_value(EnvVars.HTTP_REFERER)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if app_name:
        headers["X-Title"] = app_name
    if http_referer:
        headers["HTTP-Referer"] = http_referer

    return headers


__all__ = ["build_openrouter_headers"]
