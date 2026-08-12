"""Exact ordering regressions for semantic response grouping."""

from unittest.mock import Mock, call

from openrouter_mcp.collective_intelligence.semantic_similarity import ResponseGrouper


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
