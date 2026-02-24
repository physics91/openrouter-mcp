"""
Centralized configuration constants for OpenRouter MCP.

This module provides a Single Source of Truth (SSOT) for all configuration
values used throughout the codebase. Using these constants instead of
hardcoded values ensures consistency and makes maintenance easier.

Usage:
    from openrouter_mcp.config.constants import APIConfig, CacheConfig, ModelDefaults

    base_url = APIConfig.BASE_URL
    timeout = CacheConfig.DEFAULT_TTL_SECONDS
    temperature = ModelDefaults.TEMPERATURE
"""

from typing import Optional


class APIConfig:
    """API endpoint and connection configuration."""

    BASE_URL: str = "https://openrouter.ai/api/v1"
    DEFAULT_TIMEOUT: float = 30.0
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0


class CacheConfig:
    """Cache configuration for model and response caching."""

    DEFAULT_TTL_SECONDS: int = 3600  # 1 hour
    MIN_TTL_HOURS: float = 0.08334   # 5 minutes minimum
    DEFAULT_TTL_HOURS: float = 1.0
    MODEL_CACHE_FILE: str = ".cache/openrouter_model_cache.json"


class ModelDefaults:
    """Default parameters for model completion requests."""

    TEMPERATURE: float = 0.7
    MAX_TOKENS: Optional[int] = None
    STREAM: bool = False
    TOP_P: float = 1.0
    FREQUENCY_PENALTY: float = 0.0
    PRESENCE_PENALTY: float = 0.0


class EnvVars:
    """Environment variable names for configuration."""

    API_KEY: str = "OPENROUTER_API_KEY"
    BASE_URL: str = "OPENROUTER_BASE_URL"
    APP_NAME: str = "OPENROUTER_APP_NAME"
    HTTP_REFERER: str = "OPENROUTER_HTTP_REFERER"


class ConsensusDefaults:
    """Default configuration for consensus/collective intelligence."""

    MIN_MODELS: int = 3
    MAX_MODELS: int = 5
    CONFIDENCE_THRESHOLD: float = 0.7
    AGREEMENT_THRESHOLD: float = 0.6
    SIMILARITY_THRESHOLD: float = 0.7
    TIMEOUT_SECONDS: float = 60.0


class RateLimitConfig:
    """Rate limiting configuration."""

    MAX_REQUESTS_PER_MINUTE: int = 60
    MAX_TOKENS_PER_MINUTE: int = 100000
    BACKOFF_FACTOR: float = 2.0
    MAX_BACKOFF_SECONDS: float = 60.0


class LoggingConfig:
    """Logging configuration constants."""

    DEFAULT_LEVEL: str = "INFO"
    FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


class PricingDefaults:
    """Default pricing assumptions and heuristics."""

    # Fallback per-token price used when pricing is missing
    DEFAULT_TOKEN_PRICE: float = 0.00002
    # Conservative estimate used for pre-flight quota checks
    ESTIMATED_TOKEN_PRICE: float = 0.00003
    # If a price is >= this value, assume it is per-1K tokens and normalize
    PER_1K_PRICE_THRESHOLD: float = 0.001


class BenchmarkDefaults:
    """Default configuration for benchmarking tools."""

    DEFAULT_PROMPT: str = (
        "\uc548\ub155\ud558\uc138\uc694! \uac04\ub2e8\ud55c "
        "\uc790\uae30\uc18c\uac1c\ub97c \ud574\uc8fc\uc138\uc694."
    )
    DEFAULT_MAX_TOKENS: int = 1000
    DEFAULT_DELAY_SECONDS: float = 1.0
    DEFAULT_RUNS_PER_MODEL: int = 1
    DEFAULT_MCP_RUNS: int = 3
    DEFAULT_RESULTS_DIR: str = ".cache/benchmarks"
    DEFAULT_TIMEOUT_SECONDS: float = 60.0


__all__ = [
    "APIConfig",
    "CacheConfig",
    "ModelDefaults",
    "EnvVars",
    "ConsensusDefaults",
    "RateLimitConfig",
    "LoggingConfig",
    "PricingDefaults",
    "BenchmarkDefaults",
]
