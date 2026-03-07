#!/usr/bin/env python3
"""
E2E tests for OpenRouter MCP Server.

FastMCP Client를 사용하여 MCP 프로토콜 레벨에서 서버를 실 검증합니다.
실제 OpenRouter API 호출이 발생하므로 OPENROUTER_API_KEY가 필요합니다.
"""

import json
import os

import pytest
from dotenv import load_dotenv
from fastmcp import Client

load_dotenv()

pytestmark = [pytest.mark.e2e, pytest.mark.real_api]

EXPECTED_TOOLS = {
    # chat.py
    "chat_with_model",
    "list_available_models",
    "get_usage_stats",
    # multimodal.py
    "chat_with_vision",
    "list_vision_models",
    # free_chat.py
    "free_chat",
    "list_free_models",
    "get_free_model_metrics",
    # mcp_benchmark.py
    "benchmark_models",
    "get_benchmark_history",
    "compare_model_categories",
    "export_benchmark_report",
    "compare_model_performance",
    # collective_intelligence.py
    "collective_chat_completion",
    "ensemble_reasoning",
    "adaptive_model_selection",
    "cross_model_validation",
    "collaborative_problem_solving",
}


def _skip_without_api_key():
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")


def _get_mcp_app():
    """Register handlers and return the shared FastMCP instance."""
    from src.openrouter_mcp.handlers import register_handlers
    from src.openrouter_mcp.mcp_registry import mcp

    register_handlers()
    return mcp


@pytest.fixture
def mcp_app():
    _skip_without_api_key()
    return _get_mcp_app()


def _text_from(result) -> str:
    """CallToolResult에서 텍스트 콘텐츠를 추출한다."""
    for item in result.content:
        if hasattr(item, "text"):
            return item.text
    return ""


def _json_from(result) -> dict:
    """CallToolResult에서 JSON 파싱된 dict를 반환한다."""
    return json.loads(_text_from(result))


# ── Tool Registration ──────────────────────────────────────────────


class TestToolRegistration:
    """MCP 프로토콜을 통해 도구 목록이 정상 노출되는지 검증."""

    async def test_all_tools_registered(self, mcp_app):
        async with Client(mcp_app) as client:
            tools = await client.list_tools()
            tool_names = {t.name for t in tools}

            missing = EXPECTED_TOOLS - tool_names
            assert not missing, f"Missing tools: {missing}"

    async def test_tool_count_minimum(self, mcp_app):
        async with Client(mcp_app) as client:
            tools = await client.list_tools()
            assert len(tools) >= len(EXPECTED_TOOLS)

    async def test_tools_have_descriptions(self, mcp_app):
        async with Client(mcp_app) as client:
            tools = await client.list_tools()
            for tool in tools:
                assert tool.description, f"{tool.name} has no description"


# ── Core Chat Tools ────────────────────────────────────────────────


class TestChatTools:
    """chat_with_model, list_available_models, get_usage_stats 실 검증."""

    async def test_list_available_models(self, mcp_app):
        async with Client(mcp_app) as client:
            result = await client.call_tool(
                "list_available_models",
                {"request": {"filter_by": "gpt"}},
            )
            text = _text_from(result)
            models = json.loads(text)
            assert isinstance(models, list)
            assert len(models) > 0
            assert any("gpt" in m.get("id", "").lower() for m in models)

    async def test_chat_with_model(self, mcp_app):
        async with Client(mcp_app) as client:
            result = await client.call_tool(
                "chat_with_model",
                {
                    "request": {
                        "model": "openai/gpt-4o-mini",
                        "messages": [{"role": "user", "content": "Say 'hello' and nothing else."}],
                        "temperature": 0.0,
                        "max_tokens": 10,
                    }
                },
            )
            text = _text_from(result)
            data = json.loads(text)
            assert "choices" in data
            content = data["choices"][0]["message"]["content"].lower()
            assert "hello" in content


# ── Free Chat Tools ────────────────────────────────────────────────


class TestFreeChatTools:
    """무료 모델 도구 실 검증."""

    async def test_list_free_models(self, mcp_app):
        async with Client(mcp_app) as client:
            result = await client.call_tool("list_free_models", {})
            data = _json_from(result)
            assert isinstance(data, (dict, list))

    async def test_free_chat(self, mcp_app):
        async with Client(mcp_app) as client:
            result = await client.call_tool(
                "free_chat",
                {
                    "request": {
                        "message": "Say 'hi' and nothing else.",
                        "max_tokens": 10,
                    }
                },
            )
            text = _text_from(result)
            assert len(text) > 0


# ── Collective Intelligence Tools ──────────────────────────────────


class TestCollectiveIntelligenceTools:
    """집단지능 도구 MCP 프로토콜 실 검증."""

    @pytest.mark.slow
    async def test_collective_chat_completion(self, mcp_app):
        async with Client(mcp_app, timeout=120) as client:
            result = await client.call_tool(
                "collective_chat_completion",
                {
                    "request": {
                        "prompt": "What is 2+2?",
                        "strategy": "majority_vote",
                        "min_models": 2,
                        "max_models": 2,
                        "temperature": 0.0,
                    }
                },
            )
            data = _json_from(result)
            assert "consensus_response" in data
            assert "participating_models" in data
            assert len(data["participating_models"]) >= 2

    @pytest.mark.slow
    async def test_adaptive_model_selection(self, mcp_app):
        async with Client(mcp_app, timeout=60) as client:
            result = await client.call_tool(
                "adaptive_model_selection",
                {
                    "request": {
                        "query": "Hello world in Python",
                        "task_type": "code_generation",
                    }
                },
            )
            data = _json_from(result)
            assert "selected_model" in data
            assert "confidence" in data

    @pytest.mark.slow
    async def test_cross_model_validation(self, mcp_app):
        async with Client(mcp_app, timeout=60) as client:
            result = await client.call_tool(
                "cross_model_validation",
                {
                    "request": {
                        "content": "Python is a high-level programming language.",
                        "threshold": 0.7,
                    }
                },
            )
            data = _json_from(result)
            assert "validation_result" in data
            assert data["validation_result"] in ("VALID", "INVALID")
