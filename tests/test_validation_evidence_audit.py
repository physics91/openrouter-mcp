"""Regression evidence with simulated reviewers; no live model acceptance."""

import pytest

from src.openrouter_mcp.collective_intelligence.base import (
    ProcessingResult,
    TaskContext,
)
from src.openrouter_mcp.collective_intelligence.cross_validator import (
    CrossValidator,
    ValidationConfig,
    ValidationCriteria,
    ValidationStrategy,
)
from src.openrouter_mcp.collective_intelligence.review_response import parse_review
from tests.test_cross_validation_acceptance import ReviewProvider, review

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.mark.parametrize("strategy", list(ValidationStrategy))
@pytest.mark.parametrize("content", ["", "이 주장은 틀렸습니다.", "No errors found."])
async def test_every_strategy_requires_explicit_review_evidence(strategy, content):
    validator = CrossValidator(
        ReviewProvider({"a": content, "b": content}),
        ValidationConfig(strategy=strategy),
    )
    result = await validator.process(
        ProcessingResult(content="2 + 2 = 5"), TaskContext(content="Verify the claim")
    )
    assert not result.is_valid
    assert result.validation_confidence == 0
    assert result.metadata["validation_status"] == "incomplete"
    assert result.metadata["successful_validators"] == 0


@pytest.mark.parametrize("strategy", list(ValidationStrategy))
@pytest.mark.parametrize("score", [0.0, 0.9])
async def test_every_strategy_uses_scores_and_preserves_custom_criteria(
    strategy, score
):
    def answer(task):
        if task.metadata.get("validation_type") == "peer_review":
            return review(score, criteria=["technical_correctness"])
        return "An independently generated answer."

    validator = CrossValidator(
        ReviewProvider({"a": answer, "b": answer}),
        ValidationConfig(strategy=strategy),
    )
    result = await validator.process(
        ProcessingResult(content="Claim"),
        TaskContext(
            content="Verify the claim",
            requirements={"validation_criteria": ["technical_correctness"]},
        ),
    )
    assert result.is_valid is (score >= 0.7)
    assert result.metadata["validation_status"] == "complete"
    assert result.validation_report.criteria_scores == {"technical_correctness": score}
    assert result.validation_report.validation_strategy is strategy


async def test_opposing_scores_cannot_satisfy_consensus_requirement():
    validator = CrossValidator(
        ReviewProvider({"a": review(0.0), "b": review(1.0)}),
        ValidationConfig(require_consensus=True),
    )
    result = await validator.process(
        ProcessingResult(content="Claim"),
        TaskContext(content="Check", requirements={"validation_threshold": 0.4}),
    )
    assert result.validation_report.overall_score == 0.5
    assert result.validation_report.consensus_level == 0
    assert not result.is_valid


async def test_duplicate_score_keys_are_rejected_as_ambiguous_evidence():
    with pytest.raises(ValueError):
        parse_review('{"scores":{"accuracy":0,"accuracy":1},"issues":[]}', ["accuracy"])


async def test_consensus_reviews_independent_answers_before_approving():
    def answer(task):
        if task.metadata.get("validation_type") == "peer_review":
            assert "independent-evidence-marker" in task.content
            assert task.requirements["max_tokens"] == 75
            return review(0.9)
        assert task.requirements["max_tokens"] == 75
        return "independent-evidence-marker"

    provider = ReviewProvider({"a": answer, "b": answer})
    result = await CrossValidator(
        provider, ValidationConfig(strategy=ValidationStrategy.CONSENSUS_CHECK)
    ).process(
        ProcessingResult(content="Claim"),
        TaskContext(content="Check", requirements={"max_tokens": 75}),
    )
    assert result.is_valid
    assert len(provider.tasks) == 4


async def test_specialized_models_cannot_bypass_self_exclusion_or_availability():
    validator = CrossValidator(
        ReviewProvider({"original": review(), "eligible": review()}),
        ValidationConfig(
            specialized_validators={
                ValidationCriteria.ACCURACY: ["original", "missing"]
            }
        ),
    )
    selected = await validator._select_validator_models(
        ProcessingResult(model_id="original"), TaskContext(content="Check")
    )
    assert selected == ["eligible"]


@pytest.mark.parametrize(
    "config",
    [
        {"min_validators": 0},
        {"min_validators": 3, "max_validators": 2},
        {"max_validators": -1},
        {"timeout_seconds": float("inf")},
        {"confidence_threshold": float("nan")},
        {"consensus_threshold": 1.1},
    ],
)
async def test_invalid_validation_configuration_is_rejected(config):
    with pytest.raises(ValueError):
        ValidationConfig(**config)


async def test_truncated_review_is_not_accepted_even_if_json_parses():
    from unittest.mock import AsyncMock

    from src.openrouter_mcp.handlers._openrouter_model_provider import (
        OpenRouterModelProvider,
    )

    provider = OpenRouterModelProvider(AsyncMock())
    provider._estimate_cost = AsyncMock(return_value=0)
    truncated = await provider._build_processing_result(
        TaskContext(),
        "model",
        {"choices": [{"message": {"content": review()}, "finish_reason": "length"}]},
        0.1,
    )
    validator = CrossValidator(ReviewProvider({}))
    with pytest.raises(ValueError, match="finish|complete|truncat"):
        validator._parse_peer_review_result(
            truncated, "model", ["accuracy", "consistency", "completeness", "relevance"]
        )
