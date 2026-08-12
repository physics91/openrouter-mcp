from datetime import datetime

import pytest

from src.openrouter_mcp.config.constants import PricingDefaults
from src.openrouter_mcp.runtime_thrift import (
    ThriftMetricsCollector,
    get_thrift_metrics_snapshot,
    record_coalesced_savings,
    record_compaction_savings,
    record_model_request,
    record_prompt_cache_activity,
    record_recent_reuse_savings,
    reset_thrift_metrics,
)
from src.openrouter_mcp.runtime_thrift.metrics import (
    ThriftMetrics,
    _record_coalesced_savings_on_metrics,
    _record_recent_reuse_savings_on_metrics,
    _record_saved_token_totals_on_metrics,
    get_request_thrift_metrics_snapshot,
    thrift_request_scope,
)


class _MutationTrackingMetrics:
    def __init__(self):
        object.__setattr__(self, "mutations", [])
        object.__setattr__(self, "tracking", False)
        for field_name in ThriftMetrics.__dataclass_fields__:
            if field_name not in {
                "cache_efficiency_by_provider",
                "cache_efficiency_by_model",
            }:
                setattr(self, field_name, 0)
        object.__setattr__(self, "tracking", True)

    def __setattr__(self, name, value):
        if self.tracking:
            self.mutations.append(name)
        object.__setattr__(self, name, value)


