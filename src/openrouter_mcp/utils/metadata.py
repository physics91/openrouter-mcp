#!/usr/bin/env python3
"""
Enhanced metadata extraction and enrichment utilities for OpenRouter models.

This module provides comprehensive metadata extraction, categorization,
and enrichment capabilities for AI models from the OpenRouter API.
"""

import logging
import re
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, List, Optional, TypeVar

from .pricing import normalize_pricing, parse_price

logger = logging.getLogger(__name__)

_PatternKey = TypeVar("_PatternKey")


class ModelProvider(str, Enum):
    """Enumeration of model providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    META = "meta"
    MISTRAL = "mistral"
    DEEPSEEK = "deepseek"
    XAI = "xai"
    COHERE = "cohere"
    PERPLEXITY = "perplexity"
    FIREWORKS = "fireworks"
    TOGETHER = "together"
    REPLICATE = "replicate"
    HUGGINGFACE = "huggingface"
    AI21 = "ai21"
    INFLECTION = "inflection"
    NVIDIA = "nvidia"
    UNKNOWN = "unknown"


class ModelCategory(str, Enum):
    """Enumeration of model categories."""

    CHAT = "chat"
    COMPLETION = "completion"
    IMAGE = "image"
    AUDIO = "audio"
    EMBEDDING = "embedding"
    MULTIMODAL = "multimodal"
    REASONING = "reasoning"
    CODE = "code"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    UNKNOWN = "unknown"


_PROVIDER_PREFIX_MAP = MappingProxyType(
    {
        "openai": ModelProvider.OPENAI,
        "anthropic": ModelProvider.ANTHROPIC,
        "google": ModelProvider.GOOGLE,
        "meta-llama": ModelProvider.META,
        "meta": ModelProvider.META,
        "mistralai": ModelProvider.MISTRAL,
        "deepseek": ModelProvider.DEEPSEEK,
        "xai": ModelProvider.XAI,
        "cohere": ModelProvider.COHERE,
        "perplexity": ModelProvider.PERPLEXITY,
        "fireworks": ModelProvider.FIREWORKS,
        "togethercomputer": ModelProvider.TOGETHER,
        "together": ModelProvider.TOGETHER,
        "huggingface": ModelProvider.HUGGINGFACE,
        "ai21": ModelProvider.AI21,
        "inflection": ModelProvider.INFLECTION,
        "nvidia": ModelProvider.NVIDIA,
    }
)
_LATEST_MODEL_MARKERS = (
    "gpt-4-turbo",
    "gpt-4o",
    "o1-preview",
    "o1-mini",
    "claude-3-opus",
    "claude-3-sonnet",
    "claude-3-haiku",
    "gemini-2",
    "gemini-pro",
    "gemini-ultra",
    "llama-3",
    "mistral-large",
    "deepseek-v3",
)


class ModelCapabilities:
    """Model capability flags and limits."""

    def __init__(
        self,
        supports_vision: bool = False,
        supports_function_calling: bool = False,
        supports_streaming: bool = True,
        supports_system_prompt: bool = True,
        supports_json_mode: bool = False,
        supports_tool_use: bool = False,
        max_tokens: int = 0,
        max_output_tokens: int = 0,
        supports_multiple_images: bool = False,
        supports_pdf: bool = False,
    ):
        self.supports_vision = supports_vision
        self.supports_function_calling = supports_function_calling
        self.supports_streaming = supports_streaming
        self.supports_system_prompt = supports_system_prompt
        self.supports_json_mode = supports_json_mode
        self.supports_tool_use = supports_tool_use
        self.max_tokens = max_tokens
        self.max_output_tokens = max_output_tokens
        self.supports_multiple_images = supports_multiple_images
        self.supports_pdf = supports_pdf

    def to_dict(self) -> Dict[str, Any]:
        """Convert capabilities to dictionary."""
        return {
            "supports_vision": self.supports_vision,
            "supports_function_calling": self.supports_function_calling,
            "supports_streaming": self.supports_streaming,
            "supports_system_prompt": self.supports_system_prompt,
            "supports_json_mode": self.supports_json_mode,
            "supports_tool_use": self.supports_tool_use,
            "max_tokens": self.max_tokens,
            "max_output_tokens": self.max_output_tokens,
            "supports_multiple_images": self.supports_multiple_images,
            "supports_pdf": self.supports_pdf,
        }


# Provider patterns for ID matching
PROVIDER_PATTERNS = {
    ModelProvider.OPENAI: [r"^openai/", r"^gpt-", r"^o1-"],
    ModelProvider.ANTHROPIC: [r"^anthropic/", r"^claude-"],
    ModelProvider.GOOGLE: [r"^google/", r"^gemini", r"^palm"],
    ModelProvider.META: [r"^meta-llama/", r"^meta/", r"llama-\d"],
    ModelProvider.MISTRAL: [r"^mistralai/", r"^mistral"],
    ModelProvider.DEEPSEEK: [r"^deepseek/"],
    ModelProvider.XAI: [r"^xai/", r"^grok"],
    ModelProvider.COHERE: [r"^cohere/", r"^command"],
    ModelProvider.PERPLEXITY: [r"^perplexity/", r"^pplx"],
    ModelProvider.FIREWORKS: [r"^fireworks/"],
    ModelProvider.TOGETHER: [r"^togethercomputer/"],
    ModelProvider.HUGGINGFACE: [r"^huggingface/"],
    ModelProvider.AI21: [r"^ai21/"],
    ModelProvider.INFLECTION: [r"^inflection/"],
    ModelProvider.NVIDIA: [r"^nvidia/"],
}

# Category patterns for model identification
CATEGORY_PATTERNS = {
    ModelCategory.IMAGE: [
        r"dall-?e",
        r"stable-diffusion",
        r"midjourney",
        r"imagen",
        r"text-to-image",
        r"text->image",
        r"image",
    ],
    ModelCategory.AUDIO: [
        r"whisper",
        r"speech",
        r"audio",
        r"voice",
        r"tts",
        r"audio->text",
        r"text->audio",
    ],
    ModelCategory.EMBEDDING: [r"embed", r"ada", r"text-embedding", r"vector"],
    ModelCategory.REASONING: [
        r"o1",
        r"reasoning",
        r"think",
        r"chain-of-thought",
        r"cot",
    ],
    ModelCategory.CODE: [
        r"code",
        r"codex",
        r"copilot",
        r"starcoder",
        r"codellama",
        r"deepseek-coder",
        r"wizard-?coder",
    ],
    ModelCategory.MULTIMODAL: [
        r"vision",
        r"multimodal",
        r"image\+text",
        r"text\+image",
        r"gpt-4v",
        r"gemini.*vision",
        r"claude.*vision",
    ],
}


def _find_first_pattern_match(
    text: str,
    pattern_map: Dict[_PatternKey, List[str]],
) -> Optional[_PatternKey]:
    """Return the first mapping key with a regex matching the supplied text."""
    for key, patterns in pattern_map.items():
        for pattern in patterns:
            if re.search(pattern, text):
                return key
    return None


def _coerce_non_negative_int(value: Any, default: int = 0) -> int:
    """Coerce nullable numeric values from API payloads into safe integers."""
    try:
        if value is None:
            return default
        return max(default, int(float(value)))
    except (TypeError, ValueError):
        return default


def extract_provider_from_id(model_id: str) -> ModelProvider:
    """
    Extract provider from model ID using pattern matching.

    Args:
        model_id: Model identifier string

    Returns:
        ModelProvider enum value
    """
    if not model_id:
        return ModelProvider.UNKNOWN

    model_id_lower = model_id.lower()

    # Direct provider prefix check
    if "/" in model_id:
        provider_prefix = model_id.split("/")[0].lower()

        if provider_prefix in _PROVIDER_PREFIX_MAP:
            return _PROVIDER_PREFIX_MAP[provider_prefix]

    # Pattern-based matching
    provider = _find_first_pattern_match(model_id_lower, PROVIDER_PATTERNS)
    if provider is not None:
        return provider

    return ModelProvider.UNKNOWN


def determine_model_category(model_data: Dict[str, Any]) -> ModelCategory:
    """
    Determine model category from model data.

    Args:
        model_data: Model information dictionary

    Returns:
        ModelCategory enum value
    """
    model_id = model_data.get("id", "").lower()
    model_name = model_data.get("name", "").lower()

    # Check architecture modality
    architecture = model_data.get("architecture") or {}
    modality = architecture.get("modality", "").lower()

    # Modality-based categorization
    if "image" in modality:
        if "text->image" in modality:
            return ModelCategory.IMAGE
        if "text+image" in modality or "image->text" in modality:
            return ModelCategory.MULTIMODAL

    if "audio" in modality:
        return ModelCategory.AUDIO

    # Pattern-based categorization
    combined_text = f"{model_id} {model_name} {modality}"

    category = _find_first_pattern_match(combined_text, CATEGORY_PATTERNS)
    if category is not None:
        return category

    # Check for embeddings
    if "embedding" in model_id or "embed" in model_id:
        return ModelCategory.EMBEDDING

    # Default to chat for text models
    if "text" in modality or not modality:
        return ModelCategory.CHAT

    return ModelCategory.UNKNOWN


def _extract_function_and_tool_support(
    provider: ModelProvider,
    model_id: str,
) -> tuple[bool, bool]:
    supports_functions = False
    supports_tools = False

    if provider == ModelProvider.OPENAI and (
        "gpt-4" in model_id or "gpt-3.5-turbo" in model_id
    ):
        # Most modern OpenAI models support functions
        supports_functions = True
        supports_tools = True
    elif provider == ModelProvider.ANTHROPIC:
        # Claude 3 models support tool use
        if "claude-3" in model_id:
            supports_tools = True
    elif provider == ModelProvider.GOOGLE:
        # Gemini models support functions
        if "gemini" in model_id:
            supports_functions = True

    return supports_functions, supports_tools


def _extract_model_token_limits(model_data: Dict[str, Any]) -> tuple[int, int]:
    """Extract non-negative context and completion token limits."""
    top_provider = model_data.get("top_provider") or {}
    max_tokens = _coerce_non_negative_int(model_data.get("context_length"), default=0)
    raw_max_output = top_provider.get("max_completion_tokens")
    max_output_default = 4096 if "max_completion_tokens" not in top_provider else 0
    max_output = _coerce_non_negative_int(raw_max_output, default=max_output_default)
    return max_tokens, max_output


def extract_model_capabilities(model_data: Dict[str, Any]) -> ModelCapabilities:
    """
    Extract detailed capabilities from model data.

    Args:
        model_data: Model information dictionary

    Returns:
        ModelCapabilities object
    """
    model_id = model_data.get("id", "").lower()
    architecture = model_data.get("architecture") or {}
    modality = architecture.get("modality", "").lower()

    # Vision capability
    supports_vision = (
        "image" in modality
        or "vision" in model_id
        or "multimodal" in modality
        or model_data.get("supports_vision", False)
    )

    # Function calling capability
    provider = extract_provider_from_id(model_data.get("id", ""))
    supports_functions, supports_tools = _extract_function_and_tool_support(
        provider,
        model_id,
    )

    # JSON mode support
    supports_json = (
        provider in [ModelProvider.OPENAI, ModelProvider.ANTHROPIC]
        or "json" in model_data.get("description", "").lower()
    )

    # Token limits
    max_tokens, max_output = _extract_model_token_limits(model_data)

    # Multiple images support (for vision models)
    supports_multiple_images = supports_vision and provider in [
        ModelProvider.OPENAI,
        ModelProvider.GOOGLE,
        ModelProvider.ANTHROPIC,
    ]

    # PDF support (some multimodal models)
    supports_pdf = supports_vision and provider in [
        ModelProvider.ANTHROPIC,
        ModelProvider.GOOGLE,
    ]

    return ModelCapabilities(
        supports_vision=supports_vision,
        supports_function_calling=supports_functions,
        supports_streaming=True,  # Most models support streaming
        supports_system_prompt=True,  # Most chat models support this
        supports_json_mode=supports_json,
        supports_tool_use=supports_tools,
        max_tokens=max_tokens,
        max_output_tokens=max_output,
        supports_multiple_images=supports_multiple_images,
        supports_pdf=supports_pdf,
    )


def _extract_version_parts(model_id: str) -> List[str]:
    """Extract ordered version fragments from a model identifier."""
    version_parts = []

    stage_match = re.search(
        r"(turbo|preview|beta|alpha|stable)", model_id, re.IGNORECASE
    )
    if stage_match:
        version_parts.append(stage_match.group(1).lower())

    claude_match = re.search(r"(opus|sonnet|haiku)", model_id, re.IGNORECASE)
    if claude_match:
        version_parts.append(claude_match.group(1).lower())

    date_match = re.search(r"(\d{4}-\d{2}-\d{2})|(\d{8})", model_id)
    if date_match:
        date_str = date_match.group(1) or date_match.group(2)
        if len(date_str) == 8:
            date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        version_parts.append(date_str)

    version_match = re.search(r"v(\d+(?:\.\d+)*)", model_id, re.IGNORECASE)
    if version_match:
        version_parts.append(f"v{version_match.group(1)}")

    context_match = re.search(r"(\d+k)", model_id, re.IGNORECASE)
    if context_match:
        version_parts.append(context_match.group(1))

    return version_parts


def _extract_model_family(model_id: str) -> str:
    """Extract the first matching known model family."""
    family_patterns = {
        "gpt-4": r"gpt-?4",
        "gpt-3.5": r"gpt-?3\.5",
        "claude-3": r"claude-?3",
        "claude-2": r"claude-?2",
        "gemini": r"gemini",
        "llama-3": r"llama-?3",
        "llama-2": r"llama-?2",
        "mistral": r"mistral",
        "deepseek": r"deepseek",
        "o1": r"o1",
    }

    for family_name, pattern in family_patterns.items():
        if re.search(pattern, model_id, re.IGNORECASE):
            return family_name

    return "unknown"


def _extract_release_date(model_id: str, created_timestamp: Any) -> Optional[str]:
    """Extract a release date, preferring a date embedded in the model ID."""
    release_date = None
    if created_timestamp:
        try:
            release_date = datetime.fromtimestamp(created_timestamp).strftime(
                "%Y-%m-%d"
            )
        except (ValueError, OSError, OverflowError):
            pass

    date_match = re.search(r"(\d{4})-?(\d{2})-?(\d{2})", model_id)
    if date_match:
        release_date = (
            f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        )

    return release_date


def _is_latest_model(model_id: str) -> bool:
    """Return whether a model ID matches a known latest-model heuristic."""
    if type(model_id) is str:
        model_id_lower = model_id.lower()
        return any(latest in model_id_lower for latest in _LATEST_MODEL_MARKERS)

    return any(latest in model_id.lower() for latest in _LATEST_MODEL_MARKERS)


def get_model_version_info(model_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract version information from model data.

    Args:
        model_data: Model information dictionary

    Returns:
        Dictionary with version information
    """
    model_id = model_data.get("id", "")
    model_data.get("name", "")
    created_timestamp = model_data.get("created", 0)

    version_parts = _extract_version_parts(model_id)
    version = "-".join(version_parts) if version_parts else "unknown"
    family = _extract_model_family(model_id)
    release_date = _extract_release_date(model_id, created_timestamp)
    is_latest = _is_latest_model(model_id)

    return {
        "version": version,
        "release_date": release_date,
        "is_latest": is_latest,
        "family": family,
        "full_version": f"{family}-{version}" if family != "unknown" else version,
    }


