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
from typing import List, Optional, Set

from ..utils.text import EXTENDED_ENGLISH_STOPWORDS


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
        abbreviations = {
            "ml": "machine learning",
            "ai": "artificial intelligence",
            "nlp": "natural language processing",
            "llm": "large language model",
            "llms": "large language models",
        }
        for short, expanded in abbreviations.items():
            text = re.sub(rf"\b{re.escape(short)}\b", expanded, text)

        # Normalize numeric values to reduce penalties for numeric variations
        text = re.sub(r"\b\d+(?:\.\d+)?\b", "num", text)

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text.strip())

        return text

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words, filtering by minimum length.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        # Split on word boundaries and punctuation
        tokens = re.findall(r"\b\w+\b", text)

        # Filter by minimum length
        return [
            token
            for token in tokens
            if len(token) >= self.min_token_length and token not in EXTENDED_ENGLISH_STOPWORDS
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
        Uses dynamic programming for O(m*n) complexity.

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

        # Create distance matrix
        # Only keep current and previous row to save memory
        prev_row = list(range(len2 + 1))

        for i in range(1, len1 + 1):
            curr_row = [i]
            for j in range(1, len2 + 1):
                # Cost of substitution
                cost = 0 if text1[i - 1] == text2[j - 1] else 1

                # Minimum of: deletion, insertion, substitution
                curr_row.append(
                    min(
                        prev_row[j] + 1,  # deletion
                        curr_row[j - 1] + 1,  # insertion
                        prev_row[j - 1] + cost,  # substitution
                    )
                )
            prev_row = curr_row

        # Normalize to 0-1 range
        max_len = max(len1, len2)
        distance = prev_row[-1]

        return 1.0 - (distance / max_len)

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

    def _generate_ngrams(self, text: str, n: int) -> Set[str]:
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

    def group_responses(self, texts: List[str]) -> List[List[int]]:
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

        groups: List[List[int]] = []
        assigned = set()

        for i, text1 in enumerate(texts):
            if i in assigned:
                continue

            # Start a new group with this text
            current_group = [i]
            assigned.add(i)

            # Find all similar texts
            for j, text2 in enumerate(texts):
                if j <= i or j in assigned:
                    continue

                # Check if similar to any text in current group
                # (transitive grouping)
                for group_idx in current_group:
                    if self.calculator.are_similar(
                        texts[group_idx], text2, self.similarity_threshold
                    ):
                        current_group.append(j)
                        assigned.add(j)
                        break

            groups.append(current_group)

        return groups

    def get_group_representatives(self, texts: List[str], groups: List[List[int]]) -> List[int]:
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
        representatives = []

        for group in groups:
            if len(group) == 1:
                representatives.append(group[0])
                continue

            # Calculate average similarity for each text in group
            best_idx = group[0]
            best_avg_sim = 0.0

            for idx in group:
                # Calculate average similarity to all other texts in group
                similarities = [
                    self.calculator.calculate_similarity(texts[idx], texts[other_idx]).hybrid
                    for other_idx in group
                    if other_idx != idx
                ]

                avg_sim = sum(similarities) / len(similarities) if similarities else 0.0

                if avg_sim > best_avg_sim:
                    best_avg_sim = avg_sim
                    best_idx = idx

            representatives.append(best_idx)

        return representatives


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
