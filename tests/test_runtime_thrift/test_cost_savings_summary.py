from unittest.mock import MagicMock

import pytest

from src.openrouter_mcp.runtime_thrift import summary as summary_module

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("stats", "thrift_metrics", "expected"),
    [
        (
            {"total_cost": 0.08},
            {"saved_cost_usd": 0.02},
            {
                "saved_cost_usd": 0.02,
                "estimated_cost_without_thrift_usd": 0.1,
                "effective_cost_reduction_pct": 20.0,
            },
        ),
        (
            {"total_cost": 0},
            {"saved_cost_usd": 0},
            {
                "saved_cost_usd": 0.0,
                "estimated_cost_without_thrift_usd": 0.0,
                "effective_cost_reduction_pct": 0.0,
            },
        ),
        (
            {"total_cost": -0.2},
            {"saved_cost_usd": 0.1},
            {
                "saved_cost_usd": 0.1,
                "estimated_cost_without_thrift_usd": -0.1,
                "effective_cost_reduction_pct": 0.0,
            },
        ),
        (
            {"total_cost": "invalid"},
            {"saved_cost_usd": object()},
            {
                "saved_cost_usd": 0.0,
                "estimated_cost_without_thrift_usd": 0.0,
                "effective_cost_reduction_pct": 0.0,
            },
        ),
    ],
)
def test_build_cost_savings_summary_preserves_numeric_policy(
    stats,
    thrift_metrics,
    expected,
):
    assert summary_module._build_cost_savings_summary(stats, thrift_metrics) == expected


class _TrackingDict(dict):
    def __init__(self, label, events, values):
        super().__init__(values)
        self._label = label
        self._events = events

    def get(self, key, default=None):
        self._events.append((self._label, key))
        return super().get(key, default)


def test_build_cost_savings_summary_preserves_mapping_access_order():
    events = []
    stats = _TrackingDict("stats", events, {"total_cost": 0.08})
    thrift_metrics = _TrackingDict(
        "thrift",
        events,
        {"saved_cost_usd": 0.02},
    )

    summary_module._build_cost_savings_summary(stats, thrift_metrics)

    assert events == [
        ("thrift", "saved_cost_usd"),
        ("stats", "total_cost"),
    ]


def test_build_thrift_summary_delegates_costs_before_request_count(monkeypatch):
    events = []
    stats = _TrackingDict("stats", events, {"requests": 2})
    thrift_metrics = _TrackingDict("thrift", events, {})
    cost_summary = {
        "saved_cost_usd": 1.25,
        "estimated_cost_without_thrift_usd": 2.5,
        "effective_cost_reduction_pct": 50.0,
    }

    def build_costs(actual_stats, actual_thrift_metrics):
        events.append("build costs")
        assert actual_stats is stats
        assert actual_thrift_metrics is thrift_metrics
        return cost_summary

    build = MagicMock(side_effect=build_costs)
    monkeypatch.setattr(
        summary_module,
        "_build_cost_savings_summary",
        build,
        raising=False,
    )

    result = summary_module.build_thrift_summary(stats, thrift_metrics)

    build.assert_called_once_with(stats, thrift_metrics)
    assert events[:2] == ["build costs", ("stats", "requests")]
    assert list(result)[:3] == list(cost_summary)
    assert {key: result[key] for key in cost_summary} == cost_summary