def _pricing_per_1k(model_data: Dict[str, Any]) -> Dict[str, float]:
    """Normalize prompt/completion pricing into per-1k token units for tiering."""
    normalized = normalize_pricing(
        model_data.get("pricing") or {},
        default_price=0.0,
        normalize_units=True,
        fill_missing=False,
    )
    return {
        "prompt": normalized["prompt"] * 1000.0,
        "completion": normalized["completion"] * 1000.0,
    }


def _context_quality_bonus(context_length: int) -> float:
    """Return the quality bonus for a context-window size."""
    if context_length >= 200000:
        return 2.0
    if context_length >= 100000:
        return 1.5
    if context_length >= 32000:
        return 1.0
    if context_length >= 8000:
        return 0.5
    return 0.0


def _output_quality_bonus(max_output: int) -> float:
    """Return the quality bonus for a maximum output size."""
    if max_output >= 8192:
        return 1.0
    if max_output >= 4096:
        return 0.5
    return 0.0


def _pricing_quality_adjustment(prompt_price: float) -> float:
    """Return the quality adjustment for per-1k prompt pricing."""
    if prompt_price > 0.01:
        return 1.5
    if prompt_price > 0.001:
        return 0.5
    if prompt_price == 0:
        return -1.0
    return 0.0


def calculate_quality_score(model_data: Dict[str, Any]) -> float:
    """
    Calculate a quality score for the model based on various factors.

    Args:
        model_data: Model information dictionary

    Returns:
        Quality score from 0 to 10. Pricing thresholds assume per-1k tokens.
    """
    score = 5.0  # Base score

    # Context length factor
    context_length = _coerce_non_negative_int(
        model_data.get("context_length"), default=0
    )
    score += _context_quality_bonus(context_length)

    # Output length factor
    top_provider = model_data.get("top_provider") or {}
    max_output = _coerce_non_negative_int(
        top_provider.get("max_completion_tokens"), default=0
    )
    score += _output_quality_bonus(max_output)

    # Pricing factor (premium models usually better)
    prompt_price = _pricing_per_1k(model_data)["prompt"]
    score += _pricing_quality_adjustment(prompt_price)

    # Provider reputation
    provider = extract_provider_from_id(model_data.get("id", ""))
    top_providers = [
        ModelProvider.OPENAI,
        ModelProvider.ANTHROPIC,
        ModelProvider.GOOGLE,
    ]
    if provider in top_providers:
        score += 0.5

    # Multimodal bonus
    architecture = model_data.get("architecture") or {}
    modality = architecture.get("modality", "")
    if "image" in modality or "audio" in modality:
        score += 0.5

    # Clamp score between 0 and 10
    return max(0.0, min(10.0, score))


