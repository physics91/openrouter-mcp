"""Shared text-processing constants and helpers."""

from __future__ import annotations

from typing import FrozenSet

CORE_ENGLISH_STOPWORDS: FrozenSet[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
    }
)

EXTENDED_ENGLISH_STOPWORDS: FrozenSet[str] = CORE_ENGLISH_STOPWORDS | frozenset(
    {
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "this",
        "that",
        "it",
        "as",
        "from",
        "into",
        "than",
        "then",
        "so",
        "such",
        "these",
        "those",
        "their",
        "there",
        "here",
        "we",
        "they",
        "you",
        "your",
        "our",
        "us",
        "i",
        "me",
        "my",
        "mine",
        "yours",
        "he",
        "she",
        "him",
        "her",
        "his",
        "hers",
        "them",
        "its",
    }
)

__all__ = ["CORE_ENGLISH_STOPWORDS", "EXTENDED_ENGLISH_STOPWORDS"]
