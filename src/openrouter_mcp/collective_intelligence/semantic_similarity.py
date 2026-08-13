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
_TOKEN_PATTERN = re.compile(r"\b\w+\b")
_AFFIRMATIVE_TOKENS = frozenset(
    {"yes", "yeah", "yep", "correct", "true", "affirmative", "agree"}
)
_NEGATIVE_TOKENS = frozenset({"no", "nope", "incorrect", "false", "negative"})


def _expand_abbreviation(match: re.Match[str]) -> str:
    """Expand one abbreviation matched by ``_ABBREVIATION_PATTERN``."""
    return _ABBREVIATIONS[match.group(0)]


def _jaccard_from_token_sets(tokens1: set[str], tokens2: set[str]) -> float:
    """Calculate token Jaccard similarity from materialized token sets."""
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0

    intersection_size = len(tokens1 & tokens2)
    union_size = len(tokens1) + len(tokens2) - intersection_size
    return intersection_size / union_size


def _cosine_from_tokens(tokens1: list[str], tokens2: list[str]) -> float:
    """Calculate term-frequency cosine similarity from token lists."""
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0

    tf1 = Counter(tokens1)
    tf2 = Counter(tokens2)
    dot_product = sum(frequency * tf2.get(term, 0) for term, frequency in tf1.items())
    magnitude1 = math.sqrt(sum(value * value for value in tf1.values()))
    magnitude2 = math.sqrt(sum(value * value for value in tf2.values()))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


def _boost_short_affirmations_from_tokens(
    tokens1: list[str],
    tokens2: list[str],
    token_set1: set[str],
    token_set2: set[str],
    score: float,
) -> float:
    """Boost short-response similarity from precomputed tokens and sets."""
    if not tokens1 or not tokens2:
        return score

    if len(tokens1) <= 3 or len(tokens2) <= 3:
        if token_set1.issubset(token_set2) or token_set2.issubset(token_set1):
            return max(score, 0.85)
        if token_set1 & _AFFIRMATIVE_TOKENS and token_set2 & _AFFIRMATIVE_TOKENS:
            return max(score, 0.8)
        if token_set1 & _NEGATIVE_TOKENS and token_set2 & _NEGATIVE_TOKENS:
            return max(score, 0.8)

    return score


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

        shared_token_data = None
        if _uses_canonical_similarity_pipeline(self):
            tokens1 = self._tokenize(norm1)
            tokens2 = self._tokenize(norm2)
            token_set1 = set(tokens1)
            token_set2 = set(tokens2)
            shared_token_data = (tokens1, tokens2, token_set1, token_set2)
            jaccard = _jaccard_from_token_sets(token_set1, token_set2)
        else:
            jaccard = self._jaccard_similarity(norm1, norm2)

        # Calculate remaining individual metrics
        levenshtein = self._normalized_levenshtein(norm1, norm2)
        if shared_token_data is None:
            cosine = self._cosine_similarity(norm1, norm2)
        else:
            tokens1, tokens2, _, _ = shared_token_data
            cosine = _cosine_from_tokens(tokens1, tokens2)
        ngram = self._ngram_similarity(norm1, norm2)

        # Hybrid score: weighted combination of metrics
        # Weights tuned for semantic similarity of AI responses
        hybrid = (
            0.30 * jaccard  # Token overlap is important
            + 0.20 * levenshtein  # Edit distance helps with paraphrasing
            + 0.35 * cosine  # TF-IDF captures semantic content
            + 0.15 * ngram  # Character n-grams catch similar phrasing
        )

        if shared_token_data is None:
            hybrid = self._boost_short_affirmations(norm1, norm2, hybrid)
        else:
            tokens1, tokens2, token_set1, token_set2 = shared_token_data
            hybrid = _boost_short_affirmations_from_tokens(
                tokens1, tokens2, token_set1, token_set2, hybrid
            )
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
        return _boost_short_affirmations_from_tokens(
            tokens1, tokens2, set(tokens1), set(tokens2), score
        )

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

        # Collapse Unicode whitespace runs and remove leading/trailing whitespace.
        text = " ".join(text.split())

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
        return _jaccard_from_token_sets(tokens1, tokens2)

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
        if len1 <= len2:
            shorter, longer = text1, text2
        else:
            shorter, longer = text2, text1
        if longer.startswith(shorter) or longer.endswith(shorter) or shorter in longer:
            return 1.0 - ((len(longer) - len(shorter)) / max_length)

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

        return _cosine_from_tokens(tokens1, tokens2)

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

        intersection_size = len(ngrams1 & ngrams2)
        union_size = len(ngrams1) + len(ngrams2) - intersection_size

        return intersection_size / union_size