def determine_performance_tier(model_data: Dict[str, Any]) -> str:
    """
    Determine performance tier based on model characteristics.

    Args:
        model_data: Model information dictionary

    Returns:
        Performance tier string: "premium", "standard", or "economy". Pricing
        thresholds assume per-1k tokens.
    """
    quality_score = calculate_quality_score(model_data)
    prompt_price = _pricing_per_1k(model_data)["prompt"]

    if quality_score >= 7.5 or prompt_price > 0.01:
        return "premium"
    if quality_score >= 5.0 or prompt_price > 0.001:
        return "standard"
    return "economy"


_ALL_PRICING_FIELDS = (
    "prompt",
    "completion",
    "request",
    "image",
    "web_search",
    "internal_reasoning",
)


def _has_any_cost(model_data: Dict[str, Any]) -> bool:
    """Check if model has any non-zero cost across all pricing fields."""
    pricing = model_data.get("pricing") or {}
    return any(parse_price(pricing.get(field)) > 0 for field in _ALL_PRICING_FIELDS)


def determine_cost_tier(model_data: Dict[str, Any]) -> str:
    """
    Determine cost tier based on pricing.

    Args:
        model_data: Model information dictionary

    Returns:
        Cost tier string: "free", "low", "medium", or "high". Pricing thresholds
        assume per-1k tokens.
    """
    if not _has_any_cost(model_data):
        return "free"

    # NOTE: tiering below uses only prompt+completion. Non-token costs
    # (image, request, web_search) affect the free/non-free boundary above
    # but not the low/medium/high bucketing — acceptable per plan Step 2 scope.
    pricing = _pricing_per_1k(model_data)
    prompt_price = pricing["prompt"]
    completion_price = pricing["completion"]

    total_price = prompt_price + completion_price

    if total_price < 0.002:
        return "low"
    if total_price < 0.02:
        return "medium"
    return "high"


