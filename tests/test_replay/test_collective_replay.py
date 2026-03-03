"""Deterministic replay tests for collective handler flows."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from openrouter_mcp.collective_intelligence import shutdown_lifecycle_manager
from openrouter_mcp.handlers.collective_intelligence import (
    CollectiveChatRequest,
    _collective_chat_completion_impl,
)
from tests.fixtures.mock_clients import MockClientFactory

FIXTURE_FILE = Path(__file__).parent / "fixtures" / "collective_chat_replay.json"


@pytest.fixture(autouse=True)
async def cleanup_lifecycle_manager():
    """Reset singleton lifecycle manager between replay tests."""
    yield
    await shutdown_lifecycle_manager()


@pytest.fixture
def replay_fixture() -> dict:
    return json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))


@pytest.fixture
def replay_mock_client():
    client = MockClientFactory.create_openrouter_client()
    client.list_models = AsyncMock(
        return_value=[
            {
                "id": "openai/gpt-4",
                "name": "GPT-4",
                "provider": "openai",
                "context_length": 8192,
                "pricing": {"prompt": "0.00003", "completion": "0.00006"},
            },
            {
                "id": "anthropic/claude-3-opus",
                "name": "Claude 3 Opus",
                "provider": "anthropic",
                "context_length": 200000,
                "pricing": {"prompt": "0.000015", "completion": "0.000075"},
            },
        ]
    )
    client.get_model_pricing = AsyncMock(
        return_value={"prompt": 0.00001, "completion": 0.00002}
    )
    client.chat_completion = AsyncMock(
        return_value={
            "choices": [
                {
                    "message": {"content": "Replay fixture response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 12, "total_tokens": 24},
        }
    )
    return client


@pytest.mark.asyncio
@pytest.mark.replay
@patch("openrouter_mcp.handlers.collective_intelligence.get_openrouter_client")
async def test_collective_chat_replay_is_deterministic(
    mock_get_client, replay_mock_client, replay_fixture
):
    """Same replay fixture should produce stable key fields across runs."""
    mock_get_client.return_value = replay_mock_client

    request = CollectiveChatRequest(**replay_fixture["request"])

    first = await _collective_chat_completion_impl(request)
    second = await _collective_chat_completion_impl(request)

    for field in replay_fixture["stable_fields"]:
        assert first[field] == second[field]

    assert first["consensus_response"] == replay_fixture["expected_consensus_response"]
    assert len(first["participating_models"]) == request.min_models
