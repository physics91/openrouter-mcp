"""OpenRouter model provider adapter for collective intelligence components."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from ..client.openrouter import OpenRouterClient

from ..collective_intelligence import ModelInfo, ProcessingResult, TaskContext
from ..collective_intelligence.base import ModelCapability
from ..config.constants import ConsensusDefaults, ModelDefaults, PricingDefaults
from ..utils.pricing import estimate_cost_from_usage, normalize_pricing

logger = logging.getLogger(f"{__package__}.collective_intelligence")


def _first_response_choice(response: dict[str, Any]) -> tuple[bool, Any]:
    """Return whether a response has choices and its first unmodified item."""
    choices = response.get("choices") or []
    return (True, choices[0]) if choices else (False, None)


class OpenRouterModelProvider:
    """OpenRouter implementation of ModelProvider protocol."""

    def __init__(self, client: OpenRouterClient):
        """
        Initialize the model provider.

        Args:
            client: OpenRouterClient instance that already has cache configured
        """
        self.client = client
        self._model_pricing_cache: dict[str, dict[str, float]] = {}

    @staticmethod
    def _build_chat_completion_parameters(
        task: TaskContext,
        kwargs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], Any, Any]:
        """Build chat messages and resolve generation parameter precedence."""
        messages = [{"role": "user", "content": task.content}]

        if task.requirements.get("system_prompt"):
            messages.insert(
                0, {"role": "system", "content": task.requirements["system_prompt"]}
            )

        temp_from_req = task.requirements.get("temperature")
        temp_from_kwargs = kwargs.get("temperature")
        temperature = (
            temp_from_req
            if temp_from_req is not None
            else (
                temp_from_kwargs
                if temp_from_kwargs is not None
                else ModelDefaults.TEMPERATURE
            )
        )

        kw_max = kwargs.get("max_tokens")
        max_tokens_val = (
            kw_max if kw_max is not None else task.requirements.get("max_tokens")
        )

        return messages, temperature, max_tokens_val

    async def _build_processing_result(
        self,
        task: TaskContext,
        model_id: str,
        response: dict[str, Any],
        processing_time: float,
    ) -> ProcessingResult:
        """Convert one chat response into a collective processing result."""
        has_choice, first_choice = _first_response_choice(response)
        content = ""
        if has_choice:
            content = first_choice["message"]["content"]

        confidence = self._calculate_confidence(response, content)

        usage = response.get("usage", {})
        tokens_used = usage.get("total_tokens", 0)

        cost = await self._estimate_cost(model_id, usage)

        return ProcessingResult(
            task_id=task.task_id,
            model_id=model_id,
            content=content,
            confidence=confidence,
            processing_time=processing_time,
            tokens_used=tokens_used,
            cost=cost,
            metadata={
                "usage": usage,
                "response_metadata": response.get("model", {}),
            },
        )

    async def process_task(
        self, task: TaskContext, model_id: str, **kwargs: Any
    ) -> ProcessingResult:
        """Process a task using the specified model."""
        start_time = datetime.now()

        try:
            messages, temperature, max_tokens_val = (
                self._build_chat_completion_parameters(task, kwargs)
            )

            # Call OpenRouter API
            response = await self.client.chat_completion(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens_val,
                stream=False,
            )

            processing_time = (datetime.now() - start_time).total_seconds()

            return await self._build_processing_result(
                task,
                model_id,
                response,
                processing_time,
            )

        except Exception as e:
            logger.error(f"Task processing failed for model {model_id}: {e!s}")
            raise

    def _build_model_info(self, raw_model: dict[str, Any]) -> ModelInfo:
        """Convert one raw model payload into collective model metadata."""
        model_info = ModelInfo(
            model_id=raw_model["id"],
            name=raw_model.get("name", raw_model["id"]),
            provider=raw_model.get("provider", "unknown"),
            context_length=raw_model.get("context_length", 4096),
            cost_per_token=self._extract_cost(raw_model.get("pricing", {})),
            metadata=raw_model,
        )
        model_info.capabilities = self._estimate_capabilities(raw_model)
        return model_info

    async def get_available_models(self) -> list[ModelInfo]:
        """
        Get list of available models.

        This method delegates to the client's cache system, eliminating
        the redundant local cache and preventing unnecessary API calls.
        """
        try:
            # Use client's built-in cache system
            raw_models = await self.client.list_models(use_cache=True)

            # Convert to ModelInfo objects
            models = []
            for raw_model in raw_models:
                models.append(self._build_model_info(raw_model))

            return models

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"Failed to fetch models: {e!s}")
            raise RuntimeError(
                f"Unable to fetch available models from OpenRouter: {type(e).__name__}. "
                "Check network connectivity and API key configuration."
            ) from e

    def _calculate_confidence(self, response: dict[str, Any], content: str) -> float:
        """Calculate confidence score based on response characteristics."""
        # This is a simplified confidence calculation
        # In practice, this could use more sophisticated methods

        base_confidence = float(ConsensusDefaults.CONFIDENCE_THRESHOLD)

        # Adjust based on response length (longer responses often more confident)
        if len(content) > 100:
            base_confidence += 0.1
        elif len(content) < 20:
            base_confidence -= 0.2

        # Adjust based on finish reason
        has_choice, first_choice = _first_response_choice(response)
        finish_reason = first_choice.get("finish_reason") if has_choice else None
        if finish_reason == "stop":
            base_confidence += 0.1
        elif finish_reason == "length":
            base_confidence -= 0.1

        return float(max(0.0, min(1.0, base_confidence)))

    async def _get_model_pricing(self, model_id: str) -> dict[str, float]:
        """
        Get pricing information for a specific model.

        Delegates to the client's public ``get_model_pricing()`` API which
        already handles cache look-up, fallback, and normalisation.

        Args:
            model_id: Model identifier

        Returns:
            Dictionary with 'prompt' and 'completion' cost per token
        """
        if model_id in self._model_pricing_cache:
            return self._model_pricing_cache[model_id]

        try:
            normalized_raw = await self.client.get_model_pricing(model_id)
        except Exception as e:
            logger.warning(f"Failed to fetch pricing for model {model_id}: {e}")
            normalized_raw = normalize_pricing({}, PricingDefaults.DEFAULT_TOKEN_PRICE)

        normalized = {
            "prompt": float(normalized_raw.get("prompt", 0.0)),
            "completion": float(normalized_raw.get("completion", 0.0)),
        }

        self._model_pricing_cache[model_id] = normalized
        return normalized

    async def _estimate_cost(self, model_id: str, usage: dict[str, int]) -> float:
        """
        Estimate cost based on actual model pricing and token usage.

        Args:
            model_id: Model identifier
            usage: Usage dictionary with 'prompt_tokens' and 'completion_tokens'

        Returns:
            Estimated cost in USD
        """
        pricing = await self._get_model_pricing(model_id)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_cost = float(
            estimate_cost_from_usage(
                usage,
                pricing,
                PricingDefaults.DEFAULT_TOKEN_PRICE,
            )
        )
        prompt_cost = prompt_tokens * pricing["prompt"]
        completion_cost = completion_tokens * pricing["completion"]

        logger.debug(
            f"Cost calculation for {model_id}: "
            f"{prompt_tokens} prompt tokens (${prompt_cost:.6f}) + "
            f"{completion_tokens} completion tokens (${completion_cost:.6f}) = "
            f"${total_cost:.6f}"
        )

        return total_cost

    def _extract_cost(self, pricing: dict[str, Any]) -> float:
        """Extract cost per token from pricing information."""
        normalized = normalize_pricing(pricing, PricingDefaults.DEFAULT_TOKEN_PRICE)
        return float(normalized.get("completion", PricingDefaults.DEFAULT_TOKEN_PRICE))

    def _estimate_capabilities(
        self, raw_model: dict[str, Any]
    ) -> dict[ModelCapability, float]:
        """Estimate model capabilities based on model metadata."""
        capabilities: dict[ModelCapability, float] = {}
        model_id = raw_model["id"].lower()

        # Reasoning capability
        if any(term in model_id for term in ["gpt-4", "claude", "o1"]):
            capabilities[ModelCapability.REASONING] = 0.9
        elif any(term in model_id for term in ["gpt-3.5", "llama"]):
            capabilities[ModelCapability.REASONING] = 0.7
        else:
            capabilities[ModelCapability.REASONING] = 0.5

        # Creativity capability
        if any(term in model_id for term in ["claude", "gpt-4"]):
            capabilities[ModelCapability.CREATIVITY] = 0.8
        else:
            capabilities[ModelCapability.CREATIVITY] = 0.6

        # Code capability
        if any(term in model_id for term in ["code", "codestral", "deepseek"]):
            capabilities[ModelCapability.CODE] = 0.9
        elif any(term in model_id for term in ["gpt-4", "claude"]):
            capabilities[ModelCapability.CODE] = 0.8
        else:
            capabilities[ModelCapability.CODE] = 0.5

        # Accuracy capability
        if any(term in model_id for term in ["gpt-4", "claude", "o1"]):
            capabilities[ModelCapability.ACCURACY] = 0.9
        else:
            capabilities[ModelCapability.ACCURACY] = 0.7

        return capabilities