_SYMMETRIC_METHOD_NAMES = (
    "calculate_similarity",
    "_normalize_text",
    "_tokenize",
    "_jaccard_similarity",
    "_normalized_levenshtein",
    "_cosine_similarity",
    "_generate_ngrams",
    "_ngram_similarity",
    "_boost_short_affirmations",
    "_boost_high_overlap",
)
_CANONICAL_SYMMETRIC_METHODS = tuple(
    (name, getattr(SemanticSimilarityCalculator, name))
    for name in _SYMMETRIC_METHOD_NAMES
)
_SYMMETRIC_METHOD_NAME_SET = frozenset(_SYMMETRIC_METHOD_NAMES)
_CANONICAL_SYMMETRIC_METHOD_VALUES = tuple(
    method for _, method in _CANONICAL_SYMMETRIC_METHODS
)


def _uses_canonical_similarity_pipeline(
    calculator: SemanticSimilarityCalculator,
) -> bool:
    """Return whether all observable calculator methods retain canonical behavior."""
    if type(calculator) is not SemanticSimilarityCalculator:
        return False
    if not vars(calculator).keys().isdisjoint(_SYMMETRIC_METHOD_NAME_SET):
        return False

    calculator_namespace = type(calculator).__dict__
    current_methods = tuple(
        calculator_namespace.get(name) for name in _SYMMETRIC_METHOD_NAMES
    )
    return current_methods == _CANONICAL_SYMMETRIC_METHOD_VALUES


