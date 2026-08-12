"""Exact ordering regressions for semantic response grouping."""

from collections import Counter
from copy import deepcopy
from unittest.mock import Mock, call

import pytest

from openrouter_mcp.collective_intelligence.semantic_similarity import (
    ResponseGrouper,
    SimilarityScore,
)


def test_group_responses_preserves_duplicate_and_transitive_order() -> None:
    calculator = Mock()
    calculator._normalize_text.side_effect = str.lower
    similar_pairs = {("A", "B"), ("B", "C")}
    calculator.are_similar.side_effect = (
        lambda left, right, threshold: (left, right) in similar_pairs
    )
    grouper = ResponseGrouper(similarity_threshold=0.7, calculator=calculator)

    groups = grouper.group_responses(["A", "a", "B", "C", "D"])

    assert groups == [[0, 1, 2, 3], [4]]
    assert calculator.are_similar.call_args_list == [
        call("A", "B", 0.7),
        call("A", "C", 0.7),
        call("B", "C", 0.7),
        call("A", "D", 0.7),
        call("B", "D", 0.7),
        call("C", "D", 0.7),
    ]


def test_select_group_representative_returns_singleton_without_similarity_calls() -> (
    None
):
    calculator = Mock()
    calculator.calculate_similarity.side_effect = AssertionError(
        "singleton should not calculate similarity"
    )
    grouper = ResponseGrouper(calculator=calculator)

    assert grouper._select_group_representative(["only"], [0]) == 0
    calculator.calculate_similarity.assert_not_called()


def test_select_group_representative_uses_highest_average_similarity() -> None:
    calculator = Mock()
    scores = {
        ("a", "b"): 0.1,
        ("a", "c"): 0.2,
        ("b", "a"): 0.1,
        ("b", "c"): 0.9,
        ("c", "a"): 0.2,
        ("c", "b"): 0.9,
    }
    calculator.calculate_similarity.side_effect = lambda left, right: SimilarityScore(
        jaccard=0.0,
        levenshtein=0.0,
        cosine=0.0,
        ngram=0.0,
        hybrid=scores[(left, right)],
    )
    grouper = ResponseGrouper(calculator=calculator)

    representative = grouper._select_group_representative(
        ["a", "b", "c"],
        [0, 1, 2],
    )

    assert representative == 2
    assert Counter(
        tuple(current.args)
        for current in calculator.calculate_similarity.call_args_list
    ) == Counter(scores.keys())


def test_select_group_representative_preserves_zero_tie_and_duplicate_semantics() -> (
    None
):
    calculator = Mock()
    calculator.calculate_similarity.return_value = SimilarityScore(
        jaccard=0.0,
        levenshtein=0.0,
        cosine=0.0,
        ngram=0.0,
        hybrid=0.0,
    )
    grouper = ResponseGrouper(calculator=calculator)

    assert grouper._select_group_representative(["a", "b"], [1, 0]) == 1

    calculator.calculate_similarity.reset_mock()
    assert grouper._select_group_representative(["a", "b"], [1, 1]) == 1
    calculator.calculate_similarity.assert_not_called()


def test_select_group_representative_preserves_empty_group_failure() -> None:
    grouper = ResponseGrouper()

    with pytest.raises(IndexError):
        grouper._select_group_representative(["a"], [])


def test_get_group_representatives_delegates_groups_without_mutating_inputs() -> None:
    grouper = ResponseGrouper()
    texts = ["a", "b", "c"]
    groups = [[0, 2], [1]]
    original_texts = list(texts)
    original_groups = deepcopy(groups)
    grouper._select_group_representative = Mock(side_effect=[2, 1])

    representatives = grouper.get_group_representatives(texts, groups)

    assert representatives == [2, 1]
    assert grouper._select_group_representative.call_args_list == [
        call(texts, groups[0]),
        call(texts, groups[1]),
    ]
    assert texts == original_texts
    assert groups == original_groups
