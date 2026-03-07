"""Shared payloads and assertions for collective-intelligence handler tests."""

from __future__ import annotations

from typing import Any, Dict, List

from openrouter_mcp.collective_intelligence import shutdown_lifecycle_manager


def _model(
    model_id: str,
    name: str,
    provider: str,
    context_length: int,
    prompt_price: str,
    completion_price: str,
) -> Dict[str, Any]:
    return {
        "id": model_id,
        "name": name,
        "provider": provider,
        "context_length": context_length,
        "pricing": {"prompt": prompt_price, "completion": completion_price},
    }


def mocked_available_models() -> List[Dict[str, Any]]:
    """Default model list for mocked collective-intelligence tests."""
    return [
        _model("openai/gpt-4", "GPT-4", "openai", 8192, "0.00001", "0.00003"),
        _model(
            "anthropic/claude-3-opus",
            "Claude 3 Opus",
            "anthropic",
            200000,
            "0.000005",
            "0.000015",
        ),
        _model(
            "meta-llama/llama-3-70b",
            "Llama 3 70B",
            "meta-llama",
            8000,
            "0.000005",
            "0.00001",
        ),
    ]


def contract_model_pair() -> List[Dict[str, Any]]:
    """Two-model pair used by contract and regression tests."""
    return [
        _model("openai/gpt-4", "GPT-4", "openai", 8192, "0.00003", "0.00006"),
        _model(
            "anthropic/claude-3-opus",
            "Claude 3 Opus",
            "anthropic",
            200000,
            "0.000015",
            "0.000075",
        ),
    ]


def regression_mock_models() -> List[Dict[str, Any]]:
    """Extended model list used by regression tests."""
    return contract_model_pair() + [
        _model(
            "meta-llama/llama-3-70b",
            "Llama 3 70B",
            "meta-llama",
            8000,
            "0.00001",
            "0.00002",
        ),
        _model(
            "deepseek/deepseek-coder",
            "DeepSeek Coder",
            "deepseek",
            16000,
            "0.000001",
            "0.000002",
        ),
    ]


def assert_collective_chat_response_shape(
    result: Dict[str, Any],
    *,
    min_response_length: int = 1,
    min_model_count: int = 2,
) -> None:
    """Assert the common response envelope for collective chat outputs."""
    assert isinstance(result, dict)
    assert "consensus_response" in result
    assert "agreement_level" in result
    assert "confidence_score" in result
    assert "participating_models" in result
    assert "individual_responses" in result
    assert isinstance(result["consensus_response"], str)
    assert len(result["consensus_response"]) >= min_response_length
    assert 0.0 <= result["confidence_score"] <= 1.0
    assert len(result["participating_models"]) >= min_model_count
    assert len(result["individual_responses"]) >= min_model_count


async def cleanup_collective_lifecycle() -> None:
    """Shutdown singleton lifecycle manager between tests."""
    await shutdown_lifecycle_manager()


__all__ = [
    "assert_collective_chat_response_shape",
    "cleanup_collective_lifecycle",
    "contract_model_pair",
    "mocked_available_models",
    "regression_mock_models",
]
