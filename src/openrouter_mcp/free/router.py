"""Free model router with quality-weighted selection and smart rotation."""

import logging
import time
from typing import Any, Dict, List, Optional

from ..config.constants import FreeChatConfig
from ..models.cache import ModelCache
from ..utils.metadata import extract_provider_from_id
from .classifier import TASK_MODEL_AFFINITY, TaskType
from .metrics import MetricsCollector

logger = logging.getLogger(__name__)


class FreeModelRouter:
    """Selects the best available free model using quality scoring and rotation."""

    def __init__(
        self,
        model_cache: ModelCache,
        metrics: Optional[MetricsCollector] = None,
    ) -> None:
        self._cache = model_cache
        self._cooldowns: Dict[str, float] = {}
        self._usage_counts: Dict[str, int] = {}
        self._metrics = metrics

    def _get_blended_reputation(self, provider: str, model_id: str) -> float:
        """Blend static reputation with real performance data when available."""
        static = FreeChatConfig.MODEL_REPUTATION.get(
            provider.lower(), FreeChatConfig.DEFAULT_REPUTATION
        )
        if self._metrics is None:
            return static
        m = self._metrics.get_metrics(model_id)
        if m is None or m.total_requests < FreeChatConfig.ADAPTIVE_MIN_REQUESTS:
            return static
        alpha = min(
            m.total_requests / FreeChatConfig.ADAPTIVE_RAMP_REQUESTS,
            FreeChatConfig.ADAPTIVE_MAX_ALPHA,
        )
        perf_score = self._metrics.get_performance_score(model_id)
        return alpha * perf_score + (1 - alpha) * static

    def _score_model(
        self, model: dict, task_type: Optional[TaskType] = None
    ) -> float:
        """Score a model from 0.0 to 1.0 based on quality heuristics."""
        context_length = model.get("context_length", 0)
        context_score = min(context_length / FreeChatConfig.MAX_CONTEXT_LENGTH, 1.0)

        provider = model.get("provider", "")
        if not provider or provider == "unknown":
            provider = extract_provider_from_id(model.get("id", "")).value
        reputation = self._get_blended_reputation(provider, model.get("id", ""))

        caps = model.get("capabilities", {})
        feature_score = 0.0
        if caps.get("supports_vision", False):
            feature_score += 0.5
        if caps.get("supports_function_calling", False):
            feature_score += 0.5

        base_score = (
            FreeChatConfig.CONTEXT_LENGTH_WEIGHT * context_score
            + FreeChatConfig.REPUTATION_WEIGHT * reputation
            + FreeChatConfig.FEATURES_WEIGHT * feature_score
        )

        # Apply task-type affinity bonus
        if task_type is not None:
            affinity = TASK_MODEL_AFFINITY.get(task_type, {})
            bonus = affinity.get(provider.lower(), 0.0)
            base_score += bonus

        return min(1.0, base_score)

    def list_models_with_status(self) -> List[Dict[str, Any]]:
        """Return all free models with quality scores and availability.

        Note: Scores here exclude task-type affinity bonuses since no specific
        task context is available. Actual selection scores in select_model()
        may differ when a task_type is provided.
        """
        free_models = self._cache.filter_models(free_only=True)
        result = []
        for model in free_models:
            result.append({
                "id": model.get("id", ""),
                "name": model.get("name", ""),
                "context_length": model.get("context_length", 0),
                "provider": model.get("provider", "unknown"),
                "quality_score": round(self._score_model(model), 3),
                "available": self._is_available(model.get("id", "")),
            })
        result.sort(key=lambda m: -m["quality_score"])
        return result

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

    async def select_model(
        self,
        preferred_models: Optional[List[str]] = None,
        task_type: Optional[TaskType] = None,
    ) -> str:
        """Select the best available free model."""
        self._cleanup_expired_cooldowns()

        free_models = self._cache.filter_models(free_only=True)

        if not free_models:
            raise RuntimeError("사용 가능한 free 모델이 없습니다. 캐시를 새로고침해주세요.")

        # Try preferred models first (only if they are actually free)
        if preferred_models:
            free_model_ids = {m["id"] for m in free_models}
            for pref_id in preferred_models:
                if pref_id in free_model_ids and self._is_available(pref_id):
                    self._usage_counts[pref_id] = self._usage_counts.get(pref_id, 0) + 1
                    return pref_id

        # Decay usage counts when all free models have been used at least once
        if self._usage_counts and len(self._usage_counts) >= len(free_models):
            min_count = min(
                self._usage_counts.get(m["id"], 0) for m in free_models
            )
            if min_count > 0:
                for mid in list(self._usage_counts):
                    self._usage_counts[mid] -= min_count

        # Filter available models and score with usage-based rotation penalty
        usage_penalty = FreeChatConfig.USAGE_PENALTY_FACTOR
        candidates = [
            (model, max(0.0, self._score_model(model, task_type) - self._usage_counts.get(model["id"], 0) * usage_penalty))
            for model in free_models
            if self._is_available(model["id"])
        ]

        if not candidates:
            soonest = min(self._cooldowns.values()) - time.time() if self._cooldowns else 0
            raise RuntimeError(
                f"사용 가능한 free 모델이 없습니다. {max(0, soonest):.0f}초 후 재시도해주세요."
            )

        # Sort by effective score descending
        candidates.sort(key=lambda x: -x[1])

        selected = candidates[0][0]
        model_id = selected["id"]
        self._usage_counts[model_id] = self._usage_counts.get(model_id, 0) + 1

        logger.info(f"Selected free model: {model_id} (score={candidates[0][1]:.3f})")
        return model_id
