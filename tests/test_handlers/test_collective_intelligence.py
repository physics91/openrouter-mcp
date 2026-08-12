"""Focused tests for collective-intelligence handler response serialization."""

from openrouter_mcp.collective_intelligence.base import (
    ProcessingResult,
    QualityMetrics,
    TaskContext,
)
from openrouter_mcp.collective_intelligence.cross_validator import (
    ValidationCriteria,
    ValidationIssue,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
    ValidationStrategy,
)
from openrouter_mcp.handlers.collective_intelligence import (
    _serialize_cross_validation_result,
)


def _build_validation_result(
    *, validator_models: list[str], issues: list[ValidationIssue]
) -> ValidationResult:
    original_result = ProcessingResult(
        task_id="task-1",
        model_id="source-model",
        content="Content to validate",
        confidence=0.8,
    )
    task_context = TaskContext(task_id="task-1", content="Validate this content")
    report = ValidationReport(
        original_result=original_result,
        task_context=task_context,
        validation_strategy=ValidationStrategy.PEER_REVIEW,
        validator_models=validator_models,
        issues=issues,
        overall_score=0.75,
        criteria_scores={},
        consensus_level=0.8,
        recommendations=["Report recommendation"],
    )
    return ValidationResult(
        task_id="task-1",
        original_result=original_result,
        validation_report=report,
        is_valid=False,
        validation_confidence=0.73,
        improvement_suggestions=["Improve the source"],
        quality_metrics=QualityMetrics(
            accuracy=1.0,
            consistency=1.0,
            completeness=1.0,
            relevance=1.0,
            confidence=1.0,
            coherence=1.0,
        ),
        processing_time=0.25,
    )


def _issue(
    *,
    issue_id: str,
    validator_model_id: str,
    criteria: ValidationCriteria,
    severity: ValidationSeverity,
) -> ValidationIssue:
    return ValidationIssue(
        issue_id=issue_id,
        criteria=criteria,
        severity=severity,
        description=f"Description {issue_id}",
        suggestion=f"Suggestion {issue_id}",
        confidence=0.9,
        evidence=f"Evidence {issue_id}",
        validator_model_id=validator_model_id,
    )


def test_serialize_cross_validation_result_with_explicit_validators() -> None:
    result = _build_validation_result(
        validator_models=["validator-a", "validator-without-issues"],
        issues=[
            _issue(
                issue_id="issue-1",
                validator_model_id="validator-a",
                criteria=ValidationCriteria.ACCURACY,
                severity=ValidationSeverity.HIGH,
            )
        ],
    )

    assert _serialize_cross_validation_result(result) == {
        "validation_result": "INVALID",
        "validation_score": 0.73,
        "validation_issues": [
            {
                "criteria": "accuracy",
                "severity": "high",
                "description": "Description issue-1",
                "suggestion": "Suggestion issue-1",
                "confidence": 0.9,
            }
        ],
        "model_validations": [
            {"model": "validator-a", "criteria": "accuracy", "issues_found": 1},
            {
                "model": "validator-without-issues",
                "criteria": "none",
                "issues_found": 0,
            },
        ],
        "recommendations": ["Improve the source"],
        "confidence": 0.73,
        "processing_time": 0.25,
        "quality_metrics": {
            "overall_score": 1.0,
            "accuracy": 1.0,
            "consistency": 1.0,
        },
    }


def test_serializer_derives_validator_order_from_issues() -> None:
    result = _build_validation_result(
        validator_models=[],
        issues=[
            _issue(
                issue_id="issue-1",
                validator_model_id="validator-z",
                criteria=ValidationCriteria.ACCURACY,
                severity=ValidationSeverity.HIGH,
            ),
            _issue(
                issue_id="issue-2",
                validator_model_id="validator-a",
                criteria=ValidationCriteria.CONSISTENCY,
                severity=ValidationSeverity.MEDIUM,
            ),
            _issue(
                issue_id="issue-3",
                validator_model_id="validator-z",
                criteria=ValidationCriteria.RELEVANCE,
                severity=ValidationSeverity.LOW,
            ),
        ],
    )

    assert _serialize_cross_validation_result(result) == {
        "validation_result": "INVALID",
        "validation_score": 0.73,
        "validation_issues": [
            {
                "criteria": "accuracy",
                "severity": "high",
                "description": "Description issue-1",
                "suggestion": "Suggestion issue-1",
                "confidence": 0.9,
            },
            {
                "criteria": "consistency",
                "severity": "medium",
                "description": "Description issue-2",
                "suggestion": "Suggestion issue-2",
                "confidence": 0.9,
            },
            {
                "criteria": "relevance",
                "severity": "low",
                "description": "Description issue-3",
                "suggestion": "Suggestion issue-3",
                "confidence": 0.9,
            },
        ],
        "model_validations": [
            {"model": "validator-z", "criteria": "multiple", "issues_found": 2},
            {"model": "validator-a", "criteria": "consistency", "issues_found": 1},
        ],
        "recommendations": ["Improve the source"],
        "confidence": 0.73,
        "processing_time": 0.25,
        "quality_metrics": {
            "overall_score": 1.0,
            "accuracy": 1.0,
            "consistency": 1.0,
        },
    }
