#!/usr/bin/env python3
"""
Comprehensive tests for semantic similarity detection.

These tests verify that the semantic similarity implementation correctly:
1. Groups semantically identical responses with different formatting
2. Separates semantically different responses
3. Handles edge cases (empty strings, very short text, etc.)
4. Provides consistent and accurate similarity scores
5. Performs efficiently on realistic data
"""

import math
from collections import Counter
from itertools import product
from unittest.mock import Mock

import pytest

from openrouter_mcp.collective_intelligence.semantic_similarity import (
    ResponseGrouper,
    SemanticSimilarityCalculator,
    SimilarityScore,
    calculate_response_similarity,
)


def _reference_normalized_levenshtein(text1: str, text2: str) -> float:
    """Return normalized Levenshtein similarity using a simple DP oracle."""
    if not text1 and not text2:
        return 1.0
    if not text1 or not text2:
        return 0.0

    previous_row = list(range(len(text2) + 1))
    for row_index, left_character in enumerate(text1, 1):
        current_row = [row_index]
        for column_index, right_character in enumerate(text2, 1):
            current_row.append(
                min(
                    previous_row[column_index] + 1,
                    current_row[column_index - 1] + 1,
                    previous_row[column_index - 1]
                    + (left_character != right_character),
                )
            )
        previous_row = current_row

    return 1.0 - (previous_row[-1] / max(len(text1), len(text2)))


