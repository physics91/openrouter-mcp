from unittest.mock import Mock, call

import pytest

from src.openrouter_mcp.collective_intelligence.cross_validator import (
    CrossValidator,
    ValidationConfig,
    ValidationCriteria,
    ValidationReport,
    ValidationStrategy,
    ValidatorFailureRecord,
)

pytestmark = pytest.mark.unit


def test_build_issue_validation_report_preserves_evaluation_order_and_identity(
    monkeypatch,
    mock_model_provider,
    sample_task,
    sample_processing_results,
):
    criteria = [ValidationCriteria.ACCURACY, ValidationCriteria.CLARITY]
    validator = CrossValidator(
        mock_model_provider,
        ValidationConfig(criteria=criteria),
    )
    original_result = sample_processing_results[0]
    validator_models = ["validator-a", "validator-b"]
    accuracy_issue = Mock(criteria=ValidationCriteria.ACCURACY)
    clarity_issue = Mock(criteria=ValidationCriteria.CLARITY)
    issues = [clarity_issue, accuracy_issue]
    failures = [
        ValidatorFailureRecord(
            validator_model_id="validator-b",
            criteria=ValidationCriteria.ACCURACY,
            error="unavailable",
        )
    ]
    events = []
    observed = {}

    def calculate_criteria_score(criteria_issues):
        events.append(("criteria", criteria_issues))
        return 0.25 * len(events)

    def calculate_overall_score(criteria_scores):
        events.append(("overall", criteria_scores))
        observed["criteria_scores"] = criteria_scores
        return 0.375

    def calculate_consensus_level(all_issues, models):
        events.append(("consensus", all_issues, models))
        return 0.625

    def generate_recommendations(all_issues):
        events.append(("recommendations", all_issues))
        return ["fix accuracy"]

    def build_failure_metadata(validator_failures):
        events.append(("metadata", validator_failures))
        return {"validator_failures": ["serialized"]}

    monkeypatch.setattr(
        validator, "_calculate_criteria_score", calculate_criteria_score
    )
    monkeypatch.setattr(validator, "_calculate_overall_score", calculate_overall_score)
    monkeypatch.setattr(
        validator, "_calculate_consensus_level", calculate_consensus_level
    )
    monkeypatch.setattr(
        validator, "_generate_recommendations", generate_recommendations
    )
    monkeypatch.setattr(
        validator,
        "_build_validator_failure_metadata",
        build_failure_metadata,
    )

    report = validator._build_issue_validation_report(
        original_result,
        sample_task,
        validator_models,
        issues,
        failures,
        strategy=ValidationStrategy.ADVERSARIAL,
    )

    assert events == [
        ("criteria", [accuracy_issue]),
        ("criteria", [clarity_issue]),
        ("overall", observed["criteria_scores"]),
        ("consensus", issues, validator_models),
        ("recommendations", issues),
        ("metadata", failures),
    ]
    assert list(observed["criteria_scores"]) == criteria
    assert report.original_result is original_result
    assert report.task_context is sample_task
    assert report.validation_strategy is ValidationStrategy.ADVERSARIAL
    assert report.validator_models is validator_models
    assert report.issues is issues
    assert report.criteria_scores is observed["criteria_scores"]
    assert report.overall_score == 0.375
    assert report.consensus_level == 0.625
    assert report.recommendations == ["fix accuracy"]
    assert report.metadata == {"validator_failures": ["serialized"]}


def test_build_issue_validation_report_preserves_exception_short_circuit(
    monkeypatch,
    mock_model_provider,
    sample_task,
    sample_processing_results,
):
    validator = CrossValidator(
        mock_model_provider,
        ValidationConfig(
            criteria=[ValidationCriteria.ACCURACY, ValidationCriteria.CLARITY]
        ),
    )
    criteria_score = Mock(side_effect=[0.5, RuntimeError("score failed")])
    overall_score = Mock()
    consensus_level = Mock()
    recommendations = Mock()
    failure_metadata = Mock()
    monkeypatch.setattr(validator, "_calculate_criteria_score", criteria_score)
    monkeypatch.setattr(validator, "_calculate_overall_score", overall_score)
    monkeypatch.setattr(validator, "_calculate_consensus_level", consensus_level)
    monkeypatch.setattr(validator, "_generate_recommendations", recommendations)
    monkeypatch.setattr(
        validator,
        "_build_validator_failure_metadata",
        failure_metadata,
    )

    with pytest.raises(RuntimeError, match="score failed"):
        validator._build_issue_validation_report(
            sample_processing_results[0],
            sample_task,
            ["validator-a"],
            [],
            [],
            strategy=ValidationStrategy.PEER_REVIEW,
        )

    assert criteria_score.call_args_list == [call([]), call([])]
    overall_score.assert_not_called()
    consensus_level.assert_not_called()
    recommendations.assert_not_called()
    failure_metadata.assert_not_called()


@pytest.mark.asyncio
async def test_peer_review_delegates_issue_report_building(
    monkeypatch,
    mock_model_provider,
    sample_task,
    sample_processing_results,
):
    validator = CrossValidator(mock_model_provider)
    issues = [Mock()]
    failures = [Mock()]
    report = Mock(spec=ValidationReport)
    build_report = Mock(return_value=report)
    report.metadata = {}
    collect_results = Mock(return_value=(issues, failures, {}))
    monkeypatch.setattr(
        validator,
        "_build_issue_validation_report",
        build_report,
        raising=False,
    )
    monkeypatch.setattr(validator, "_collect_peer_review_results", collect_results)
    validator_models = []
    original_result = sample_processing_results[0]

    result = await validator._peer_review_validation(
        original_result,
        sample_task,
        validator_models,
    )

    assert result is report
    collect_results.assert_called_once_with(
        [],
        validator_models,
        [criterion.value for criterion in validator.config.criteria],
    )
    build_report.assert_called_once_with(
        original_result,
        sample_task,
        validator_models,
        issues,
        failures,
        strategy=ValidationStrategy.PEER_REVIEW,
    )


@pytest.mark.asyncio
async def test_adversarial_delegates_issue_report_building(
    monkeypatch,
    mock_model_provider,
    sample_task,
    sample_processing_results,
):
    validator = CrossValidator(mock_model_provider)
    report = Mock(spec=ValidationReport)
    report.metadata = {}
    build_report = Mock(return_value=report)
    monkeypatch.setattr(
        validator,
        "_build_issue_validation_report",
        build_report,
        raising=False,
    )
    validator_models = []
    original_result = sample_processing_results[0]

    result = await validator._adversarial_validation(
        original_result,
        sample_task,
        validator_models,
    )

    assert result is report
    assert build_report.call_args.args[:3] == (
        original_result,
        sample_task,
        validator_models,
    )
    assert build_report.call_args.args[3:] == ([], [])
    assert build_report.call_args.kwargs == {"strategy": ValidationStrategy.ADVERSARIAL}
