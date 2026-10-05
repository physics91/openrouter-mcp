from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

import src.openrouter_mcp.collective_intelligence.cross_validator as validator_module
from src.openrouter_mcp.collective_intelligence.cross_validator import (
    CrossValidator,
    ValidationCriteria,
    ValidationReport,
    ValidationStrategy,
)

pytestmark = pytest.mark.unit


def test_copy_validation_report_with_strategy_preserves_existing_copy_contract(
    sample_task,
    sample_processing_results,
):
    original_result = sample_processing_results[0]
    validator_models = ["validator-a"]
    issues = [Mock()]
    criteria_scores = {ValidationCriteria.ACCURACY: 0.75}
    recommendations = ["review accuracy"]
    source = ValidationReport(
        original_result=original_result,
        task_context=sample_task,
        validation_strategy=ValidationStrategy.PEER_REVIEW,
        validator_models=validator_models,
        issues=issues,
        overall_score=0.75,
        criteria_scores=criteria_scores,
        consensus_level=0.5,
        recommendations=recommendations,
        revised_content="revised",
        validation_time=1.25,
        metadata={"validator_failures": ["failure"]},
        timestamp=datetime(2000, 1, 1),
    )

    copied = validator_module._copy_validation_report_with_strategy(
        source,
        ValidationStrategy.QUALITY_ASSURANCE,
    )

    assert copied is not source
    assert copied.original_result is original_result
    assert copied.task_context is sample_task
    assert copied.validation_strategy is ValidationStrategy.QUALITY_ASSURANCE
    assert copied.validator_models is validator_models
    assert copied.issues is issues
    assert copied.overall_score == 0.75
    assert copied.criteria_scores is criteria_scores
    assert copied.consensus_level == 0.5
    assert copied.recommendations is recommendations
    assert copied.revised_content is None
    assert copied.validation_time == 0.0
    assert copied.metadata == source.metadata
    assert copied.metadata is not source.metadata
    assert copied.timestamp != source.timestamp
    assert source.validation_strategy is ValidationStrategy.PEER_REVIEW
    assert source.metadata == {"validator_failures": ["failure"]}


@pytest.mark.asyncio
async def test_quality_assurance_delegates_report_copy(
    monkeypatch,
    mock_model_provider,
    sample_task,
    sample_processing_results,
):
    validator = CrossValidator(mock_model_provider)
    peer_report = Mock()
    copied_report = Mock(spec=ValidationReport)
    peer_review = AsyncMock(return_value=peer_report)
    copy_report = Mock(return_value=copied_report)
    monkeypatch.setattr(validator, "_peer_review_validation", peer_review)
    monkeypatch.setattr(
        validator_module,
        "_copy_validation_report_with_strategy",
        copy_report,
        raising=False,
    )
    original_result = sample_processing_results[0]
    validator_models = ["validator-a"]

    result = await validator._quality_assurance_validation(
        original_result,
        sample_task,
        validator_models,
    )

    assert result is copied_report
    peer_review.assert_awaited_once_with(original_result, sample_task, validator_models)
    copy_report.assert_called_once_with(
        peer_report,
        ValidationStrategy.QUALITY_ASSURANCE,
    )


@pytest.mark.asyncio
async def test_bias_detection_fallback_delegates_report_copy(
    monkeypatch,
    mock_model_provider,
    sample_task,
    sample_processing_results,
):
    validator = CrossValidator(mock_model_provider)
    validator.specialized_validators.pop(ValidationCriteria.BIAS_NEUTRALITY)
    peer_report = Mock()
    copied_report = Mock(spec=ValidationReport)
    peer_review = AsyncMock(return_value=peer_report)
    copy_report = Mock(return_value=copied_report)
    monkeypatch.setattr(validator, "_peer_review_validation", peer_review)
    monkeypatch.setattr(
        validator_module,
        "_copy_validation_report_with_strategy",
        copy_report,
        raising=False,
    )
    original_result = sample_processing_results[0]
    validator_models = ["validator-a"]

    result = await validator._bias_detection_validation(
        original_result,
        sample_task,
        validator_models,
    )

    assert result is copied_report
    peer_review.assert_awaited_once_with(original_result, sample_task, validator_models)
    copy_report.assert_called_once_with(
        peer_report,
        ValidationStrategy.BIAS_DETECTION,
    )