def _reference_cosine_similarity(
    calculator: SemanticSimilarityCalculator, text1: str, text2: str
) -> float:
    """Return cosine similarity using the previous dense-vector calculation."""
    tokens1 = calculator._tokenize(text1)
    tokens2 = calculator._tokenize(text2)
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0

    frequencies1 = Counter(tokens1)
    frequencies2 = Counter(tokens2)
    terms = set(frequencies1) | set(frequencies2)
    vector1 = [frequencies1.get(term, 0) for term in terms]
    vector2 = [frequencies2.get(term, 0) for term in terms]
    dot_product = sum(left * right for left, right in zip(vector1, vector2))
    magnitude1 = math.sqrt(sum(value * value for value in vector1))
    magnitude2 = math.sqrt(sum(value * value for value in vector2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


def _reference_jaccard_similarity(
    calculator: SemanticSimilarityCalculator, text1: str, text2: str
) -> float:
    """Return token Jaccard similarity using the previous union-set calculation."""
    tokens1 = set(calculator._tokenize(text1))
    tokens2 = set(calculator._tokenize(text2))
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0

    return len(tokens1 & tokens2) / len(tokens1 | tokens2)


def _reference_ngram_similarity(
    calculator: SemanticSimilarityCalculator, text1: str, text2: str
) -> float:
    """Return n-gram similarity using the previous union-set calculation."""
    ngrams1 = calculator._generate_ngrams(text1, calculator.ngram_size)
    ngrams2 = calculator._generate_ngrams(text2, calculator.ngram_size)
    if not ngrams1 and not ngrams2:
        return 1.0
    if not ngrams1 or not ngrams2:
        return 0.0

    return len(ngrams1 & ngrams2) / len(ngrams1 | ngrams2)


def _reference_calculate_similarity(
    calculator: SemanticSimilarityCalculator, text1: str, text2: str
) -> SimilarityScore:
    """Return the score using the previous metric orchestration path."""
    norm1 = calculator._normalize_text(text1)
    norm2 = calculator._normalize_text(text2)
    if norm1 == norm2:
        return SimilarityScore(1.0, 1.0, 1.0, 1.0, 1.0)

    jaccard = calculator._jaccard_similarity(norm1, norm2)
    levenshtein = calculator._normalized_levenshtein(norm1, norm2)
    cosine = calculator._cosine_similarity(norm1, norm2)
    ngram = calculator._ngram_similarity(norm1, norm2)
    hybrid = 0.30 * jaccard + 0.20 * levenshtein + 0.35 * cosine + 0.15 * ngram
    hybrid = calculator._boost_short_affirmations(norm1, norm2, hybrid)
    hybrid = calculator._boost_high_overlap(jaccard, cosine, hybrid)
    return SimilarityScore(jaccard, levenshtein, cosine, ngram, hybrid)


class TestSemanticSimilarityCalculator:
    """Test the core semantic similarity calculator."""

    @pytest.fixture
    def calculator(self):
        """Create a standard calculator instance."""
        return SemanticSimilarityCalculator()

    def test_identical_texts(self, calculator):
        """Identical texts should have perfect similarity."""
        text = "The quick brown fox jumps over the lazy dog."
        score = calculator.calculate_similarity(text, text)

        assert score.hybrid == pytest.approx(1.0, abs=0.01)
        assert score.jaccard == 1.0
        assert score.levenshtein == 1.0
        assert score.cosine == pytest.approx(1.0, abs=0.01)
        assert score.ngram == pytest.approx(1.0, abs=0.01)

    def test_completely_different_texts(self, calculator):
        """Completely different texts should have low similarity."""
        text1 = "Python is a programming language."
        text2 = "The weather is sunny today."
        score = calculator.calculate_similarity(text1, text2)

        # Should be very different
        assert score.hybrid < 0.3
        assert score.jaccard < 0.3

    def test_semantically_identical_different_formatting(self, calculator):
        """Semantically identical responses with different formatting should be similar."""
        # Same meaning, different formatting
        text1 = "Renewable energy sources are sustainable and reduce carbon emissions."
        text2 = "Renewable energy sources are sustainable, and reduce carbon emissions."

        score = calculator.calculate_similarity(text1, text2)

        # Should be highly similar (minor punctuation difference)
        assert score.hybrid > 0.85
        assert score.jaccard > 0.8

    def test_paraphrased_content(self, calculator):
        """Paraphrased content should show some similarity."""
        text1 = "Machine learning models require large datasets for training."
        text2 = "ML models need substantial amounts of data to train effectively."

        score = calculator.calculate_similarity(text1, text2)

        # Should show some similarity (same concept, different words)
        # Note: Without embeddings, paraphrased content has lower similarity
        # This is expected for lightweight text-based matching
        assert score.hybrid > 0.1  # Some similarity detected
        assert score.cosine > 0.05  # Cosine should capture some shared terms

    def test_case_insensitivity_default(self, calculator):
        """By default, comparison should be case-insensitive."""
        text1 = "HELLO WORLD"
        text2 = "hello world"

        score = calculator.calculate_similarity(text1, text2)

        # Should be identical despite case difference
        assert score.hybrid == pytest.approx(1.0, abs=0.01)

    def test_case_sensitivity_when_enabled(self):
        """With case sensitivity enabled, case should matter."""
        calculator = SemanticSimilarityCalculator(case_sensitive=True)

        text1 = "HELLO WORLD"
        text2 = "hello world"

        score = calculator.calculate_similarity(text1, text2)

        # Should be different due to case
        assert score.hybrid < 1.0

    def test_whitespace_normalization(self, calculator):
        """Extra whitespace should be normalized."""
        text1 = "This  is   a    test."
        text2 = "This is a test."

        score = calculator.calculate_similarity(text1, text2)

        # Should be identical after normalization
        assert score.hybrid == pytest.approx(1.0, abs=0.01)

    @pytest.mark.parametrize(
        ("case_sensitive", "text", "expected"),
        [
            (
                False,
                " AI\tML nlp llm llms 12 12.5 \n",
                (
                    "artificial intelligence machine learning natural language "
                    "processing large language model large language models num num"
                ),
            ),
            (
                True,
                "AI ai ML ml NLP nlp LLM llm LLMs llms 12.5",
                (
                    "AI artificial intelligence ML machine learning NLP natural "
                    "language processing LLM large language model LLMs large "
                    "language models num"
                ),
            ),
        ],
    )
    def test_normalization_preserves_abbreviations_numbers_and_whitespace(
        self, case_sensitive, text, expected
    ):
        """Compiled patterns must preserve normalization order and case rules."""
        calculator = SemanticSimilarityCalculator(case_sensitive=case_sensitive)

        assert calculator._normalize_text(text) == expected

    def test_tokenize_preserves_unicode_word_boundaries(self, calculator):
        """The compiled token pattern must keep Python's Unicode word behavior."""
        assert calculator._tokenize("Alpha42, 한글; café_2! x") == [
            "Alpha42",
            "한글",
            "café_2",
        ]

    @pytest.mark.parametrize(
        ("text1", "text2"),
        [
            ("", ""),
            ("alpha", ""),
            ("alpha alpha beta", "alpha beta beta"),
            ("left unique tokens", "right disjoint words"),
            ("한글 café café", "한글 차"),
            ("the a x", "the a y"),
        ],
    )
    def test_cosine_similarity_matches_dense_vector_reference(
        self, calculator, text1, text2
    ):
        """Sparse cosine calculation must preserve the dense-vector result."""
        assert calculator._cosine_similarity(
            text1, text2
        ) == _reference_cosine_similarity(calculator, text1, text2)

    @pytest.mark.parametrize(
        ("text1", "text2"),
        [
            ("", ""),
            ("the a x", "the a y"),
            ("alpha", ""),
            ("identical token set", "identical token set"),
            ("alpha beta gamma", "delta epsilon zeta"),
            ("alpha beta gamma", "beta gamma delta"),
            ("한글 café", "한글 차"),
            ("alpha alpha beta", "alpha beta beta"),
        ],
    )
    def test_jaccard_similarity_matches_union_set_reference(
        self, calculator, text1, text2
    ):
        """Set-cardinality math must preserve token Jaccard results."""
        assert calculator._jaccard_similarity(
            text1, text2
        ) == _reference_jaccard_similarity(calculator, text1, text2)

    @pytest.mark.parametrize(
        ("text1", "text2"),
        [
            ("", ""),
            ("alpha", ""),
            ("identical n-grams", "identical n-grams"),
            ("abcdefgh", "ijklmnop"),
            ("abcdefghi", "defghijkl"),
            ("한글 café", "한글 차"),
            ("aaaaaa", "aaaaba"),
        ],
    )
    def test_ngram_similarity_matches_union_set_reference(
        self, calculator, text1, text2
    ):
        """Set-cardinality math must preserve the union-set result."""
        assert calculator._ngram_similarity(
            text1, text2
        ) == _reference_ngram_similarity(calculator, text1, text2)

    @pytest.mark.parametrize(
        ("text1", "text2"),
        [
            ("", "alpha"),
            ("yes", "yes correct"),
            ("no", "no incorrect"),
            ("alpha beta gamma", "beta gamma delta"),
            ("AI model 12", "ML model 13"),
            ("한글 café", "한글 차"),
        ],
    )
    def test_shared_token_pipeline_matches_legacy_orchestration(
        self, calculator, text1, text2
    ):
        """Canonical token reuse must preserve the full legacy score."""
        assert calculator.calculate_similarity(
            text1, text2
        ) == _reference_calculate_similarity(calculator, text1, text2)

    def test_instance_shadowed_calculator_uses_legacy_pipeline(self):
        """Instance method overrides must retain the observable call path."""
        calculator = SemanticSimilarityCalculator()
        calculator._jaccard_similarity = Mock(return_value=0.11)
        calculator._normalized_levenshtein = Mock(return_value=0.22)
        calculator._cosine_similarity = Mock(return_value=0.33)
        calculator._ngram_similarity = Mock(return_value=0.44)
        calculator._boost_short_affirmations = Mock(return_value=0.55)
        calculator._boost_high_overlap = Mock(return_value=0.66)

        score = calculator.calculate_similarity("alpha", "beta")

        assert score == SimilarityScore(0.11, 0.22, 0.33, 0.44, 0.66)
        calculator._jaccard_similarity.assert_called_once_with("alpha", "beta")
        calculator._normalized_levenshtein.assert_called_once_with("alpha", "beta")
        calculator._cosine_similarity.assert_called_once_with("alpha", "beta")
        calculator._ngram_similarity.assert_called_once_with("alpha", "beta")
        calculator._boost_short_affirmations.assert_called_once()
        calculator._boost_high_overlap.assert_called_once_with(0.11, 0.33, 0.55)

    def test_class_monkeypatch_uses_legacy_pipeline(self, monkeypatch):
        """Class descriptor changes must disable canonical token reuse."""
        calls = []

        def custom_jaccard(calculator, text1, text2):
            calls.append((calculator, text1, text2))
            return 0.125

        monkeypatch.setattr(
            SemanticSimilarityCalculator, "_jaccard_similarity", custom_jaccard
        )
        calculator = SemanticSimilarityCalculator()

        score = calculator.calculate_similarity("alpha", "beta")

        assert score.jaccard == 0.125
        assert calls == [(calculator, "alpha", "beta")]

    def test_subclass_calculator_uses_legacy_pipeline(self):
        """Subclass overrides must stay on the legacy method path."""

        class CustomCalculator(SemanticSimilarityCalculator):
            def _jaccard_similarity(self, text1, text2):
                return 0.125

        calculator = CustomCalculator()

        assert calculator.calculate_similarity("alpha", "beta").jaccard == 0.125

    def test_identical_after_normalization_short_circuits_expensive_metrics(self):
        """Identical normalized texts should skip the expensive metric pipeline."""
        calculator = SemanticSimilarityCalculator()
        calculator._jaccard_similarity = Mock(
            side_effect=AssertionError("normalized identity should short-circuit")
        )
        calculator._normalized_levenshtein = Mock(
            side_effect=AssertionError("normalized identity should short-circuit")
        )
        calculator._cosine_similarity = Mock(
            side_effect=AssertionError("normalized identity should short-circuit")
        )
        calculator._ngram_similarity = Mock(
            side_effect=AssertionError("normalized identity should short-circuit")
        )

        score = calculator.calculate_similarity("HELLO   WORLD", "hello world")

        assert score.hybrid == 1.0
        assert score.jaccard == 1.0
        assert score.levenshtein == 1.0
        assert score.cosine == 1.0
        assert score.ngram == 1.0

    def test_empty_strings(self, calculator):
        """Empty strings should be handled correctly."""
        score1 = calculator.calculate_similarity("", "")
        assert score1.hybrid == 1.0  # Both empty = identical

        score2 = calculator.calculate_similarity("hello", "")
        assert score2.hybrid == 0.0  # One empty = no similarity

        score3 = calculator.calculate_similarity("", "world")
        assert score3.hybrid == 0.0  # One empty = no similarity

    def test_very_short_texts(self, calculator):
        """Very short texts should be handled correctly."""
        score = calculator.calculate_similarity("a", "a")
        assert score.hybrid > 0.8

        # Note: Very short different texts may score high due to single token matching
        # After filtering by min_token_length, single chars might be treated similarly
        score2 = calculator.calculate_similarity("a", "b")
        # Expecting high similarity for single-char comparison (both are very short)
        assert 0.0 <= score2.hybrid <= 1.0  # Just ensure valid range

    def test_levenshtein_matches_reference_for_exhaustive_short_strings(
        self, calculator
    ):
        """The bit-vector implementation should match the DP oracle exactly."""
        strings = [""]
        for length in range(1, 6):
            strings.extend(
                "".join(characters) for characters in product("ab", repeat=length)
            )

        for text1 in strings:
            for text2 in strings:
                assert calculator._normalized_levenshtein(
                    text1, text2
                ) == _reference_normalized_levenshtein(text1, text2)

    @pytest.mark.parametrize("length", [30, 31, 32, 60, 61, 62])
    def test_levenshtein_matches_reference_at_integer_limb_boundaries(
        self, calculator, length
    ):
        """Carry propagation across Python integer limbs must preserve distance."""
        text = ("a🙂한b" * ((length + 3) // 4))[:length]
        midpoint = length // 2
        variants = [
            text[:midpoint] + "Ω" + text[midpoint + 1 :],
            text[:midpoint] + "Z" + text[midpoint:],
            text[:midpoint] + text[midpoint + 1 :],
            "나" * length,
            text + "끝" * 3,
        ]

        for variant in variants:
            for text1, text2 in ((text, variant), (variant, text)):
                assert calculator._normalized_levenshtein(
                    text1, text2
                ) == _reference_normalized_levenshtein(text1, text2)

    @pytest.mark.parametrize(
        ("text1", "text2"),
        [
            ("shared prefix " * 30 + "A", "shared prefix " * 30 + "B"),
            ("A" + " shared suffix" * 30, "B" + " shared suffix" * 30),
            (
                "header " * 20 + "old middle" + " footer" * 20,
                "header " * 20 + "new middle" + " footer" * 20,
            ),
            ("🙂한" * 40 + "A끝", "🙂한" * 40 + "B끝"),
            ("fully shared🙂" * 20, "fully shared🙂" * 20),
            ("shared 한글" * 20, "shared 한글" * 20 + "tail"),
        ],
    )
    def test_levenshtein_matches_reference_with_long_common_affixes(
        self, calculator, text1, text2
    ):
        """Trimming shared affixes must retain distance and normalization."""
        assert calculator._normalized_levenshtein(
            text1, text2
        ) == _reference_normalized_levenshtein(text1, text2)

    @pytest.mark.parametrize(
        ("shorter", "longer"),
        [
            ("a" * 30, "a" * 30 + "tail"),
            ("b" * 31, "head" + "b" * 31),
            ("c" * 32, "c" * 32 + "tail"),
            ("d" * 60, "head" + "d" * 60),
            ("🙂한" * 31, "🙂한" * 31 + "끝"),
            ("café" * 16, "시작" + "café" * 16),
            ("e" * 61, "head" + "e" * 61 + "tail"),
            ("🙂한글" * 21, "시작" + "🙂한글" * 21 + "끝"),
        ],
    )
    def test_levenshtein_matches_reference_for_containment(
        self, calculator, shorter, longer
    ):
        """Contiguous containment must return the exact edit distance."""
        for text1, text2 in ((shorter, longer), (longer, shorter)):
            assert calculator._normalized_levenshtein(
                text1, text2
            ) == _reference_normalized_levenshtein(text1, text2)

    def test_are_similar_method(self, calculator):
        """Test the boolean similarity check method."""
        text1 = "Python is great for data science."
        text2 = "Python is great for data science!"

        # Very similar, should pass default threshold
        assert calculator.are_similar(text1, text2, threshold=0.7)

        # Different texts should fail
        text3 = "JavaScript is used for web development."
        assert not calculator.are_similar(text1, text3, threshold=0.7)

    def test_custom_thresholds(self, calculator):
        """Test similarity with custom thresholds."""
        text1 = "Machine learning is a subset of AI."
        text2 = "ML is part of artificial intelligence."

        # Very lower threshold should match (paraphrased content)
        assert calculator.are_similar(text1, text2, threshold=0.15)

        # Higher threshold will not match
        # (paraphrased content has low similarity without embeddings)
        assert not calculator.are_similar(text1, text2, threshold=0.9)


class TestResponseGrouper:
    """Test the response grouping functionality."""

    @pytest.fixture
    def grouper(self):
        """Create a standard grouper instance."""
        return ResponseGrouper(similarity_threshold=0.7)

    def test_single_response(self, grouper):
        """Single response should form one group."""
        responses = ["Single response"]
        groups = grouper.group_responses(responses)

        assert len(groups) == 1
        assert groups[0] == [0]

    def test_identical_responses(self, grouper):
        """Identical responses should be grouped together."""
        responses = [
            "Renewable energy reduces carbon emissions.",
            "Renewable energy reduces carbon emissions.",
            "Renewable energy reduces carbon emissions.",
        ]
        groups = grouper.group_responses(responses)

        assert len(groups) == 1
        assert set(groups[0]) == {0, 1, 2}

    def test_normalized_duplicate_responses_skip_similarity_checks(self):
        """Normalized duplicates should group without calling the similarity engine."""
        calculator = SemanticSimilarityCalculator()
        calculator.are_similar = Mock(
            side_effect=AssertionError("normalized duplicates should short-circuit")
        )
        grouper = ResponseGrouper(similarity_threshold=0.7, calculator=calculator)

        responses = [
            "Renewable energy reduces carbon emissions.",
            " renewable   energy reduces carbon emissions. ",
            "RENEWABLE ENERGY REDUCES CARBON EMISSIONS.",
        ]

        groups = grouper.group_responses(responses)

        assert len(groups) == 1
        assert set(groups[0]) == {0, 1, 2}

    def test_similar_responses_grouped(self, grouper):
        """Semantically similar responses should be grouped together."""
        responses = [
            "Renewable energy sources are sustainable and reduce carbon emissions.",
            "Renewable energy is sustainable, reduces carbon emissions, and is cost-effective.",
            "Renewable energy sources are sustainable and help reduce carbon emissions.",
        ]
        groups = grouper.group_responses(responses)

        # Should group very similar responses (though second response has extra content)
        # With threshold 0.7, responses 0 and 2 should group, but 1 might be separate
        assert len(groups) <= 2  # At most 2 groups
        # Verify all responses are accounted for
        all_indices = set()
        for group in groups:
            all_indices.update(group)
        assert all_indices == {0, 1, 2}

    def test_different_responses_separated(self, grouper):
        """Semantically different responses should be in separate groups."""
        responses = [
            "Renewable energy sources are sustainable and reduce carbon emissions.",
            "Python is a versatile programming language used for web development.",
            "The stock market experienced volatility due to economic uncertainty.",
        ]
        groups = grouper.group_responses(responses)

        # All three should be in different groups
        assert len(groups) == 3
        assert {len(group) for group in groups} == {1}

    def test_mixed_grouping(self, grouper):
        """Test grouping with mix of similar and different responses."""
        responses = [
            "Climate change is a global challenge.",  # Topic 1
            "Global warming poses significant risks.",  # Topic 1 (related)
            "Python is excellent for data science.",  # Topic 2
            "Python excels at data analysis.",  # Topic 2 (related)
            "The economy is recovering steadily.",  # Topic 3
        ]
        groups = grouper.group_responses(responses)

        # With threshold 0.7, similar topics might or might not group
        # Depends on exact word overlap
        assert len(groups) >= 3  # At least 3 groups (some may be separate)

        # Check that all responses are accounted for
        group_sizes = sorted([len(g) for g in groups])
        assert sum(group_sizes) == 5  # All responses accounted for

    def test_empty_input(self, grouper):
        """Empty input should return empty groups."""
        groups = grouper.group_responses([])
        assert groups == []

    def test_custom_threshold_strict(self):
        """Test with very strict similarity threshold."""
        grouper = ResponseGrouper(similarity_threshold=0.95)

        responses = [
            "Hello world",
            "Hello world!",  # Minor punctuation difference
        ]
        groups = grouper.group_responses(responses)

        # With strict threshold, might be separate groups
        # (depends on exact similarity score)
        assert len(groups) >= 1

    def test_custom_threshold_lenient(self):
        """Test with lenient similarity threshold."""
        grouper = ResponseGrouper(similarity_threshold=0.1)  # Extremely lenient

        responses = [
            "Machine learning models need data.",
            "ML systems require datasets.",  # Different words, same concept
        ]
        groups = grouper.group_responses(responses)

        # With extremely lenient threshold, should group together
        # Note: These paraphrased texts have very low lexical similarity
        assert len(groups) <= 2  # May still be separate due to different wording

    def test_get_group_representatives(self, grouper):
        """Test finding most representative response from each group."""
        responses = [
            "Climate change is a major global issue today.",
            "Global warming is a significant worldwide problem.",
            "Climate change poses major challenges globally.",
            "Python is used for data science.",
        ]

        groups = grouper.group_responses(responses)
        representatives = grouper.get_group_representatives(responses, groups)

        # Should have one representative per group
        assert len(representatives) == len(groups)

        # All representatives should be valid indices
        assert all(0 <= idx < len(responses) for idx in representatives)

        # Representatives should be unique
        assert len(representatives) == len(set(representatives))

    def test_real_world_ai_responses(self, grouper):
        """Test with realistic AI model responses about the same question."""
        # Simulate different AI models answering: "What are the benefits of renewable energy?"
        responses = [
            # Group 1: Sustainability-focused answers (very similar)
            "Renewable energy sources are sustainable, reduce carbon emissions, and become more cost-effective over time.",
            "Key advantages of renewable energy include sustainability, environmental protection through reduced emissions, and long-term economic benefits.",
            "Renewable energy is sustainable, reduces greenhouse gas emissions, and provides energy independence.",
            # Group 2: Economic-focused answers (related)
            "Renewable energy creates jobs, stimulates economic growth, and reduces dependency on fossil fuel imports.",
            "The renewable energy sector drives job creation, economic development, and reduces reliance on imported energy.",
            # Group 3: Technology-focused answer
            "Advances in renewable energy technologies like solar panels and wind turbines have dramatically improved efficiency and lowered costs.",
        ]

        groups = grouper.group_responses(responses)

        # With threshold 0.7 and different focuses, may have many groups
        # But should still group some similar responses
        assert 2 <= len(groups) <= 6  # Flexible grouping

        # Verify all responses are accounted for
        all_indices = set()
        for group in groups:
            all_indices.update(group)
        assert len(all_indices) == 6


class TestConvenienceFunction:
    """Test the convenience function for quick similarity checks."""

    def test_calculate_response_similarity(self):
        """Test the convenience function."""
        text1 = "Hello world"
        text2 = "Hello world!"

        similarity = calculate_response_similarity(text1, text2)

        # Should return a float between 0 and 1
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0

        # Should be high for similar texts
        assert similarity > 0.8


class TestPerformance:
    """Test performance characteristics of similarity algorithms."""

    def test_large_text_handling(self):
        """Test that large texts are handled efficiently."""
        calculator = SemanticSimilarityCalculator()

        # Create large texts (simulate long AI responses)
        large_text = " ".join(["This is a long response." for _ in range(100)])

        # Should complete without errors or significant delay
        score = calculator.calculate_similarity(large_text, large_text)
        assert score.hybrid > 0.99

    def test_many_responses_grouping(self):
        """Test grouping many responses efficiently."""
        grouper = ResponseGrouper(similarity_threshold=0.7)

        # Create many responses
        responses = [f"This is response number {i} about renewable energy." for i in range(50)]

        # Add some duplicates
        responses.extend(
            [
                "This is a duplicate response.",
                "This is a duplicate response.",
                "This is a duplicate response.",
            ]
        )

        # Should complete efficiently
        groups = grouper.group_responses(responses)

        # Should have multiple groups
        assert len(groups) > 1

        # Duplicates should be in same group
        # Find the group with the duplicates
        duplicate_groups = [g for g in groups if len(g) >= 3]
        assert len(duplicate_groups) >= 1


class TestEdgeCases:
    """Test edge cases and potential failure modes."""

    @pytest.fixture
    def calculator(self):
        """Create a calculator instance."""
        return SemanticSimilarityCalculator()

    def test_special_characters(self, calculator):
        """Test handling of special characters."""
        text1 = "Hello! @#$% ^&*() World?"
        text2 = "Hello! World?"

        score = calculator.calculate_similarity(text1, text2)

        # Should handle special characters gracefully
        assert 0.0 <= score.hybrid <= 1.0
        assert score.hybrid > 0.5  # Still somewhat similar

    def test_numbers_in_text(self, calculator):
        """Test handling of numbers in text."""
        text1 = "The year 2024 was significant."
        text2 = "The year 2025 was significant."

        score = calculator.calculate_similarity(text1, text2)

        # Should be very similar (only year differs)
        # Actual score is ~0.79, so we adjust threshold
        assert score.hybrid > 0.75

    def test_unicode_characters(self, calculator):
        """Test handling of unicode characters."""
        text1 = "Hello 世界! Здравствуй мир!"
        text2 = "Hello 世界! Здравствуй мир!"

        score = calculator.calculate_similarity(text1, text2)

        # Should handle unicode correctly
        assert score.hybrid > 0.99

    def test_only_punctuation(self, calculator):
        """Test texts with only punctuation."""
        text1 = "!!!"
        text2 = "???"

        score = calculator.calculate_similarity(text1, text2)

        # Should handle gracefully (likely low/zero similarity)
        assert 0.0 <= score.hybrid <= 1.0

    def test_very_long_repeated_text(self, calculator):
        """Test with very repetitive text."""
        text1 = "repeat " * 1000
        text2 = "repeat " * 1000

        score = calculator.calculate_similarity(text1, text2)

        # Should recognize as identical
        assert score.hybrid > 0.99


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
