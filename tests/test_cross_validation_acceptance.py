"""Acceptance regressions with simulated providers, not live model acceptance."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.collective_intelligence.base import (
    ModelInfo,
    ProcessingResult,
    TaskContext,
)
from src.openrouter_mcp.collective_intelligence.cross_validator import (
    CrossValidator,
    ValidationConfig,
    ValidationStrategy,
)
from src.openrouter_mcp.handlers._collective_serialization import (
    _serialize_cross_validation_result,
)
from src.openrouter_mcp.handlers._openrouter_model_provider import (
    OpenRouterModelProvider,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def review(score=0.9, criteria=None, issues=None):
    return json.dumps(
        {
            "scores": {
                name: score
                for name in criteria
                or ["accuracy", "consistency", "completeness", "relevance"]
            },
            "issues": issues or [],
        },
        ensure_ascii=False,
    )


class ReviewProvider:
    def __init__(self, responses):
        self.responses = responses
        self.tasks = []

    async def get_available_models(self):
        return [
            ModelInfo(model_id=name, name=name, provider="evaluation")
            for name in self.responses
        ]

    async def process_task(self, task, model_id, **kwargs):
        self.tasks.append(task)
        await asyncio.sleep(0)
        response = self.responses[model_id]
        if isinstance(response, Exception):
            raise response
        if callable(response):
            response = response(task)
        return ProcessingResult(model_id=model_id, content=response, confidence=0.9)


async def evaluate(provider, requirements=None):
    result = await CrossValidator(provider).process(
        ProcessingResult(content="2 + 2 = 5", model_id="original"),
        TaskContext(content="Check this claim", requirements=requirements or {}),
    )
    return _serialize_cross_validation_result(result)


@pytest.mark.parametrize(
    "responses",
    [
        {"a": RuntimeError("unavailable"), "b": RuntimeError("unavailable")},
        {"a": review(), "b": RuntimeError("unavailable")},
        {"a": review()},
        {},
    ],
)
async def test_insufficient_successful_validators_cannot_approve(responses):
    result = await evaluate(ReviewProvider(responses))
    assert result["validation_result"] == "INVALID"
    assert result["confidence"] == 0
    assert result["validation_status"] == "incomplete"


@pytest.mark.parametrize(
    "content",
    [
        "이 답변은 사실과 다릅니다. 정확성 점수: 0점.",
        "Accuracy: 0.0/1.0. Verdict: FAIL. The answer is false.",
        "No errors found.",
        "",
        '{"scores":{"accuracy":1},"issues":[]}',
        review(float("nan")),
        review(True),
        review(1.5),
    ],
)
async def test_unparseable_or_invalid_review_is_not_evidence_of_validity(content):
    result = await evaluate(ReviewProvider({"a": content, "b": content}))
    assert result["validation_result"] == "INVALID"
    assert result["validation_status"] == "incomplete"
    assert len(result["validator_failures"]) == 2


async def test_structured_rejection_uses_scores_even_without_english_keywords():
    result = await evaluate(ReviewProvider({"a": review(0.0), "b": review(0.0)}))
    assert result["validation_result"] == "INVALID"
    assert result["validation_status"] == "complete"
    assert result["validation_score"] == 0


async def test_valid_structured_reviews_can_approve_and_degraded_state_is_visible():
    result = await evaluate(
        ReviewProvider({"a": review(), "b": review(), "c": RuntimeError("offline")})
    )
    assert result["validation_result"] == "VALID"
    assert result["validation_status"] == "degraded"
    assert result["validation_score"] == pytest.approx(0.9)
    assert result["successful_validators"] == 2
    assert len(result["validator_failures"]) == 1
    failed = next(item for item in result["model_validations"] if item["model"] == "c")
    assert failed["status"] == "failed"


async def test_custom_criteria_and_generation_limits_reach_actual_provider_adapter():
    client = AsyncMock()
    client.list_models.return_value = [
        {"id": "evaluation/a"},
        {"id": "evaluation/b"},
    ]
    client.get_model_pricing.return_value = {"prompt": 0, "completion": 0}
    client.chat_completion.return_value = {
        "choices": [
            {"message": {"content": review(criteria=["technical_correctness"])}}
        ],
        "usage": {},
    }
    result = await evaluate(
        OpenRouterModelProvider(client),
        {
            "validation_criteria": ["technical_correctness"],
            "max_tokens": 32,
            "temperature": 0.0,
            "system_prompt": "한국어로 설명하세요.",
        },
    )
    assert result["validation_result"] == "VALID"
    for call in client.chat_completion.call_args_list:
        assert call.kwargs["max_tokens"] == 32
        assert call.kwargs["temperature"] == 0.0
        assert call.kwargs["messages"][0]["content"] == "한국어로 설명하세요."
        assert "technical_correctness" in call.kwargs["messages"][-1]["content"]


async def test_concurrent_requests_do_not_mutate_shared_validation_criteria():
    provider = ReviewProvider(
        {
            name: lambda task: review(criteria=task.requirements["validation_criteria"])
            for name in ("a", "b")
        }
    )
    validator = CrossValidator(provider)
    tasks = [
        TaskContext(content="Check", requirements={"validation_criteria": [name]})
        for name in ("domain_a", "domain_b")
    ]
    results = await asyncio.gather(
        *(validator.process(ProcessingResult(content="answer"), task) for task in tasks)
    )
    assert all(result.is_valid for result in results)
    for result, name in zip(results, ("domain_a", "domain_b")):
        assert result.validation_report.metadata["review_scores"]["a"] == {name: 0.9}


@pytest.mark.parametrize("strategy", list(ValidationStrategy))
async def test_every_strategy_preserves_all_provider_failure(strategy):
    provider = ReviewProvider(
        {"a": RuntimeError("offline"), "b": RuntimeError("offline")}
    )
    result = await CrossValidator(
        provider, ValidationConfig(strategy=strategy)
    ).process(ProcessingResult(content="claim"), TaskContext(content="check"))
    assert not result.is_valid
    assert result.validation_confidence == 0
    assert result.metadata["validation_status"] == "incomplete"


async def test_rejected_review_does_not_expose_sensitive_input_in_error_metadata():
    result = await evaluate(
        ReviewProvider({"a": '{"scores":"sensitive-eval-input"}', "b": review()})
    )
    assert "sensitive-eval-input" not in json.dumps(result)


async def test_structured_korean_issue_is_preserved_and_critical_issue_rejects():
    content = review(
        issues=[
            {
                "criterion": "accuracy",
                "severity": "critical",
                "description": "사실과 다릅니다",
                "suggestion": "근거를 확인하세요",
                "evidence": "2 + 2 = 5",
            }
        ]
    )
    result = await evaluate(ReviewProvider({"a": content, "b": content}))
    assert result["validation_result"] == "INVALID"
    assert result["validation_issues"][0]["description"] == "사실과 다릅니다"


@pytest.mark.parametrize(
    ("responses", "tracked_models"),
    [
        ({"a": review(), "b": RuntimeError("offline")}, set()),
        ({"a": review(), "b": review(), "c": RuntimeError("offline")}, {"a", "b"}),
    ],
)
async def test_failure_and_incomplete_evidence_do_not_train_validator_quality(
    responses, tracked_models
):
    validator = CrossValidator(ReviewProvider(responses))
    await validator.process(
        ProcessingResult(content="claim"), TaskContext(content="check")
    )
    assert set(validator.get_validator_performance()) == tracked_models
