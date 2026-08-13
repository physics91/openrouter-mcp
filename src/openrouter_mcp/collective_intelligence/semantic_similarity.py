"""
Semantic Similarity Utilities for Response Grouping

This module provides lightweight, efficient algorithms for measuring semantic similarity
between model responses, enabling better consensus building without heavy dependencies
on machine learning models or embeddings.

Algorithms:
1. Token-based Jaccard Similarity (set overlap)
2. Normalized Levenshtein Distance (edit distance)
3. TF-IDF Cosine Similarity (lightweight vectorization)
4. N-gram Similarity (character and word level)
5. Hybrid scoring combining multiple metrics
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from ..utils.text import EXTENDED_ENGLISH_STOPWORDS

_ABBREVIATIONS = {
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "llm": "large language model",
    "llms": "large language models",
}
_ABBREVIATION_PATTERN = re.compile(r"\b(?:ml|ai|nlp|llms|llm)\b")
_NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_TOKEN_PATTERN = re.compile(r"\b\w+\b")


def _expand_abbreviation(match: re.Match[str]) -> str:
    """Expand one abbreviation matched by ``_ABBREVIATION_PATTERN``."""
    return _ABBREVIATIONS[match.group(0)]


@dataclass
class SimilarityScore:
    """Container for similarity metrics."""

    jaccard: float
    levenshtein: float
    cosine: float
    ngram: float
    hybrid: float


class SemanticSimilarityCalculator:
    """
    Lightweight semantic similarity calculator that combines multiple text distance
    and similarity metrics without requiring external ML models or embeddings.
    """

    def __init__(
        self,
        min_token_length: int = 2,
        ngram_size: int = 3,
        case_sensitive: bool = False,
    ):
        """
        Initialize the similarity calculator.

        Args:
            min_token_length: Minimum token length to consider (filters noise)
            ngram_size: Size of character n-grams for similarity
            case_sensitive: Whether to consider case in comparisons
        """
        self.min_token_length = min_token_length
        self.ngram_size = ngram_size
        self.case_sensitive = case_sensitive

    def calculate_similarity(self, text1: str, text2: str) -> SimilarityScore:
        """
        Calculate comprehensive similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            SimilarityScore with multiple metrics and hybrid score
        """
        # Normalize texts
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)

        if norm1 == norm2:
            return SimilarityScore(
                jaccard=1.0,
                levenshtein=1.0,
                cosine=1.0,
                ngram=1.0,
                hybrid=1.0,
            )

        # Calculate individual metrics
        jaccard = self._jaccard_similarity(norm1, norm2)
        levenshtein = self._normalized_levenshtein(norm1, norm2)
        cosine = self._cosine_similarity(norm1, norm2)
        ngram = self._ngram_similarity(norm1, norm2)

        # Hybrid score: weighted combination of metrics
        # Weights tuned for semantic similarity of AI responses
        hybrid = (
            0.30 * jaccard  # Token overlap is important
            + 0.20 * levenshtein  # Edit distance helps with paraphrasing
            + 0.35 * cosine  # TF-IDF captures semantic content
            + 0.15 * ngram  # Character n-grams catch similar phrasing
        )

        hybrid = self._boost_short_affirmations(norm1, norm2, hybrid)
        hybrid = self._boost_high_overlap(jaccard, cosine, hybrid)

        return SimilarityScore(
            jaccard=jaccard,
            levenshtein=levenshtein,
            cosine=cosine,
            ngram=ngram,
            hybrid=hybrid,
        )

    def _boost_short_affirmations(self, text1: str, text2: str, score: float) -> float:
        """Boost similarity for short affirmations or subset responses."""
        tokens1 = self._tokenize(text1)
        tokens2 = self._tokenize(text2)

        if not tokens1 or not tokens2:
            return score

        set1 = set(tokens1)
        set2 = set(tokens2)
        short_limit = 3

        if len(tokens1) <= short_limit or len(tokens2) <= short_limit:
            if set1.issubset(set2) or set2.issubset(set1):
                return max(score, 0.85)

            affirmatives = {
                "yes",
                "yeah",
                "yep",
                "correct",
                "true",
                "affirmative",
                "agree",
            }
            negatives = {"no", "nope", "incorrect", "false", "negative"}

            if set1 & affirmatives and set2 & affirmatives:
                return max(score, 0.8)
            if set1 & negatives and set2 & negatives:
                return max(score, 0.8)

        return score

    def _boost_high_overlap(self, jaccard: float, cosine: float, score: float) -> float:
        """Boost similarity when lexical overlap is already strong."""
        if jaccard >= 0.6 and cosine >= 0.6:
            return max(score, 0.72)
        if jaccard >= 0.5 and cosine >= 0.7:
            return max(score, 0.7)
        return score

    def are_similar(self, text1: str, text2: str, threshold: float = 0.7) -> bool:
        """
        Determine if two texts are semantically similar.

        Args:
            text1: First text
            text2: Second text
            threshold: Similarity threshold (0-1), default 0.7

        Returns:
            True if hybrid similarity >= threshold
        """
        score = self.calculate_similarity(text1, text2)
        return score.hybrid >= threshold

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not self.case_sensitive:
            text = text.lower()

        # Expand common abbreviations to improve similarity
        text = _ABBREVIATION_PATTERN.sub(_expand_abbreviation, text)

        # Normalize numeric values to reduce penalties for numeric variations
        text = _NUMBER_PATTERN.sub("num", text)

        # Remove extra whitespace
        text = _WHITESPACE_PATTERN.sub(" ", text.strip())

        return text

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text into words, filtering by minimum length.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        # Split on word boundaries and punctuation
        tokens = _TOKEN_PATTERN.findall(text)

        # Filter by minimum length
        return [
            token
            for token in tokens
            if len(token) >= self.min_token_length
            and token not in EXTENDED_ENGLISH_STOPWORDS
        ]

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate Jaccard similarity (set overlap) between tokenized texts.

        Jaccard = |A ∩ B| / |A ∪ B|

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score between 0 and 1
        """
        tokens1 = set(self._tokenize(text1))
        tokens2 = set(self._tokenize(text2))

        if not tokens1 and not tokens2:
            return 1.0  # Both empty = identical

        if not tokens1 or not tokens2:
            return 0.0  # One empty = no similarity

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        return len(intersection) / len(union)

    def _normalized_levenshtein(self, text1: str, text2: str) -> float:
        """
        Calculate normalized Levenshtein distance (edit distance).

        Normalized to 0-1 range where 1 = identical, 0 = completely different.
        Uses Myers' bit-vector algorithm for exact unit-cost edit distance.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Normalized similarity score between 0 and 1
        """
        len1, len2 = len(text1), len(text2)

        if len1 == 0 and len2 == 0:
            return 1.0

        if len1 == 0 or len2 == 0:
            return 0.0

        max_length = max(len1, len2)

        shared_length = min(len1, len2)
        prefix_length = 0
        while (
            prefix_length < shared_length
            and text1[prefix_length] == text2[prefix_length]
        ):
            prefix_length += 1
        if prefix_length:
            text1 = text1[prefix_length:]
            text2 = text2[prefix_length:]

        shared_length = min(len(text1), len(text2))
        suffix_length = 0
        while (
            suffix_length < shared_length
            and text1[-suffix_length - 1] == text2[-suffix_length - 1]
        ):
            suffix_length += 1
        if suffix_length:
            text1 = text1[:-suffix_length]
            text2 = text2[:-suffix_length]

        if not text1 or not text2:
            distance = max(len(text1), len(text2))
            return 1.0 - (distance / max_length)

        # Myers' bit-vector recurrence computes the same unit-cost edit distance
        # while moving the character loop into Python's optimized integer operations.
        # Use the shorter text as the bit pattern to minimize the integer width.
        if len(text1) < len(text2):
            text1, text2 = text2, text1

        pattern_length = len(text2)
        character_masks: dict[str, int] = {}
        for index, character in enumerate(text2):
            character_masks[character] = character_masks.get(character, 0) | (
                1 << index
            )

        pattern_mask = (1 << pattern_length) - 1
        highest_bit = 1 << (pattern_length - 1)
        positive = pattern_mask
        negative = 0
        distance = pattern_length

        for character in text1:
            matches = character_masks.get(character, 0)
            combined = matches | negative
            horizontal = (((combined & positive) + positive) ^ positive) | combined
            positive_gap = negative | ~(horizontal | positive)
            negative_gap = positive & horizontal

            if positive_gap & highest_bit:
                distance += 1
            elif negative_gap & highest_bit:
                distance -= 1

            positive_gap = ((positive_gap << 1) | 1) & pattern_mask
            negative_gap = (negative_gap << 1) & pattern_mask
            positive = (negative_gap | ~(horizontal | positive_gap)) & pattern_mask
            negative = positive_gap & horizontal

        return 1.0 - (distance / max_length)

    def _cosine_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate cosine similarity between texts using term frequency vectors.

        Uses simple term frequency vectors to calculate cosine similarity,
        which is more appropriate for comparing two documents directly.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Cosine similarity between 0 and 1
        """
        tokens1 = self._tokenize(text1)
        tokens2 = self._tokenize(text2)

        if not tokens1 and not tokens2:
            return 1.0

        if not tokens1 or not tokens2:
            return 0.0

        # Calculate term frequencies
        tf1 = Counter(tokens1)
        tf2 = Counter(tokens2)

        # Get all unique terms
        all_terms = set(tf1.keys()) | set(tf2.keys())

        # Create frequency vectors
        vector1 = [tf1.get(term, 0) for term in all_terms]
        vector2 = [tf2.get(term, 0) for term in all_terms]

        # Calculate cosine similarity
        dot_product = sum(v1 * v2 for v1, v2 in zip(vector1, vector2))

        magnitude1 = math.sqrt(sum(v * v for v in vector1))
        magnitude2 = math.sqrt(sum(v * v for v in vector2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def _generate_ngrams(self, text: str, n: int) -> set[str]:
        """
        Generate character n-grams from text.

        Args:
            text: Input text
            n: N-gram size

        Returns:
            Set of n-grams
        """
        if len(text) < n:
            return {text}

        return {text[i : i + n] for i in range(len(text) - n + 1)}

    def _ngram_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate n-gram similarity between texts.

        Uses character n-grams to capture similar phrasing even with
        different word choices.

        Args:
            text1: First text
            text2: Second text

        Returns:
            N-gram similarity between 0 and 1
        """
        ngrams1 = self._generate_ngrams(text1, self.ngram_size)
        ngrams2 = self._generate_ngrams(text2, self.ngram_size)

        if not ngrams1 and not ngrams2:
            return 1.0

        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = ngrams1 & ngrams2
        union = ngrams1 | ngrams2

        return len(intersection) / len(union)


