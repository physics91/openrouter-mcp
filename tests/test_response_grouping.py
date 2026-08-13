"""Exact ordering regressions for semantic response grouping."""

import math
import random
from collections import Counter
from copy import deepcopy
from unittest.mock import Mock, call

import pytest

import openrouter_mcp.collective_intelligence.semantic_similarity as similarity_module
from openrouter_mcp.collective_intelligence.semantic_similarity import (
    ResponseGrouper,
    SemanticSimilarityCalculator,
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


def test_prepared_grouping_matches_forced_legacy_random_workloads() -> None:
    """Canonical feature reuse must preserve exact grouping and ordering."""

    class TextList(list):
        """Force the legacy path without changing list behavior."""

    rng = random.Random(20260813)
    vocabulary = [
        "renewable",
        "energy",
        "model",
        "evidence",
        "conclusion",
        "AI",
        "ML",
        "한글",
        "café",
        "yes",
        "no",
    ]
    grouper = ResponseGrouper(similarity_threshold=0.72)

    for size in (2, 5, 15, 40):
        for _ in range(25):
            texts = [
                " ".join(rng.choices(vocabulary, k=rng.randrange(1, 12)))
                for _ in range(size)
            ]
            if size > 3 and rng.random() < 0.5:
                texts[-1] = texts[0].upper()

            assert grouper.group_responses(texts) == grouper.group_responses(
                TextList(texts)
            )


@pytest.mark.parametrize(
    "dependency_name",
    [
        "_jaccard_from_token_sets",
        "_cosine_from_tokens",
        "_boost_short_affirmations_from_tokens",
        "_uses_canonical_similarity_pipeline",
    ],
)
def test_prepared_grouping_falls_back_for_rebound_metric_dependencies(
    monkeypatch, dependency_name
) -> None:
    """Rebound canonical helpers must remain observable through the legacy path."""

    def fail_if_called(*args, **kwargs):
        raise RuntimeError(dependency_name)

    monkeypatch.setattr(similarity_module, dependency_name, fail_if_called)

    with pytest.raises(RuntimeError, match=dependency_name):
        ResponseGrouper().group_responses(["alpha response", "beta response"])


@pytest.mark.parametrize("dependency_name", ["SimilarityScore", "_TOKEN_PATTERN"])
def test_prepared_grouping_falls_back_for_rebound_module_dependencies(
    monkeypatch, dependency_name
) -> None:
    """Rebound result/token dependencies must disable prepared grouping."""
    if dependency_name == "SimilarityScore":

        def replacement(*args, **kwargs):
            raise RuntimeError(dependency_name)

    else:
        replacement = Mock()
        replacement.findall.side_effect = RuntimeError(dependency_name)

    monkeypatch.setattr(similarity_module, dependency_name, replacement)

    with pytest.raises(RuntimeError, match=dependency_name):
        ResponseGrouper().group_responses(["alpha response", "beta response"])


def test_prepared_grouping_preserves_exact_calculator_are_similar_shadow() -> None:
    """An exact calculator instance hook must keep the legacy comparison path."""
    calculator = SemanticSimilarityCalculator()
    calculator.are_similar = Mock(return_value=False)
    grouper = ResponseGrouper(calculator=calculator)

    assert grouper.group_responses(["alpha response", "beta response"]) == [
        [0],
        [1],
    ]
    calculator.are_similar.assert_called_once_with(
        "alpha response", "beta response", 0.7
    )


def test_prepared_grouping_preserves_grouper_instance_hook() -> None:
    """Grouper method shadows must disable the prepared feature path."""
    grouper = ResponseGrouper()
    grouper._build_similarity_group = Mock(return_value=[0, 1])

    assert grouper.group_responses(["alpha response", "beta response"]) == [
        [0, 1],
        [0, 1],
    ]
    assert grouper._build_similarity_group.call_count == 2


def test_prepared_grouping_preserves_stateful_calculator_configuration() -> None:
    """Non-primitive calculator settings must retain repeated legacy operations."""

    class StatefulFlag:
        calls = 0

        def __bool__(self):
            type(self).calls += 1
            return False

    calculator = SemanticSimilarityCalculator()
    calculator.case_sensitive = StatefulFlag()

    ResponseGrouper(calculator=calculator).group_responses(
        ["alpha response", "beta response"]
    )

    assert StatefulFlag.calls == 4


def test_prepared_grouping_rejects_subclassed_inputs_and_enforces_caps() -> None:
    """Only bounded builtin containers and strings may use prepared grouping."""

    class TextList(list):
        pass

    class Text(str):
        pass

    grouper = ResponseGrouper()

    assert grouper._can_use_prepared_grouping(["a", "b"])
    assert not grouper._can_use_prepared_grouping(TextList(["a", "b"]))
    assert not grouper._can_use_prepared_grouping([Text("a"), "b"])
    assert grouper._can_use_prepared_grouping(["a"] * 128)
    assert not grouper._can_use_prepared_grouping(["a"] * 129)
    assert grouper._can_use_prepared_grouping(["a" * (256 * 1024), ""])
    assert not grouper._can_use_prepared_grouping(["a" * (256 * 1024 + 1), ""])


def test_prepared_pair_preserves_exact_hybrid_threshold_boundary() -> None:
    """Cached pair arithmetic must match the canonical hybrid bit for bit."""
    grouper = ResponseGrouper()
    calculator = grouper.calculator
    texts = [
        "renewable energy model with evidence",
        "renewable power model with supporting evidence",
    ]
    normalized = [calculator._normalize_text(text) for text in texts]
    hybrid = calculator.calculate_similarity(*texts).hybrid

    for threshold in (
        math.nextafter(hybrid, -math.inf),
        hybrid,
        math.nextafter(hybrid, math.inf),
    ):
        grouper.similarity_threshold = threshold
        assert grouper._prepared_responses_are_similar(normalized, {}, 0, 1) is (
            hybrid >= threshold
        )


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


def test_select_group_representative_reuses_canonical_symmetric_scores() -> None:
    calculator = SemanticSimilarityCalculator()
    grouper = ResponseGrouper(calculator=calculator)
    scores = {
        frozenset(("a", "b")): 0.1,
        frozenset(("a", "c")): 0.2,
        frozenset(("b", "c")): 0.9,
    }
    grouper._calculate_pair_similarity = Mock(
        side_effect=lambda left, right: scores[frozenset((left, right))]
    )

    representative = grouper._select_group_representative(
        ["a", "b", "c"],
        [0, 1, 2],
    )

    assert representative == 2
    assert grouper._calculate_pair_similarity.call_args_list == [
        call("a", "b"),
        call("a", "c"),
        call("b", "c"),
    ]


def test_select_group_representative_preserves_shadowed_asymmetric_calculator() -> None:
    calculator = SemanticSimilarityCalculator()
    scores = {
        ("a", "b"): 0.1,
        ("a", "c"): 0.2,
        ("b", "a"): 0.1,
        ("b", "c"): 0.9,
        ("c", "a"): 0.2,
        ("c", "b"): 0.9,
    }
    calculator.calculate_similarity = Mock(
        side_effect=lambda left, right: SimilarityScore(
            jaccard=0.0,
            levenshtein=0.0,
            cosine=0.0,
            ngram=0.0,
            hybrid=scores[(left, right)],
        )
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
