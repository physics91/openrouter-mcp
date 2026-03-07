#!/usr/bin/env python3
"""
Provider configuration management for OpenRouter MCP Server.

This module handles loading and managing provider configurations,
including aliases, capabilities, and quality tiers.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Cache for loaded configuration
_config_cache: Optional[Dict[str, Any]] = None


class ProviderConfigError(RuntimeError):
    """Provider 설정 로드 실패."""


def _as_str_dict(value: Any) -> Dict[str, Any]:
    """JSON 객체를 string-key dict로 정규화."""
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _build_default_config() -> Dict[str, Any]:
    """새 기본 설정 사본 생성."""
    return {
        "providers": {},
        "aliases": {},
        "quality_tiers": {},
    }


def load_provider_config() -> Dict[str, Any]:
    """
    Load provider configuration from JSON file.

    Returns:
        Dictionary containing provider configuration
    """
    global _config_cache

    if _config_cache is not None:
        return _config_cache

    config_path = Path(__file__).parent / "providers.json"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
            logger.info(f"Loaded provider configuration from {config_path}")
            return _config_cache
    except FileNotFoundError:
        logger.warning(f"Provider config file not found: {config_path}")
        _config_cache = _build_default_config()
        return _config_cache
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse provider config: {e}")
        raise ProviderConfigError(f"Provider config is invalid JSON: {config_path}") from e
    except Exception as e:
        logger.error(f"Error loading provider config: {e}")
        raise ProviderConfigError(f"Provider config load failed: {config_path}") from e


def resolve_provider_alias(provider_name: str) -> str:
    """
    Resolve provider alias to canonical name.

    Args:
        provider_name: Provider name or alias

    Returns:
        Canonical provider name
    """
    if not provider_name:
        return "unknown"

    provider_lower = provider_name.lower()
    config = load_provider_config()
    aliases = _as_str_dict(config.get("aliases", {}))

    # Check if it's an alias
    if provider_lower in aliases:
        canonical = aliases.get(provider_lower)
        if isinstance(canonical, str):
            return canonical

    # Check if it's already a canonical name
    providers = _as_str_dict(config.get("providers", {}))
    if provider_lower in providers:
        return provider_lower

    # Check for partial matches
    for alias, canonical in aliases.items():
        if isinstance(canonical, str) and (alias in provider_lower or provider_lower in alias):
            return canonical

    return provider_lower


def get_provider_info(provider_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a provider.

    Args:
        provider_name: Provider name or alias

    Returns:
        Provider information dictionary
    """
    canonical_name = resolve_provider_alias(provider_name)
    config = load_provider_config()
    providers = _as_str_dict(config.get("providers", {}))

    provider_info = providers.get(canonical_name)
    if isinstance(provider_info, dict):
        return provider_info

    # Return default info for unknown providers
    return {
        "display_name": provider_name.title(),
        "website": "",
        "description": f"AI model provider: {provider_name}",
        "default_capabilities": {
            "supports_streaming": True,
            "supports_system_prompt": True,
        },
        "model_families": [],
    }


def get_quality_tier_info(tier_name: str) -> Dict[str, Any]:
    """
    Get information about a quality tier.

    Args:
        tier_name: Quality tier name

    Returns:
        Quality tier information dictionary
    """
    config = load_provider_config()
    quality_tiers = _as_str_dict(config.get("quality_tiers", {}))

    tier_info = quality_tiers.get(tier_name)
    if isinstance(tier_info, dict):
        return tier_info

    # Return default info for unknown tiers
    return {
        "description": f"Quality tier: {tier_name}",
        "typical_cost": "Variable",
        "examples": [],
    }