_GROUPING_MODULE_DEPENDENCY_NAMES = (
    "Counter",
    "SimilarityScore",
    "EXTENDED_ENGLISH_STOPWORDS",
    "_ABBREVIATIONS",
    "_ABBREVIATION_PATTERN",
    "_NUMBER_PATTERN",
    "_TOKEN_PATTERN",
    "_AFFIRMATIVE_TOKENS",
    "_NEGATIVE_TOKENS",
    "_expand_abbreviation",
    "_jaccard_from_token_sets",
    "_cosine_from_tokens",
    "_boost_short_affirmations_from_tokens",
    "_uses_canonical_similarity_pipeline",
    "_SYMMETRIC_METHOD_NAMES",
    "_SYMMETRIC_METHOD_NAME_SET",
    "_CANONICAL_SYMMETRIC_METHODS",
    "_CANONICAL_SYMMETRIC_METHOD_VALUES",
)
_CANONICAL_GROUPING_MODULE_DEPENDENCIES = tuple(
    (name, globals()[name]) for name in _GROUPING_MODULE_DEPENDENCY_NAMES
)
_CANONICAL_GROUPING_SQRT = math.sqrt
_MAX_PREPARED_GROUPING_RESPONSES = 128
_MAX_PREPARED_GROUPING_CHARACTERS = 256 * 1024
_MAX_PREPARED_NGRAM_CHARACTERS = 16 * 1024
_MAX_PREPARED_NGRAM_WINDOWS = 32 * 1024
_MAX_PREPARED_NGRAM_GENERATED_CHARACTERS = 1024 * 1024


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

        if (
            type(self) is ResponseGrouper
            and "_can_use_prepared_grouping" not in vars(self)
            and type(self).__dict__.get("_can_use_prepared_grouping")
            is _CANONICAL_CAN_USE_PREPARED_GROUPING
            and self._can_use_prepared_grouping(texts)
        ):
            return self._group_prepared_responses(texts)

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

    def _can_use_prepared_grouping(self, texts: list[str]) -> bool:
        """Return whether grouping can safely reuse canonical response features."""
        if type(self) is not ResponseGrouper or type(texts) is not list:
            return False
        if len(texts) > _MAX_PREPARED_GROUPING_RESPONSES:
            return False
        if any(type(text) is not str for text in texts):
            return False
        if sum(len(text) for text in texts) > _MAX_PREPARED_GROUPING_CHARACTERS:
            return False

        calculator = self.calculator
        if type(calculator) is not SemanticSimilarityCalculator:
            return False
        if type(calculator.case_sensitive) is not bool:
            return False
        if type(calculator.min_token_length) is not int:
            return False
        if type(calculator.ngram_size) is not int:
            return False

        dependency_namespace = globals()
        if math.sqrt is not _CANONICAL_GROUPING_SQRT:
            return False
        if any(
            dependency_namespace.get(name) is not dependency
            for name, dependency in _CANONICAL_GROUPING_MODULE_DEPENDENCIES
        ):
            return False
        if not _uses_canonical_similarity_pipeline(calculator):
            return False

        calculator_namespace = vars(calculator)
        if "are_similar" in calculator_namespace:
            return False
        if (
            type(calculator).__dict__.get("are_similar")
            is not _CANONICAL_CALCULATOR_ARE_SIMILAR
        ):
            return False

        grouper_namespace = vars(self)
        if not grouper_namespace.keys().isdisjoint(_CANONICAL_GROUPER_METHOD_NAME_SET):
            return False
        grouper_type_namespace = type(self).__dict__
        return all(
            grouper_type_namespace.get(name) is method
            for name, method in _CANONICAL_GROUPER_METHODS
        )

    def _group_prepared_responses(self, texts: list[str]) -> list[list[int]]:
        """Group canonical responses while reusing normalized lexical features."""
        normalized_texts = [self.calculator._normalize_text(text) for text in texts]
        normalized_to_representative: dict[str, int] = {}
        representative_indices: list[int] = []
        duplicate_members: dict[int, list[int]] = {}

        for idx, normalized in enumerate(normalized_texts):
            representative_idx = normalized_to_representative.get(normalized)
            if representative_idx is None:
                normalized_to_representative[normalized] = idx
                representative_indices.append(idx)
                duplicate_members[idx] = [idx]
                continue
            duplicate_members[representative_idx].append(idx)

        prepared_responses: dict[int, tuple[int, Counter[str], float]] = {}
        prepared_ngrams: dict[int, int] = {}
        ngram_bits = {} if self._can_prepare_grouping_ngrams(normalized_texts) else None
        groups: list[list[int]] = []
        assigned_representatives: set[int] = set()

        for seed_idx in representative_indices:
            if seed_idx in assigned_representatives:
                continue

            current_group = list(duplicate_members[seed_idx])
            current_representatives = [seed_idx]
            assigned_representatives.add(seed_idx)

            for candidate_idx in representative_indices:
                if (
                    candidate_idx <= seed_idx
                    or candidate_idx in assigned_representatives
                ):
                    continue

                for group_idx in current_representatives:
                    if self._prepared_responses_are_similar(
                        normalized_texts,
                        prepared_responses,
                        prepared_ngrams,
                        ngram_bits,
                        group_idx,
                        candidate_idx,
                    ):
                        current_representatives.append(candidate_idx)
                        current_group.extend(duplicate_members[candidate_idx])
                        assigned_representatives.add(candidate_idx)
                        break

            groups.append(current_group)

        return groups

    def _can_prepare_grouping_ngrams(self, normalized_texts: list[str]) -> bool:
        """Bound the work and retained text used by prepared n-gram masks."""
        if sum(len(text) for text in normalized_texts) > _MAX_PREPARED_NGRAM_CHARACTERS:
            return False

        ngram_size = self.calculator.ngram_size
        total_windows = 0
        total_generated_characters = 0

        for text in normalized_texts:
            text_length = len(text)
            if text_length < ngram_size:
                window_count = 1
                generated_characters = text_length
            else:
                window_count = text_length - ngram_size + 1
                if ngram_size > 0:
                    generated_characters = window_count * ngram_size
                elif ngram_size == 0:
                    generated_characters = 0
                else:
                    generated_characters = window_count * text_length

            total_windows += window_count
            if total_windows > _MAX_PREPARED_NGRAM_WINDOWS:
                return False

            total_generated_characters += generated_characters
            if total_generated_characters > _MAX_PREPARED_NGRAM_GENERATED_CHARACTERS:
                return False

        return True

    def _prepare_grouping_response(
        self, normalized_text: str
    ) -> tuple[int, Counter[str], float]:
        """Prepare reusable lexical features."""
        tokens = self.calculator._tokenize(normalized_text)
        frequencies = Counter(tokens)
        magnitude = math.sqrt(sum(value * value for value in frequencies.values()))
        return len(tokens), frequencies, magnitude

    def _prepare_grouping_ngram_mask(
        self, normalized_text: str, ngram_bits: dict[str, int]
    ) -> int:
        """Encode one response's reusable n-gram set as a bit mask."""
        ngram_mask = 0
        ngram_size = self.calculator.ngram_size
        if len(normalized_text) < ngram_size:
            ngrams = (normalized_text,)
        else:
            ngrams = (
                normalized_text[index : index + ngram_size]
                for index in range(len(normalized_text) - ngram_size + 1)
            )

        ngram_bit_get = ngram_bits.get
        for ngram in ngrams:
            ngram_bit = ngram_bit_get(ngram)
            if ngram_bit is None:
                ngram_bit = 1 << len(ngram_bits)
                ngram_bits[ngram] = ngram_bit
            ngram_mask |= ngram_bit

        return ngram_mask

    def _prepared_responses_are_similar(
        self,
        normalized_texts: list[str],
        prepared_responses: dict[int, tuple[int, Counter[str], float]],
        prepared_ngrams: dict[int, int],
        ngram_bits: dict[str, int] | None,
        left_idx: int,
        right_idx: int,
    ) -> bool:
        """Compare normalized responses using lazily cached lexical features."""
        left_prepared = prepared_responses.get(left_idx)
        if left_prepared is None:
            left_prepared = self._prepare_grouping_response(normalized_texts[left_idx])
            prepared_responses[left_idx] = left_prepared

        right_prepared = prepared_responses.get(right_idx)
        if right_prepared is None:
            right_prepared = self._prepare_grouping_response(
                normalized_texts[right_idx]
            )
            prepared_responses[right_idx] = right_prepared

        left_count, left_frequencies, left_magnitude = left_prepared
        right_count, right_frequencies, right_magnitude = right_prepared
        left_terms = left_frequencies.keys()
        right_terms = right_frequencies.keys()

        if not left_frequencies and not right_frequencies:
            jaccard = 1.0
        elif not left_frequencies or not right_frequencies:
            jaccard = 0.0
        else:
            intersection_size = len(left_terms & right_terms)
            union_size = (
                len(left_frequencies) + len(right_frequencies) - intersection_size
            )
            jaccard = intersection_size / union_size

        calculator = self.calculator
        if not left_count and not right_count:
            cosine = 1.0
        elif not left_count or not right_count:
            cosine = 0.0
        else:
            dot_product = 0
            right_frequency = right_frequencies.get
            for term, frequency in left_frequencies.items():
                dot_product += frequency * right_frequency(term, 0)
            if left_magnitude == 0 or right_magnitude == 0:
                cosine = 0.0
            else:
                cosine = dot_product / (left_magnitude * right_magnitude)

        boost_floor = 0.0
        if left_count and right_count and (left_count <= 3 or right_count <= 3):
            if left_terms <= right_terms or right_terms <= left_terms:
                boost_floor = 0.85
            elif (
                left_terms & _AFFIRMATIVE_TOKENS and right_terms & _AFFIRMATIVE_TOKENS
            ) or (left_terms & _NEGATIVE_TOKENS and right_terms & _NEGATIVE_TOKENS):
                boost_floor = 0.8

        if jaccard >= 0.6 and cosine >= 0.6:
            boost_floor = max(boost_floor, 0.72)
        elif jaccard >= 0.5 and cosine >= 0.7:
            boost_floor = max(boost_floor, 0.7)

        threshold = self.similarity_threshold
        ngram = None
        if type(threshold) is int or type(threshold) is float:
            lower_hybrid = 0.30 * jaccard + 0.20 * 0.0 + 0.35 * cosine + 0.15 * 0.0
            upper_hybrid = 0.30 * jaccard + 0.20 * 1.0 + 0.35 * cosine + 0.15 * 1.0
            if boost_floor:
                lower_hybrid = max(lower_hybrid, boost_floor)
                upper_hybrid = max(upper_hybrid, boost_floor)

            if lower_hybrid >= threshold:
                return True
            if upper_hybrid < threshold:
                return False

            if ngram_bits is not None:
                left_ngrams = prepared_ngrams.get(left_idx)
                if left_ngrams is None:
                    left_ngrams = self._prepare_grouping_ngram_mask(
                        normalized_texts[left_idx], ngram_bits
                    )
                    prepared_ngrams[left_idx] = left_ngrams

                right_ngrams = prepared_ngrams.get(right_idx)
                if right_ngrams is None:
                    right_ngrams = self._prepare_grouping_ngram_mask(
                        normalized_texts[right_idx], ngram_bits
                    )
                    prepared_ngrams[right_idx] = right_ngrams

                intersection_size = (left_ngrams & right_ngrams).bit_count()
                union_size = (left_ngrams | right_ngrams).bit_count()
                ngram = intersection_size / union_size
                lower_hybrid = (
                    0.30 * jaccard + 0.20 * 0.0 + 0.35 * cosine + 0.15 * ngram
                )
                upper_hybrid = (
                    0.30 * jaccard + 0.20 * 1.0 + 0.35 * cosine + 0.15 * ngram
                )
                if boost_floor:
                    lower_hybrid = max(lower_hybrid, boost_floor)
                    upper_hybrid = max(upper_hybrid, boost_floor)

                if lower_hybrid >= threshold:
                    return True
                if upper_hybrid < threshold:
                    return False

        levenshtein = calculator._normalized_levenshtein(
            normalized_texts[left_idx], normalized_texts[right_idx]
        )
        if ngram is None:
            if ngram_bits is None:
                ngram = calculator._ngram_similarity(
                    normalized_texts[left_idx], normalized_texts[right_idx]
                )
            else:
                left_ngrams = prepared_ngrams.get(left_idx)
                if left_ngrams is None:
                    left_ngrams = self._prepare_grouping_ngram_mask(
                        normalized_texts[left_idx], ngram_bits
                    )
                    prepared_ngrams[left_idx] = left_ngrams

                right_ngrams = prepared_ngrams.get(right_idx)
                if right_ngrams is None:
                    right_ngrams = self._prepare_grouping_ngram_mask(
                        normalized_texts[right_idx], ngram_bits
                    )
                    prepared_ngrams[right_idx] = right_ngrams

                intersection_size = (left_ngrams & right_ngrams).bit_count()
                union_size = (left_ngrams | right_ngrams).bit_count()
                ngram = intersection_size / union_size

        hybrid = 0.30 * jaccard + 0.20 * levenshtein + 0.35 * cosine + 0.15 * ngram
        if boost_floor:
            hybrid = max(hybrid, boost_floor)

        return hybrid >= threshold

    def _select_group_representative(self, texts: list[str], group: list[int]) -> int:
        """Select the index with the highest average similarity in one group."""
        if len(group) == 1:
            return group[0]

        if self._uses_canonical_symmetric_calculator() and len(group) == len(
            set(group)
        ):
            if (
                len(group) >= 3
                and type(self) is ResponseGrouper
                and "_can_use_prepared_representative_selection" not in vars(self)
                and type(self).__dict__.get(
                    "_can_use_prepared_representative_selection"
                )
                is _CANONICAL_CAN_USE_PREPARED_REPRESENTATIVE_SELECTION
                and self._can_use_prepared_representative_selection(texts, group)
            ):
                return self._select_prepared_group_representative(texts, group)
            return self._select_symmetric_group_representative(texts, group)

        best_idx = group[0]
        best_avg_sim = 0.0

        for idx in group:
            similarities = [
                self._calculate_pair_similarity(texts[idx], texts[other_idx])
                for other_idx in group
                if other_idx != idx
            ]

            avg_sim = sum(similarities) / len(similarities) if similarities else 0.0

            if avg_sim > best_avg_sim:
                best_avg_sim = avg_sim
                best_idx = idx

        return best_idx

    def _calculate_pair_similarity(self, text1: str, text2: str) -> float:
        """Calculate the hybrid score for one response pair."""
        return self.calculator.calculate_similarity(text1, text2).hybrid

    def _uses_canonical_symmetric_calculator(self) -> bool:
        """Return whether the calculator retains the canonical symmetric methods."""
        calculator = self.calculator
        if type(calculator) is not SemanticSimilarityCalculator:
            return False
        if any(name in vars(calculator) for name in _SYMMETRIC_METHOD_NAMES):
            return False

        calculator_type = type(calculator)
        return all(
            getattr(calculator_type, name, None) is canonical_method
            for name, canonical_method in _CANONICAL_SYMMETRIC_METHODS
        )

    def _can_use_prepared_representative_selection(
        self, texts: list[str], group: list[int]
    ) -> bool:
        """Return whether representative scoring can safely reuse features."""
        if type(group) is not list or len(group) < 3:
            return False
        if any(type(idx) is not int for idx in group):
            return False
        if len(group) != len(set(group)):
            return False
        if any(idx < -len(texts) or idx >= len(texts) for idx in group):
            return False

        grouper_namespace = vars(self)
        if not grouper_namespace.keys().isdisjoint(
            _CANONICAL_REPRESENTATIVE_METHOD_NAME_SET
        ):
            return False
        grouper_type_namespace = type(self).__dict__
        if any(
            grouper_type_namespace.get(name) is not method
            for name, method in _CANONICAL_REPRESENTATIVE_METHODS
        ):
            return False
        if "_can_use_prepared_grouping" in grouper_namespace:
            return False
        if (
            grouper_type_namespace.get("_can_use_prepared_grouping")
            is not _CANONICAL_CAN_USE_PREPARED_GROUPING
        ):
            return False

        return self._can_use_prepared_grouping(texts)

    def _calculate_prepared_pair_similarity(
        self,
        normalized_left: str,
        normalized_right: str,
        left_prepared: tuple[int, Counter[str], float],
        right_prepared: tuple[int, Counter[str], float],
        left_ngrams: int,
        right_ngrams: int,
    ) -> float:
        """Calculate one exact hybrid score from reusable response features."""
        if normalized_left == normalized_right:
            return 1.0

        left_count, left_frequencies, left_magnitude = left_prepared
        right_count, right_frequencies, right_magnitude = right_prepared
        left_terms = left_frequencies.keys()
        right_terms = right_frequencies.keys()

        if not left_frequencies and not right_frequencies:
            jaccard = 1.0
        elif not left_frequencies or not right_frequencies:
            jaccard = 0.0
        else:
            intersection_size = len(left_terms & right_terms)
            union_size = (
                len(left_frequencies) + len(right_frequencies) - intersection_size
            )
            jaccard = intersection_size / union_size

        levenshtein = self.calculator._normalized_levenshtein(
            normalized_left, normalized_right
        )

        if not left_count and not right_count:
            cosine = 1.0
        elif not left_count or not right_count:
            cosine = 0.0
        else:
            dot_product = 0
            right_frequency = right_frequencies.get
            for term, frequency in left_frequencies.items():
                dot_product += frequency * right_frequency(term, 0)
            if left_magnitude == 0 or right_magnitude == 0:
                cosine = 0.0
            else:
                cosine = dot_product / (left_magnitude * right_magnitude)

        intersection_size = (left_ngrams & right_ngrams).bit_count()
        union_size = (left_ngrams | right_ngrams).bit_count()
        ngram = intersection_size / union_size
        hybrid = 0.30 * jaccard + 0.20 * levenshtein + 0.35 * cosine + 0.15 * ngram

        if left_count and right_count and (left_count <= 3 or right_count <= 3):
            if left_terms <= right_terms or right_terms <= left_terms:
                hybrid = max(hybrid, 0.85)
            elif (
                left_terms & _AFFIRMATIVE_TOKENS and right_terms & _AFFIRMATIVE_TOKENS
            ) or (left_terms & _NEGATIVE_TOKENS and right_terms & _NEGATIVE_TOKENS):
                hybrid = max(hybrid, 0.8)

        if jaccard >= 0.6 and cosine >= 0.6:
            hybrid = max(hybrid, 0.72)
        elif jaccard >= 0.5 and cosine >= 0.7:
            hybrid = max(hybrid, 0.7)

        return hybrid

    def _select_prepared_group_representative(
        self, texts: list[str], group: list[int]
    ) -> int:
        """Select a representative while reusing exact response features."""
        normalized_texts = {
            idx: self.calculator._normalize_text(texts[idx]) for idx in group
        }
        if not self._can_prepare_grouping_ngrams(
            [normalized_texts[idx] for idx in group]
        ):
            return self._select_symmetric_group_representative(texts, group)

        prepared_responses = {
            idx: self._prepare_grouping_response(normalized_texts[idx]) for idx in group
        }
        ngram_bits: dict[str, int] = {}
        prepared_ngrams = {
            idx: self._prepare_grouping_ngram_mask(normalized_texts[idx], ngram_bits)
            for idx in group
        }
        similarity_totals = [0.0] * len(group)

        for position, idx in enumerate(group):
            for other_position in range(position + 1, len(group)):
                other_idx = group[other_position]
                similarity = self._calculate_prepared_pair_similarity(
                    normalized_texts[idx],
                    normalized_texts[other_idx],
                    prepared_responses[idx],
                    prepared_responses[other_idx],
                    prepared_ngrams[idx],
                    prepared_ngrams[other_idx],
                )
                similarity_totals[position] += similarity
                similarity_totals[other_position] += similarity

        best_idx = group[0]
        best_avg_sim = 0.0
        comparison_count = len(group) - 1
        for idx, total in zip(group, similarity_totals):
            avg_sim = total / comparison_count
            if avg_sim > best_avg_sim:
                best_avg_sim = avg_sim
                best_idx = idx

        return best_idx

    def _select_symmetric_group_representative(
        self, texts: list[str], group: list[int]
    ) -> int:
        """Select a representative while evaluating each symmetric pair once."""
        similarity_totals = [0.0] * len(group)

        for position, idx in enumerate(group):
            for other_position in range(position + 1, len(group)):
                other_idx = group[other_position]
                similarity = self._calculate_pair_similarity(
                    texts[idx], texts[other_idx]
                )
                similarity_totals[position] += similarity
                similarity_totals[other_position] += similarity

        best_idx = group[0]
        best_avg_sim = 0.0
        comparison_count = len(group) - 1
        for idx, total in zip(group, similarity_totals):
            avg_sim = total / comparison_count
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