class TestRuntimeThriftMetrics:
    @pytest.mark.unit
    def test_shared_saved_token_totals_use_default_cost_policy(self):
        metrics = ThriftMetrics(
            saved_prompt_tokens=10,
            saved_completion_tokens=20,
            saved_cost_usd=1.0,
        )

        _record_saved_token_totals_on_metrics(
            metrics,
            prompt_tokens=2,
            completion_tokens=3,
            estimated_cost_usd=None,
        )

        assert metrics.saved_prompt_tokens == 12
        assert metrics.saved_completion_tokens == 23
        assert metrics.saved_cost_usd == pytest.approx(
            1.0 + (5 * PricingDefaults.ESTIMATED_TOKEN_PRICE)
        )

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("record_savings", "expected_mutations"),
        [
            (
                _record_coalesced_savings_on_metrics,
                [
                    "coalesced_requests",
                    "saved_prompt_tokens",
                    "saved_completion_tokens",
                    "saved_cost_usd",
                ],
            ),
            (
                _record_recent_reuse_savings_on_metrics,
                [
                    "recent_reuse_requests",
                    "recent_reuse_prompt_tokens",
                    "recent_reuse_completion_tokens",
                    "saved_prompt_tokens",
                    "saved_completion_tokens",
                    "saved_cost_usd",
                ],
            ),
        ],
    )
    def test_savings_metrics_preserve_mutation_order(
        self,
        record_savings,
        expected_mutations,
    ):
        metrics = _MutationTrackingMetrics()

        record_savings(metrics, prompt_tokens=2, completion_tokens=3)

        assert metrics.mutations == expected_mutations

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "record_savings",
        [
            _record_coalesced_savings_on_metrics,
            _record_recent_reuse_savings_on_metrics,
        ],
    )
    @pytest.mark.parametrize(
        ("prompt_tokens", "completion_tokens"),
        [("invalid", 1), (1, "invalid")],
    )
    def test_savings_metrics_do_not_mutate_when_token_conversion_fails(
        self,
        record_savings,
        prompt_tokens,
        completion_tokens,
    ):
        metrics = ThriftMetrics()

        with pytest.raises(ValueError):
            record_savings(metrics, prompt_tokens, completion_tokens)

        assert metrics == ThriftMetrics()

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("record_savings", "expected_metrics"),
        [
            (
                _record_coalesced_savings_on_metrics,
                ThriftMetrics(
                    coalesced_requests=1,
                    saved_prompt_tokens=2,
                    saved_completion_tokens=3,
                ),
            ),
            (
                _record_recent_reuse_savings_on_metrics,
                ThriftMetrics(
                    recent_reuse_requests=1,
                    recent_reuse_prompt_tokens=2,
                    recent_reuse_completion_tokens=3,
                    saved_prompt_tokens=2,
                    saved_completion_tokens=3,
                ),
            ),
        ],
    )
    def test_savings_metrics_keep_token_mutations_when_cost_conversion_fails(
        self,
        record_savings,
        expected_metrics,
    ):
        metrics = ThriftMetrics()

        with pytest.raises(ValueError):
            record_savings(metrics, 2, 3, estimated_cost_usd="invalid")

        assert metrics == expected_metrics

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("estimated_cost_usd", "expected_cost_usd"),
        [
            (0.0, 0.0),
            (-1.0, 0.0),
            (float("nan"), 0.0),
            (float("inf"), float("inf")),
        ],
    )
    @pytest.mark.parametrize(
        "record_savings",
        [
            _record_coalesced_savings_on_metrics,
            _record_recent_reuse_savings_on_metrics,
        ],
    )
    def test_savings_metrics_preserve_explicit_cost_semantics(
        self,
        record_savings,
        estimated_cost_usd,
        expected_cost_usd,
    ):
        metrics = ThriftMetrics()

        record_savings(
            metrics,
            prompt_tokens=-2,
            completion_tokens=3,
            estimated_cost_usd=estimated_cost_usd,
        )

        assert metrics.saved_prompt_tokens == 0
        assert metrics.saved_completion_tokens == 3
        assert metrics.saved_cost_usd == expected_cost_usd

    @pytest.mark.unit
    def test_request_scope_tracks_local_metrics_without_resetting_global_totals(self):
        reset_thrift_metrics()
        record_compaction_savings(10)

        with thrift_request_scope():
            record_compaction_savings(5)
            record_model_request("anthropic/claude-sonnet-4")
            record_coalesced_savings(
                prompt_tokens=100,
                completion_tokens=20,
                estimated_cost_usd=0.003,
            )
            record_recent_reuse_savings(
                prompt_tokens=40,
                completion_tokens=10,
                estimated_cost_usd=0.002,
            )
            record_prompt_cache_activity(
                cached_prompt_tokens=300,
                cache_write_prompt_tokens=100,
                estimated_saved_cost_usd=0.007,
                model="anthropic/claude-sonnet-4",
            )

            request_metrics = get_request_thrift_metrics_snapshot()

        assert request_metrics["compacted_tokens"] == 5
        assert request_metrics["saved_prompt_tokens"] == 440
        assert request_metrics["saved_completion_tokens"] == 30
        assert request_metrics["saved_cost_usd"] == 0.012
        assert request_metrics["cached_prompt_tokens"] == 300
        assert request_metrics["cache_write_prompt_tokens"] == 100
        assert request_metrics["cache_hit_requests"] == 1
        assert request_metrics["cache_write_requests"] == 1
        assert request_metrics["recent_reuse_requests"] == 1
        assert request_metrics["recent_reuse_prompt_tokens"] == 40
        assert request_metrics["recent_reuse_completion_tokens"] == 10
        assert (
            request_metrics["cache_efficiency_by_provider"]["anthropic"]["observed_requests"] == 1
        )
        assert (
            request_metrics["cache_efficiency_by_provider"]["anthropic"]["cache_hit_requests"] == 1
        )
        assert (
            request_metrics["cache_efficiency_by_provider"]["anthropic"]["saved_cost_usd"] == 0.007
        )
        assert (
            request_metrics["cache_efficiency_by_model"]["anthropic/claude-sonnet-4"][
                "cache_write_requests"
            ]
            == 1
        )
        assert get_request_thrift_metrics_snapshot()["saved_prompt_tokens"] == 0

        global_metrics = get_thrift_metrics_snapshot()
        assert global_metrics["compacted_tokens"] == 15
        assert global_metrics["saved_prompt_tokens"] == 440
        assert global_metrics["saved_completion_tokens"] == 30
        assert global_metrics["saved_cost_usd"] == 0.012
        assert global_metrics["cache_hit_requests"] == 1
        assert global_metrics["cache_write_requests"] == 1
        assert global_metrics["recent_reuse_requests"] == 1
        assert global_metrics["cache_efficiency_by_provider"]["anthropic"]["observed_requests"] == 1

    @pytest.mark.unit
    def test_collector_persists_daily_rollups_and_filters_by_date(self, tmp_path):
        current_time = {"value": datetime(2026, 4, 10, 12, 0, 0)}
        persistence_path = tmp_path / "runtime_thrift_metrics.json"

        collector = ThriftMetricsCollector(
            persistence_path=str(persistence_path),
            now_provider=lambda: current_time["value"],
        )
        collector.record_compaction_savings(10)
        collector.record_coalesced_savings(
            prompt_tokens=100,
            completion_tokens=20,
            estimated_cost_usd=0.003,
        )
        collector.record_model_request("anthropic/claude-sonnet-4")
        collector.record_prompt_cache_activity(
            cached_prompt_tokens=300,
            cache_write_prompt_tokens=100,
            estimated_saved_cost_usd=0.007,
            model="anthropic/claude-sonnet-4",
        )

        current_time["value"] = datetime(2026, 4, 11, 9, 0, 0)
        collector.record_recent_reuse_savings(
            prompt_tokens=25,
            completion_tokens=5,
            estimated_cost_usd=0.001,
        )
        collector.record_model_request("openai/gpt-4o-mini")
        collector.record_prompt_cache_activity(
            cached_prompt_tokens=80,
            cache_write_prompt_tokens=20,
            estimated_saved_cost_usd=0.002,
            model="openai/gpt-4o-mini",
        )

        reloaded = ThriftMetricsCollector(persistence_path=str(persistence_path))

        first_day = reloaded.snapshot_for_dates("2026-04-10", "2026-04-10")
        assert first_day["saved_cost_usd"] == 0.01
        assert first_day["saved_prompt_tokens"] == 400
        assert first_day["compacted_tokens"] == 10
        assert first_day["cache_efficiency_by_provider"]["anthropic"]["cached_prompt_tokens"] == 300
        assert "openai" not in first_day["cache_efficiency_by_provider"]

        second_day = reloaded.snapshot_for_dates("2026-04-11", "2026-04-11")
        assert second_day["saved_cost_usd"] == 0.003
        assert second_day["saved_prompt_tokens"] == 105
        assert second_day["recent_reuse_requests"] == 1
        assert second_day["cache_efficiency_by_provider"]["openai"]["cached_prompt_tokens"] == 80
        assert "anthropic" not in second_day["cache_efficiency_by_provider"]

        aggregate = reloaded.snapshot()
        assert aggregate["saved_cost_usd"] == 0.013
        assert aggregate["saved_prompt_tokens"] == 505

    @pytest.mark.unit
    def test_collector_recovers_from_corrupt_persistence_file(self, tmp_path):
        persistence_path = tmp_path / "runtime_thrift_metrics.json"
        persistence_path.write_text("{ definitely-not-json", encoding="utf-8")

        collector = ThriftMetricsCollector(persistence_path=str(persistence_path))

        assert collector.snapshot()["saved_cost_usd"] == 0.0
        assert collector.snapshot()["saved_prompt_tokens"] == 0

        collector.record_compaction_savings(7)

        reloaded = ThriftMetricsCollector(persistence_path=str(persistence_path))
        assert reloaded.snapshot()["compacted_tokens"] == 7
