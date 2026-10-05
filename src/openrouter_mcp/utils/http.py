"""HTTP utilities for OpenRouter MCP."""

from __future__ import annotations

import ipaddress
from typing import Optional

import httpx

from ..config.constants import EnvVars
from .env import get_env_value


def validate_api_base_url(base_url: str) -> str:
    """Require encrypted remote requests; allow HTTP only for local development."""
    try:
        url = httpx.URL(base_url)
    except httpx.InvalidURL:
        raise ValueError("Invalid API base URL") from None
    if not url.is_absolute_url or url.userinfo or url.query or url.fragment:
        raise ValueError(
            "API base URL must be absolute and contain no credentials, query, or fragment"
        )
    local = url.host == "localhost"
    try:
        local = local or ipaddress.ip_address(url.host).is_loopback
    except ValueError:
        pass
    if url.scheme != "https" and not (url.scheme == "http" and local):
        raise ValueError(
            "API base URL must use HTTPS; HTTP is allowed only for loopback hosts"
        )
    return str(url).rstrip("/")


def build_openrouter_headers(
    api_key: str,
    app_name: Optional[str] = None,
    http_referer: Optional[str] = None,
    *,
    fallback_to_env: bool = True,
) -> dict[str, str]:
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


__all__ = ["build_openrouter_headers", "validate_api_base_url"]
