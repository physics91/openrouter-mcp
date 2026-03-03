"""Configuration modules for OpenRouter MCP Server."""

from .constants import (
    APIConfig,
    CacheConfig,
    ConsensusDefaults,
    EnvVars,
    LoggingConfig,
    ModelDefaults,
    RateLimitConfig,
)
from .constants import __all__ as _ALL_CONSTANT_EXPORTS
from .providers import (
    get_provider_info,
    get_quality_tier_info,
    load_provider_config,
    resolve_provider_alias,
)

_CONSTANT_EXPORT_MAP = {
    "APIConfig": APIConfig,
    "CacheConfig": CacheConfig,
    "ModelDefaults": ModelDefaults,
    "EnvVars": EnvVars,
    "ConsensusDefaults": ConsensusDefaults,
    "RateLimitConfig": RateLimitConfig,
    "LoggingConfig": LoggingConfig,
}
_CONSTANT_EXPORTS = [
    name for name in _ALL_CONSTANT_EXPORTS if name in _CONSTANT_EXPORT_MAP
]

__all__ = [
    "load_provider_config",
    "resolve_provider_alias",
    "get_provider_info",
    "get_quality_tier_info",
    *_CONSTANT_EXPORTS,
]
