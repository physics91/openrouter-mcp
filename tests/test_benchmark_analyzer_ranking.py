from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest

from src.openrouter_mcp.handlers import benchmark_analyzer as analyzer_module
from src.openrouter_mcp.handlers.benchmark_analyzer import (
    ModelPerformanceAnalyzer,
    _rank_models_by,
)

pytestmark = pytest.mark.unit


def test_rank_models_by_scores_only_successes_and_preserves_identity():
    higher = SimpleNamespace(success=True, metrics=object())
    failed = SimpleNamespace(success=False)
    missing_metrics = SimpleNamespace(success=True, metrics=None)
    lower = SimpleNamespace(success=True, metrics=object())
    results = [lower, failed, higher, missing_metrics]
    scorer = Mock(side_effect=[0.3, 0.8])

    ranked = _rank_models_by(results, scorer)

    assert ranked == [
        (higher, 0.8),
        (lower, 0.3),
        (failed, 0.0),
        (missing_metrics, 0.0),
    ]
    assert ranked[0][0] is higher
    assert ranked[1][0] is lower
    assert ranked[2][0] is failed
    assert ranked[3][0] is missing_metrics
    assert scorer.call_args_list == [call(lower), call(higher)]
    assert results == [lower, failed, higher, missing_metrics]


def test_rank_models_by_keeps_input_order_for_tied_scores():
    first = SimpleNamespace(success=True, metrics=object())
    second = SimpleNamespace(success=True, metrics=object())
    scorer = Mock(return_value=0.5)

    ranked = _rank_models_by([first, second], scorer)

    assert ranked == [(first, 0.5), (second, 0.5)]
    assert ranked[0][0] is first
    assert ranked[1][0] is second


def test_rank_models_by_handles_empty_input_without_scoring():
    scorer = Mock()

    assert _rank_models_by([], scorer) == []

    scorer.assert_not_called()


def test_rank_models_delegates_with_existing_fixed_formula():
    results = [object()]
    metrics = SimpleNamespace(
        speed_score=0.8,
        cost_score=0.6,
        quality_score=0.9,
        throughput_score=0.4,
    )
    score_target = SimpleNamespace(metrics=metrics)
    sentinel = [(object(), 123.0)]

    def rank(received_results, score_result):
        assert received_results is results
        assert score_result(score_target) == pytest.approx(0.725)
        return sentinel

    with patch.object(analyzer_module, "_rank_models_by", side_effect=rank) as rank_by:
        ranked = ModelPerformanceAnalyzer().rank_models(results)

    assert ranked is sentinel
    rank_by.assert_called_once()


def test_rank_models_with_weights_delegates_with_sparse_defaults():
    results = [object()]
    weights = {"quality": 2.0}
    metrics = SimpleNamespace(
        speed_score=0.8,
        cost_score=0.6,
        quality_score=0.9,
        throughput_score=0.4,
    )
    score_target = SimpleNamespace(metrics=metrics)
    sentinel = [(object(), 456.0)]

    def rank(received_results, score_result):
        assert received_results is results
        assert score_result(score_target) == pytest.approx(1.8)
        return sentinel

    with patch.object(analyzer_module, "_rank_models_by", side_effect=rank) as rank_by:
        ranked = ModelPerformanceAnalyzer().rank_models_with_weights(results, weights)

    assert ranked is sentinel
    rank_by.assert_called_once()


def test_rank_models_by_propagates_scorer_failure_before_later_results():
    first = SimpleNamespace(success=True, metrics=object())
    second = SimpleNamespace(success=True, metrics=object())
    scorer = Mock(side_effect=RuntimeError("score failed"))

    with pytest.raises(RuntimeError, match="score failed"):
        _rank_models_by([first, second], scorer)

    scorer.assert_called_once_with(first)
