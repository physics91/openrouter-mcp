from unittest.mock import AsyncMock

import httpx
import pytest

from src.openrouter_mcp.client.openrouter import InvalidRequestError, OpenRouterClient
from src.openrouter_mcp.handlers.chat import UsageStatsRequest, get_usage_stats

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def test_usage_uses_current_key_endpoint_and_does_not_invent_token_counts():
    def respond(request):
        assert request.url.path == "/api/v1/key"
        assert not request.url.query
        return httpx.Response(
            200,
            json={
                "data": {
                    "usage": 12.5,
                    "usage_daily": 0.5,
                    "limit_remaining": 7.5,
                    "label": "private key label",
                    "creator_user_id": "private-user",
                }
            },
        )

    async with OpenRouterClient(api_key="test-key", enable_cache=False) as client:
        await client._client.aclose()
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        result = await client.track_usage()
    assert result["total_cost"] == 12.5
    assert result["scope"] == "api_key"
    assert result["usage_daily"] == 0.5
    assert result["total_tokens"] is None
    assert result["requests"] is None
    assert "label" not in result
    assert "creator_user_id" not in result


@pytest.mark.parametrize(
    "dates", [{"start_date": "2026-10-01"}, {"end_date": "2026-10-05"}]
)
async def test_unsupported_date_ranges_fail_before_http(dates):
    async with OpenRouterClient(api_key="test-key", enable_cache=False) as client:
        client._make_request = AsyncMock()
        with pytest.raises(InvalidRequestError, match="date range"):
            await client.track_usage(**dates)
        client._make_request.assert_not_called()


async def test_usage_response_keeps_remote_spending_separate_from_local_savings(
    monkeypatch,
):
    client = AsyncMock()
    client.track_usage.return_value = {
        "scope": "api_key",
        "total_cost": 12.5,
        "requests": None,
    }
    monkeypatch.setattr(
        "src.openrouter_mcp.handlers.chat.get_openrouter_client",
        AsyncMock(return_value=client),
    )
    result = await get_usage_stats(UsageStatsRequest())
    assert result["thrift_scope"] == "local_runtime"
    assert result["thrift_summary"]["estimated_cost_without_thrift_usd"] is None
    assert result["thrift_summary"]["effective_cost_reduction_pct"] is None
