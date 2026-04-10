from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.runtime_thrift.response_metadata import (
    attach_thrift_metadata_from_payload,
    enrich_response_with_thrift_metadata,
)


class TestResponseMetadata:
    @pytest.mark.unit
    def test_attaches_thrift_metadata_from_payload_total_cost(self):
        payload = {
            "total_cost": 0.09,
            "total_tokens": 1800,
            "requests": 10,
        }
        thrift_metrics = {
            "saved_cost_usd": 0.01,
            "saved_prompt_tokens": 442,
            "cached_prompt_tokens": 300,
            "cache_write_prompt_tokens": 100,
            "cache_hit_requests": 1,
            "cache_write_requests": 1,
            "compacted_tokens": 42,
            "saved_completion_tokens": 20,
            "coalesced_requests": 1,
            "deferred_requests": 0,
            "cache_efficiency_by_provider": {
                "anthropic": {
                    "observed_requests": 4,
                    "cached_prompt_tokens": 300,
                    "cache_write_prompt_tokens": 100,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.01,
                }
            },
            "cache_efficiency_by_model": {
                "anthropic/claude-sonnet-4": {
                    "observed_requests": 4,
                    "cached_prompt_tokens": 300,
                    "cache_write_prompt_tokens": 100,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.01,
                }
            },
        }

        enriched = attach_thrift_metadata_from_payload(payload, thrift_metrics)

        assert enriched["thrift_metrics"] == thrift_metrics
        assert enriched["thrift_summary"]["saved_cost_usd"] == 0.01
        assert enriched["thrift_summary"]["estimated_cost_without_thrift_usd"] == 0.1
        assert enriched["thrift_summary"]["effective_cost_reduction_pct"] == 10.0
        assert (
            enriched["thrift_summary"]["prompt_savings_breakdown"]["recent_reuse_prompt_tokens"]
            == 0
        )
        assert enriched["thrift_summary"]["request_savings_breakdown"] == {
            "coalesced_requests": 1,
            "recent_reuse_requests": 0,
            "deferred_requests": 0,
        }
        assert enriched["thrift_summary"]["cache_efficiency"] == {
            "cached_prompt_tokens": 300,
            "cache_write_prompt_tokens": 100,
            "cache_hit_requests": 1,
            "cache_write_requests": 1,
            "cache_hit_request_rate_pct": 10.0,
            "cache_write_request_rate_pct": 10.0,
            "cache_hit_share_of_saved_prompt_tokens_pct": 67.87,
            "reuse_to_write_ratio": 3.0,
        }
        assert enriched["thrift_summary"]["cache_efficiency_by_provider"]["anthropic"] == {
            "observed_requests": 4,
            "cached_prompt_tokens": 300,
            "cache_write_prompt_tokens": 100,
            "cache_hit_requests": 1,
            "cache_write_requests": 1,
            "cache_hit_request_rate_pct": 25.0,
            "cache_write_request_rate_pct": 25.0,
            "reuse_to_write_ratio": 3.0,
            "saved_cost_usd": 0.01,
        }
        assert (
            enriched["thrift_summary"]["cache_efficiency_by_model"]["anthropic/claude-sonnet-4"][
                "cache_hit_request_rate_pct"
            ]
            == 25.0
        )

    @pytest.mark.unit
    def test_attaches_thrift_metadata_with_recent_reuse_breakdown(self):
        payload = {
            "total_cost": 0.09,
            "total_tokens": 1800,
            "requests": 10,
        }
        thrift_metrics = {
            "saved_cost_usd": 0.01,
            "saved_prompt_tokens": 492,
            "cached_prompt_tokens": 300,
            "cache_write_prompt_tokens": 100,
            "cache_hit_requests": 2,
            "cache_write_requests": 1,
            "compacted_tokens": 42,
            "saved_completion_tokens": 35,
            "coalesced_requests": 1,
            "recent_reuse_requests": 2,
            "recent_reuse_prompt_tokens": 50,
            "recent_reuse_completion_tokens": 15,
            "deferred_requests": 0,
            "cache_efficiency_by_provider": {
                "anthropic": {
                    "observed_requests": 5,
                    "cached_prompt_tokens": 300,
                    "cache_write_prompt_tokens": 100,
                    "cache_hit_requests": 2,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.01,
                }
            },
            "cache_efficiency_by_model": {
                "anthropic/claude-sonnet-4": {
                    "observed_requests": 5,
                    "cached_prompt_tokens": 300,
                    "cache_write_prompt_tokens": 100,
                    "cache_hit_requests": 2,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.01,
                }
            },
        }

        enriched = attach_thrift_metadata_from_payload(payload, thrift_metrics)

        breakdown = enriched["thrift_summary"]["prompt_savings_breakdown"]
        assert breakdown["cache_reuse_tokens"] == 300
        assert breakdown["coalesced_prompt_tokens"] == 142
        assert breakdown["recent_reuse_prompt_tokens"] == 50
        assert enriched["thrift_summary"]["request_savings_breakdown"] == {
            "coalesced_requests": 1,
            "recent_reuse_requests": 2,
            "deferred_requests": 0,
        }
        assert enriched["thrift_summary"]["cache_efficiency"]["cache_hit_requests"] == 2
        assert enriched["thrift_summary"]["cache_efficiency"]["cache_write_requests"] == 1
        assert enriched["thrift_summary"]["cache_efficiency"]["cache_hit_request_rate_pct"] == 20.0
        assert (
            enriched["thrift_summary"]["cache_efficiency"]["cache_write_request_rate_pct"] == 10.0
        )
        assert (
            enriched["thrift_summary"]["cache_efficiency_by_provider"]["anthropic"][
                "cache_hit_request_rate_pct"
            ]
            == 40.0
        )
        assert enriched["thrift_summary"]["cache_hotspots"] == {
            "providers": [
                {
                    "provider": "anthropic",
                    "saved_cost_usd": 0.01,
                    "cached_prompt_tokens": 300,
                    "cache_hit_request_rate_pct": 40.0,
                    "cache_write_request_rate_pct": 20.0,
                    "reuse_to_write_ratio": 3.0,
                    "reason": "Hit volume keeps pace with writes, so warming converts into real savings",
                }
            ],
            "models": [
                {
                    "model": "anthropic/claude-sonnet-4",
                    "saved_cost_usd": 0.01,
                    "cached_prompt_tokens": 300,
                    "cache_hit_request_rate_pct": 40.0,
                    "cache_write_request_rate_pct": 20.0,
                    "reuse_to_write_ratio": 3.0,
                    "reason": "Hit volume keeps pace with writes, so warming converts into real savings",
                }
            ],
        }

    @pytest.mark.unit
    def test_attaches_thrift_metadata_with_cache_hotspots_sorted_and_trimmed(self):
        payload = {
            "total_cost": 0.5,
            "total_tokens": 4000,
            "requests": 20,
        }
        thrift_metrics = {
            "saved_cost_usd": 0.04,
            "saved_prompt_tokens": 1200,
            "cached_prompt_tokens": 900,
            "cache_write_prompt_tokens": 260,
            "cache_hit_requests": 5,
            "cache_write_requests": 4,
            "compacted_tokens": 40,
            "saved_completion_tokens": 60,
            "coalesced_requests": 2,
            "recent_reuse_requests": 1,
            "recent_reuse_prompt_tokens": 100,
            "recent_reuse_completion_tokens": 10,
            "deferred_requests": 0,
            "cache_efficiency_by_provider": {
                "anthropic": {
                    "observed_requests": 6,
                    "cached_prompt_tokens": 500,
                    "cache_write_prompt_tokens": 120,
                    "cache_hit_requests": 3,
                    "cache_write_requests": 2,
                    "saved_cost_usd": 0.02,
                },
                "google": {
                    "observed_requests": 5,
                    "cached_prompt_tokens": 200,
                    "cache_write_prompt_tokens": 90,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.005,
                },
                "openai": {
                    "observed_requests": 4,
                    "cached_prompt_tokens": 100,
                    "cache_write_prompt_tokens": 20,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.009,
                },
                "xai": {
                    "observed_requests": 3,
                    "cached_prompt_tokens": 100,
                    "cache_write_prompt_tokens": 30,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.006,
                },
            },
            "cache_efficiency_by_model": {
                "anthropic/claude-sonnet-4": {
                    "observed_requests": 4,
                    "cached_prompt_tokens": 450,
                    "cache_write_prompt_tokens": 90,
                    "cache_hit_requests": 3,
                    "cache_write_requests": 2,
                    "saved_cost_usd": 0.018,
                },
                "anthropic/claude-haiku-4": {
                    "observed_requests": 2,
                    "cached_prompt_tokens": 50,
                    "cache_write_prompt_tokens": 30,
                    "cache_hit_requests": 0,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.002,
                },
                "google/gemini-2.5-pro": {
                    "observed_requests": 5,
                    "cached_prompt_tokens": 200,
                    "cache_write_prompt_tokens": 90,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.005,
                },
                "openai/gpt-4o-mini": {
                    "observed_requests": 4,
                    "cached_prompt_tokens": 100,
                    "cache_write_prompt_tokens": 20,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.009,
                },
                "xai/grok-4": {
                    "observed_requests": 3,
                    "cached_prompt_tokens": 100,
                    "cache_write_prompt_tokens": 30,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.006,
                },
            },
        }

        enriched = attach_thrift_metadata_from_payload(payload, thrift_metrics)

        assert enriched["thrift_summary"]["cache_hotspots"]["providers"] == [
            {
                "provider": "anthropic",
                "saved_cost_usd": 0.02,
                "cached_prompt_tokens": 500,
                "cache_hit_request_rate_pct": 50.0,
                "cache_write_request_rate_pct": 33.33,
                "reuse_to_write_ratio": 4.1667,
                "reason": "High hit rate and strong reuse-to-write ratio make this a primary savings source",
            },
            {
                "provider": "openai",
                "saved_cost_usd": 0.009,
                "cached_prompt_tokens": 100,
                "cache_hit_request_rate_pct": 25.0,
                "cache_write_request_rate_pct": 25.0,
                "reuse_to_write_ratio": 5.0,
                "reason": "Moderate hit rate, but each cache write gets reused multiple times",
            },
            {
                "provider": "xai",
                "saved_cost_usd": 0.006,
                "cached_prompt_tokens": 100,
                "cache_hit_request_rate_pct": 33.33,
                "cache_write_request_rate_pct": 33.33,
                "reuse_to_write_ratio": 3.3333,
                "reason": "Hit volume keeps pace with writes, so warming converts into real savings",
            },
        ]
        assert enriched["thrift_summary"]["cache_hotspots"]["models"] == [
            {
                "model": "anthropic/claude-sonnet-4",
                "saved_cost_usd": 0.018,
                "cached_prompt_tokens": 450,
                "cache_hit_request_rate_pct": 75.0,
                "cache_write_request_rate_pct": 50.0,
                "reuse_to_write_ratio": 5.0,
                "reason": "High hit rate and strong reuse-to-write ratio make this a primary savings source",
            },
            {
                "model": "openai/gpt-4o-mini",
                "saved_cost_usd": 0.009,
                "cached_prompt_tokens": 100,
                "cache_hit_request_rate_pct": 25.0,
                "cache_write_request_rate_pct": 25.0,
                "reuse_to_write_ratio": 5.0,
                "reason": "Moderate hit rate, but each cache write gets reused multiple times",
            },
            {
                "model": "xai/grok-4",
                "saved_cost_usd": 0.006,
                "cached_prompt_tokens": 100,
                "cache_hit_request_rate_pct": 33.33,
                "cache_write_request_rate_pct": 33.33,
                "reuse_to_write_ratio": 3.3333,
                "reason": "Hit volume keeps pace with writes, so warming converts into real savings",
            },
        ]

    @pytest.mark.unit
    def test_attaches_thrift_metadata_with_cache_deadspots_sorted_and_trimmed(self):
        payload = {
            "total_cost": 0.5,
            "total_tokens": 4000,
            "requests": 20,
        }
        thrift_metrics = {
            "saved_cost_usd": 0.04,
            "saved_prompt_tokens": 1200,
            "cached_prompt_tokens": 900,
            "cache_write_prompt_tokens": 420,
            "cache_hit_requests": 5,
            "cache_write_requests": 7,
            "compacted_tokens": 40,
            "saved_completion_tokens": 60,
            "coalesced_requests": 2,
            "recent_reuse_requests": 1,
            "recent_reuse_prompt_tokens": 100,
            "recent_reuse_completion_tokens": 10,
            "deferred_requests": 0,
            "cache_efficiency_by_provider": {
                "anthropic": {
                    "observed_requests": 8,
                    "cached_prompt_tokens": 120,
                    "cache_write_prompt_tokens": 200,
                    "cache_hit_requests": 0,
                    "cache_write_requests": 4,
                    "saved_cost_usd": 0.001,
                },
                "google": {
                    "observed_requests": 6,
                    "cached_prompt_tokens": 60,
                    "cache_write_prompt_tokens": 150,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 3,
                    "saved_cost_usd": 0.002,
                },
                "openai": {
                    "observed_requests": 4,
                    "cached_prompt_tokens": 90,
                    "cache_write_prompt_tokens": 80,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.006,
                },
                "xai": {
                    "observed_requests": 5,
                    "cached_prompt_tokens": 40,
                    "cache_write_prompt_tokens": 110,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 2,
                    "saved_cost_usd": 0.0015,
                },
            },
            "cache_efficiency_by_model": {
                "anthropic/claude-sonnet-4": {
                    "observed_requests": 5,
                    "cached_prompt_tokens": 0,
                    "cache_write_prompt_tokens": 160,
                    "cache_hit_requests": 0,
                    "cache_write_requests": 3,
                    "saved_cost_usd": 0.0,
                },
                "google/gemini-2.5-pro": {
                    "observed_requests": 4,
                    "cached_prompt_tokens": 30,
                    "cache_write_prompt_tokens": 120,
                    "cache_hit_requests": 0,
                    "cache_write_requests": 2,
                    "saved_cost_usd": 0.0007,
                },
                "xai/grok-4": {
                    "observed_requests": 5,
                    "cached_prompt_tokens": 40,
                    "cache_write_prompt_tokens": 110,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 2,
                    "saved_cost_usd": 0.0015,
                },
                "openai/gpt-4o-mini": {
                    "observed_requests": 4,
                    "cached_prompt_tokens": 90,
                    "cache_write_prompt_tokens": 80,
                    "cache_hit_requests": 1,
                    "cache_write_requests": 1,
                    "saved_cost_usd": 0.006,
                },
            },
        }

        enriched = attach_thrift_metadata_from_payload(payload, thrift_metrics)

        assert enriched["thrift_summary"]["cache_deadspots"] == {
            "providers": [
                {
                    "provider": "anthropic",
                    "saved_cost_usd": 0.001,
                    "cached_prompt_tokens": 120,
                    "cache_hit_request_rate_pct": 0.0,
                    "cache_write_request_rate_pct": 50.0,
                    "reuse_to_write_ratio": 0.6,
                    "reason": "Cache writes are piling up, but zero hits means warmups are being wasted",
                },
                {
                    "provider": "google",
                    "saved_cost_usd": 0.002,
                    "cached_prompt_tokens": 60,
                    "cache_hit_request_rate_pct": 16.67,
                    "cache_write_request_rate_pct": 50.0,
                    "reuse_to_write_ratio": 0.4,
                    "reason": "Cache writes are visible, but hit conversion is still weak",
                },
                {
                    "provider": "xai",
                    "saved_cost_usd": 0.0015,
                    "cached_prompt_tokens": 40,
                    "cache_hit_request_rate_pct": 20.0,
                    "cache_write_request_rate_pct": 40.0,
                    "reuse_to_write_ratio": 0.3636,
                    "reason": "Some hits exist, but reuse depth is still too shallow to justify the warmup cost",
                },
            ],
            "models": [
                {
                    "model": "anthropic/claude-sonnet-4",
                    "saved_cost_usd": 0.0,
                    "cached_prompt_tokens": 0,
                    "cache_hit_request_rate_pct": 0.0,
                    "cache_write_request_rate_pct": 60.0,
                    "reuse_to_write_ratio": 0.0,
                    "reason": "Cache writes are piling up, but zero hits means warmups are being wasted",
                },
                {
                    "model": "google/gemini-2.5-pro",
                    "saved_cost_usd": 0.0007,
                    "cached_prompt_tokens": 30,
                    "cache_hit_request_rate_pct": 0.0,
                    "cache_write_request_rate_pct": 50.0,
                    "reuse_to_write_ratio": 0.25,
                    "reason": "Cache writes are piling up, but zero hits means warmups are being wasted",
                },
                {
                    "model": "xai/grok-4",
                    "saved_cost_usd": 0.0015,
                    "cached_prompt_tokens": 40,
                    "cache_hit_request_rate_pct": 20.0,
                    "cache_write_request_rate_pct": 40.0,
                    "reuse_to_write_ratio": 0.3636,
                    "reason": "Some hits exist, but reuse depth is still too shallow to justify the warmup cost",
                },
            ],
        }

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_enriches_payload_with_thrift_metadata_and_estimated_cost(self):
        client = AsyncMock()
        client.get_model_pricing.return_value = {
            "prompt": 0.001,
            "completion": 0.002,
        }
        payload = {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }
        }
        thrift_metrics = {
            "saved_cost_usd": 0.006,
            "saved_prompt_tokens": 120,
            "cached_prompt_tokens": 80,
            "cache_write_prompt_tokens": 20,
            "cache_hit_requests": 1,
            "cache_write_requests": 1,
            "compacted_tokens": 5,
            "saved_completion_tokens": 10,
            "coalesced_requests": 1,
            "deferred_requests": 0,
        }

        enriched = await enrich_response_with_thrift_metadata(
            client=client,
            model="openai/gpt-4o",
            payload=payload,
            thrift_metrics=thrift_metrics,
        )

        assert enriched["thrift_metrics"] == thrift_metrics
        assert enriched["thrift_summary"]["saved_cost_usd"] == 0.006
        assert enriched["thrift_summary"]["estimated_cost_without_thrift_usd"] == 0.00602
        assert enriched["thrift_summary"]["prompt_savings_breakdown"]["cache_reuse_tokens"] == 80
        assert enriched["thrift_summary"]["cache_efficiency"]["cache_hit_request_rate_pct"] == 100.0
        assert (
            enriched["thrift_summary"]["cache_efficiency"]["cache_write_request_rate_pct"] == 100.0
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_enriches_payload_with_explicit_cost_override_without_pricing_lookup(self):
        client = AsyncMock()
        payload = {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }
        }
        thrift_metrics = {
            "saved_cost_usd": 0.006,
            "saved_prompt_tokens": 120,
            "cached_prompt_tokens": 80,
            "cache_write_prompt_tokens": 20,
            "cache_hit_requests": 1,
            "cache_write_requests": 1,
            "compacted_tokens": 5,
            "saved_completion_tokens": 10,
            "coalesced_requests": 1,
            "deferred_requests": 0,
        }

        enriched = await enrich_response_with_thrift_metadata(
            client=client,
            model="google/gemma-3-27b:free",
            payload=payload,
            thrift_metrics=thrift_metrics,
            total_cost_override_usd=0.0,
        )

        client.get_model_pricing.assert_not_called()
        assert enriched["thrift_summary"]["saved_cost_usd"] == 0.006
        assert enriched["thrift_summary"]["estimated_cost_without_thrift_usd"] == 0.006
        assert enriched["thrift_summary"]["cache_efficiency"]["cache_hit_request_rate_pct"] == 100.0
