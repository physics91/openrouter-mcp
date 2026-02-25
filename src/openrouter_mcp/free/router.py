"""Free model router with quality-weighted selection and smart rotation."""

import logging
import time
from typing import Dict, List, Optional

from ..config.constants import FreeChatConfig
from ..models.cache import ModelCache
from ..utils.metadata import extract_provider_from_id

logger = logging.getLogger(__name__)

_MAX_CONTEXT_LENGTH = 262144


class FreeModelRouter:
    """Selects the best available free model using quality scoring and rotation."""

    def __init__(self, model_cache: ModelCache) -> None:
        self._cache = model_cache
        self._cooldowns: Dict[str, float] = {}
        self._usage_counts: Dict[str, int] = {}

    def _score_model(self, model: dict) -> float:
        """Score a model from 0.0 to 1.0 based on quality heuristics."""
        context_length = model.get("context_length", 0)
        context_score = min(context_length / _MAX_CONTEXT_LENGTH, 1.0)

        provider = model.get("provider", "")
        if not provider or provider == "unknown":
            provider = extract_provider_from_id(model.get("id", "")).value
        reputation = FreeChatConfig.MODEL_REPUTATION.get(
            provider.lower(), FreeChatConfig.DEFAULT_REPUTATION
        )

        caps = model.get("capabilities", {})
        feature_score = 0.0
        if caps.get("supports_vision", False):
            feature_score += 0.5
        if caps.get("supports_function_calling", False):
            feature_score += 0.5

        return (
            FreeChatConfig.CONTEXT_LENGTH_WEIGHT * context_score
            + FreeChatConfig.REPUTATION_WEIGHT * reputation
            + FreeChatConfig.FEATURES_WEIGHT * feature_score
        )

    def _is_available(self, model_id: str) -> bool:
        """Check if a model is not in cooldown."""
        cooldown_until = self._cooldowns.get(model_id)
        if cooldown_until is None:
            return True
        return time.time() >= cooldown_until

    def report_rate_limit(
        self, model_id: str, cooldown_seconds: float = FreeChatConfig.DEFAULT_COOLDOWN_SECONDS
    ) -> None:
        """Register a model for cooldown after rate limit."""
        self._cooldowns[model_id] = time.time() + cooldown_seconds
        logger.info(f"Model {model_id} in cooldown for {cooldown_seconds}s")

    def _cleanup_expired_cooldowns(self) -> None:
        """Remove expired cooldown entries."""
        now = time.time()
        self._cooldowns = {
            mid: until for mid, until in self._cooldowns.items() if until > now
        }
