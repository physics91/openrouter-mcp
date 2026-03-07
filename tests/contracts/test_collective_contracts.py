"""Contract tests for collective-intelligence MCP tool responses."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from jsonschema import Draft202012Validator

from openrouter_mcp.handlers.collective_intelligence import (
    AdaptiveModelRequest,
    CollaborativeSolvingRequest,
    CollectiveChatRequest,
    CrossValidationRequest,
    EnsembleReasoningRequest,
    _adaptive_model_selection_impl,
    _collaborative_problem_solving_impl,
    _collective_chat_completion_impl,
    _cross_model_validation_impl,
    _ensemble_reasoning_impl,
)
from tests.fixtures.collective_payloads import (
    cleanup_collective_lifecycle,
    contract_model_pair,
)
from tests.fixtures.mock_clients import MockClientFactory

SCHEMA_DIR = Path(__file__).parent / "schemas"
MODEL_IDS = ["openai/gpt-4", "anthropic/claude-3-opus"]


@pytest.fixture(autouse=True)
async def cleanup_lifecycle_manager():
    """Reset singleton lifecycle manager between contract tests."""
    yield
    await cleanup_collective_lifecycle()


@pytest.fixture
def contract_mock_client():
    """Create a deterministic OpenRouter client mock for contract tests."""
    client = MockClientFactory.create_openrouter_client()
    client.list_models = AsyncMock(return_value=contract_model_pair())
    client.get_model_pricing = AsyncMock(
        return_value={"prompt": 0.00001, "completion": 0.00002}
    )
    client.chat_completion = AsyncMock(
        return_value={
            "choices": [
                {
                    "message": {"content": "Contract-test response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 18, "completion_tokens": 24, "total_tokens": 42},
        }
    )
    return client


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))


def _assert_schema(instance: dict, schema_file: str) -> None:
    schema = _load_schema(schema_file)
    Draft202012Validator(schema).validate(instance)


@pytest.mark.asyncio
@pytest.mark.contract
@patch("openrouter_mcp.handlers.collective_intelligence.get_openrouter_client")
async def test_collective_chat_completion_contract(
    mock_get_client, contract_mock_client
):
    mock_get_client.return_value = contract_mock_client

    response = await _collective_chat_completion_impl(
        CollectiveChatRequest(
            prompt="Summarize test contracts",
            models=MODEL_IDS,
            min_models=2,
            max_models=2,
            strategy="majority_vote",
        )
    )

    _assert_schema(response, "collective_chat_completion.response.schema.json")


@pytest.mark.asyncio
@pytest.mark.contract
@patch("openrouter_mcp.handlers.collective_intelligence.get_openrouter_client")
async def test_ensemble_reasoning_contract(mock_get_client, contract_mock_client):
    mock_get_client.return_value = contract_mock_client

    response = await _ensemble_reasoning_impl(
        EnsembleReasoningRequest(
            problem="Plan a migration strategy",
            task_type="analysis",
            decompose=False,
            models=MODEL_IDS,
        )
    )

    _assert_schema(response, "ensemble_reasoning.response.schema.json")


@pytest.mark.asyncio
@pytest.mark.contract
@patch("openrouter_mcp.handlers.collective_intelligence.get_openrouter_client")
async def test_adaptive_model_selection_contract(mock_get_client, contract_mock_client):
    mock_get_client.return_value = contract_mock_client

    response = await _adaptive_model_selection_impl(
        AdaptiveModelRequest(
            query="Generate robust Python test code",
            task_type="code_generation",
            performance_requirements={"accuracy": 0.9, "speed": 0.7},
        )
    )

    _assert_schema(response, "adaptive_model_selection.response.schema.json")


@pytest.mark.asyncio
@pytest.mark.contract
@patch("openrouter_mcp.handlers.collective_intelligence.get_openrouter_client")
async def test_cross_model_validation_contract(mock_get_client, contract_mock_client):
    mock_get_client.return_value = contract_mock_client

    response = await _cross_model_validation_impl(
        CrossValidationRequest(
            content="Python is an interpreted programming language.",
            validation_criteria=["factual_accuracy", "technical_correctness"],
            threshold=0.7,
            models=MODEL_IDS,
        )
    )

    _assert_schema(response, "cross_model_validation.response.schema.json")


@pytest.mark.asyncio
@pytest.mark.contract
@patch("openrouter_mcp.handlers.collective_intelligence.get_openrouter_client")
async def test_collaborative_problem_solving_contract(
    mock_get_client, contract_mock_client
):
    mock_get_client.return_value = contract_mock_client

    response = await _collaborative_problem_solving_impl(
        CollaborativeSolvingRequest(
            problem="Design a lightweight release checklist",
            max_iterations=2,
            models=MODEL_IDS,
            requirements={"budget": "low"},
        )
    )

    _assert_schema(response, "collaborative_problem_solving.response.schema.json")