def _build_model_tags(
    enhanced: Dict[str, Any], capabilities: ModelCapabilities
) -> List[str]:
    """Build deduplicated search tags for enhanced model metadata."""
    tags = set()
    tags.add(enhanced["provider"])
    tags.add(enhanced["category"])

    if capabilities.supports_vision:
        tags.add("vision")
    if capabilities.supports_function_calling:
        tags.add("functions")
    if capabilities.supports_tool_use:
        tags.add("tools")
    if capabilities.max_tokens > 100000:
        tags.add("long-context")

    tags.add(enhanced["performance_tier"])
    tags.add(enhanced["cost_tier"])

    if enhanced["version_info"]["is_latest"]:
        tags.add("latest")

    return list(tags)


def enhance_model_metadata(model_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance model data with comprehensive metadata.

    Args:
        model_data: Raw model data from API

    Returns:
        Enhanced model data with additional metadata
    """
    # Create a copy to avoid modifying original
    enhanced = model_data.copy()

    # Add provider information (store as string value, not enum)
    provider = extract_provider_from_id(model_data.get("id", ""))
    enhanced["provider"] = (
        provider.value if hasattr(provider, "value") else str(provider)
    )

    # Add category (store as string value, not enum)
    category = determine_model_category(model_data)
    enhanced["category"] = (
        category.value if hasattr(category, "value") else str(category)
    )

    # Add capabilities
    capabilities = extract_model_capabilities(model_data)
    enhanced["capabilities"] = capabilities.to_dict()

    # Add version information
    enhanced["version_info"] = get_model_version_info(model_data)

    # Add performance tier
    enhanced["performance_tier"] = determine_performance_tier(model_data)

    # Add cost tier
    enhanced["cost_tier"] = determine_cost_tier(model_data)

    # Add quality score
    enhanced["quality_score"] = calculate_quality_score(model_data)

    # Add search tags for easier filtering
    enhanced["tags"] = _build_model_tags(enhanced, capabilities)

    return enhanced


def batch_enhance_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enhance a batch of models with metadata.

    Args:
        models: List of raw model data

    Returns:
        List of enhanced model data
    """
    enhanced_models = []

    for model in models:
        try:
            enhanced = enhance_model_metadata(model)
            enhanced_models.append(enhanced)
        except Exception as e:
            logger.warning(f"Failed to enhance model {model.get('id', 'unknown')}: {e}")
            # Add model as-is with minimal metadata
            model["provider"] = ModelProvider.UNKNOWN
            model["category"] = ModelCategory.UNKNOWN
            enhanced_models.append(model)

    return enhanced_models