class ResponseGrouper:
    """
    Groups similar responses together using semantic similarity.

    This is the main interface used by the consensus engine to replace
    the brittle length-based grouping with actual semantic similarity.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.7,
        calculator: Optional[SemanticSimilarityCalculator] = None,
    ) -> None:
        """
        Initialize the response grouper.

        Args:
            similarity_threshold: Minimum similarity to group responses (0-1)
            calculator: Optional custom similarity calculator
        """
        self.similarity_threshold = similarity_threshold
        self.calculator = calculator or SemanticSimilarityCalculator()

    def _collect_duplicate_members(
        self, texts: list[str]
    ) -> tuple[list[int], dict[int, list[int]]]:
        """Collect normalized duplicates under their first representative."""
        normalized_to_representative: dict[str, int] = {}
        representative_indices: list[int] = []
        duplicate_members: dict[int, list[int]] = {}

        for idx, text in enumerate(texts):
            normalized = self.calculator._normalize_text(text)
            representative_idx = normalized_to_representative.get(normalized)
            if representative_idx is None:
                normalized_to_representative[normalized] = idx
                representative_indices.append(idx)
                duplicate_members[idx] = [idx]
                continue

            duplicate_members[representative_idx].append(idx)

        return representative_indices, duplicate_members

    def _build_similarity_group(
        self,
        seed_idx: int,
        texts: list[str],
        representative_indices: list[int],
        duplicate_members: dict[int, list[int]],
        assigned_representatives: set[int],
    ) -> list[int]:
        """Build one transitive similarity group from a representative."""
        current_group = list(duplicate_members[seed_idx])
        current_representatives = [seed_idx]
        assigned_representatives.add(seed_idx)

        for candidate_idx in representative_indices:
            if candidate_idx <= seed_idx or candidate_idx in assigned_representatives:
                continue

            candidate_text = texts[candidate_idx]

            for group_idx in current_representatives:
                if self.calculator.are_similar(
                    texts[group_idx], candidate_text, self.similarity_threshold
                ):
                    current_representatives.append(candidate_idx)
                    current_group.extend(duplicate_members[candidate_idx])
                    assigned_representatives.add(candidate_idx)
                    break

        return current_group

    def group_responses(self, texts: list[str]) -> list[list[int]]:
        """
        Group similar texts together.

        Args:
            texts: List of text responses to group

        Returns:
            List of groups, where each group is a list of indices into the texts list
        """
        if not texts:
            return []

        if len(texts) == 1:
            return [[0]]

        representative_indices, duplicate_members = self._collect_duplicate_members(
            texts
        )

        groups: list[list[int]] = []
        assigned_representatives: set[int] = set()

        for i in representative_indices:
            if i in assigned_representatives:
                continue

            groups.append(
                self._build_similarity_group(
                    i,
                    texts,
                    representative_indices,
                    duplicate_members,
                    assigned_representatives,
                )
            )

        return groups

    def _select_group_representative(self, texts: list[str], group: list[int]) -> int:
        """Select the index with the highest average similarity in one group."""
        if len(group) == 1:
            return group[0]

        best_idx = group[0]
        best_avg_sim = 0.0

        for idx in group:
            similarities = [
                self.calculator.calculate_similarity(
                    texts[idx], texts[other_idx]
                ).hybrid
                for other_idx in group
                if other_idx != idx
            ]

            avg_sim = sum(similarities) / len(similarities) if similarities else 0.0

            if avg_sim > best_avg_sim:
                best_avg_sim = avg_sim
                best_idx = idx

        return best_idx

    def get_group_representatives(
        self, texts: list[str], groups: list[list[int]]
    ) -> list[int]:
        """
        Get the most representative text from each group.

        The representative is chosen as the text with highest average
        similarity to all other texts in the group.

        Args:
            texts: Original list of texts
            groups: Grouped indices from group_responses

        Returns:
            List of indices representing each group
        """
        return [self._select_group_representative(texts, group) for group in groups]


def calculate_response_similarity(response1: str, response2: str) -> float:
    """
    Convenience function to calculate similarity between two responses.

    Args:
        response1: First response text
        response2: Second response text

    Returns:
        Hybrid similarity score between 0 and 1
    """
    calculator = SemanticSimilarityCalculator()
    score = calculator.calculate_similarity(response1, response2)
    return score.hybrid