_CANONICAL_CALCULATOR_ARE_SIMILAR = SemanticSimilarityCalculator.are_similar
_CANONICAL_GROUPER_METHOD_NAMES = (
    "group_responses",
    "_collect_duplicate_members",
    "_build_similarity_group",
    "_can_use_prepared_grouping",
    "_group_prepared_responses",
    "_can_prepare_grouping_ngrams",
    "_prepare_grouping_response",
    "_prepare_grouping_ngram_mask",
    "_prepared_responses_are_similar",
)
_CANONICAL_GROUPER_METHODS = tuple(
    (name, getattr(ResponseGrouper, name)) for name in _CANONICAL_GROUPER_METHOD_NAMES
)
_CANONICAL_GROUPER_METHOD_NAME_SET = frozenset(_CANONICAL_GROUPER_METHOD_NAMES)
_CANONICAL_CAN_USE_PREPARED_GROUPING = ResponseGrouper._can_use_prepared_grouping
_CANONICAL_REPRESENTATIVE_METHOD_NAMES = (
    "_select_group_representative",
    "_calculate_pair_similarity",
    "_uses_canonical_symmetric_calculator",
    "_can_use_prepared_representative_selection",
    "_calculate_prepared_pair_similarity",
    "_select_prepared_group_representative",
    "_select_symmetric_group_representative",
    "get_group_representatives",
)
_CANONICAL_REPRESENTATIVE_METHODS = tuple(
    (name, getattr(ResponseGrouper, name))
    for name in _CANONICAL_REPRESENTATIVE_METHOD_NAMES
)
_CANONICAL_REPRESENTATIVE_METHOD_NAME_SET = frozenset(
    _CANONICAL_REPRESENTATIVE_METHOD_NAMES
)
_CANONICAL_CAN_USE_PREPARED_REPRESENTATIVE_SELECTION = (
    ResponseGrouper._can_use_prepared_representative_selection
)


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
