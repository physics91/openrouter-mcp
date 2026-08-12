"""Focused tests for collective-intelligence handler response serialization."""

from openrouter_mcp.collective_intelligence.base import (
    PerformanceMetrics,
    ProcessingResult,
    QualityMetrics,
    TaskContext,
    TaskType,
)
from openrouter_mcp.collective_intelligence.consensus_engine import (
    AgreementLevel,
    ConsensusResult,
    ConsensusStrategy,
    ModelResponse,
)
from openrouter_mcp.collective_intelligence.cross_validator import (
    ValidationCriteria,
    ValidationIssue,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
    ValidationStrategy,
)
from openrouter_mcp.collective_intelligence.ensemble_reasoning import (
    DecompositionStrategy,
    EnsembleResult,
    ModelAssignment,
    SubTask,
    SubTaskResult,
)
from openrouter_mcp.handlers.collective_intelligence import (
    _serialize_consensus_result,
    _serialize_cross_validation_result,
    _serialize_ensemble_result,
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


def test_serialize_consensus_result_preserves_independent_model_lists() -> None:
    result = ConsensusResult(
        task_id="consensus-task",
        consensus_content="Agreed response",
        agreement_level=AgreementLevel.HIGH_CONSENSUS,
        confidence_score=0.82,
        participating_models=["participant-only", "model-b"],
        model_responses=[
            ModelResponse(
                model_id="model-a",
                result=ProcessingResult(
                    task_id="consensus-task",
                    model_id="model-a",
                    content="Response A",
                    confidence=0.7,
                ),
            ),
            ModelResponse(
                model_id="model-b",
                result=ProcessingResult(
                    task_id="consensus-task",
                    model_id="model-b",
                    content="Response B",
                    confidence=0.9,
                ),
            ),
        ],
        strategy_used=ConsensusStrategy.WEIGHTED_AVERAGE,
        processing_time=0.9,
        quality_metrics=QualityMetrics(
            accuracy=0.75,
            consistency=0.75,
            completeness=0.75,
            relevance=0.75,
            confidence=0.75,
            coherence=0.75,
        ),
    )

    assert _serialize_consensus_result(result) == {
        "consensus_response": "Agreed response",
        "agreement_level": "high_consensus",
        "confidence_score": 0.82,
        "participating_models": ["participant-only", "model-b"],
        "individual_responses": [
            {"model": "model-a", "content": "Response A", "confidence": 0.7},
            {"model": "model-b", "content": "Response B", "confidence": 0.9},
        ],
        "strategy_used": "weighted_average",
        "processing_time": 0.9,
        "quality_metrics": {
            "accuracy": 0.75,
            "consistency": 0.75,
            "completeness": 0.75,
            "overall_score": 0.75,
        },
    }


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


def test_serialize_ensemble_result_preserves_response_contract() -> None:
    original_task = TaskContext(
        task_id="ensemble-task",
        task_type=TaskType.ANALYSIS,
        content="Analyze the migration",
    )
    first_subtask = SubTask(
        sub_task_id="subtask-1",
        parent_task_id="ensemble-task",
        content="Assess the current system",
        task_type=TaskType.ANALYSIS,
        required_capabilities=[],
    )
    second_subtask = SubTask(
        sub_task_id="subtask-2",
        parent_task_id="ensemble-task",
        content="Plan the target system",
        task_type=TaskType.ANALYSIS,
        required_capabilities=[],
    )
    first_assignment = ModelAssignment(
        sub_task_id="subtask-1",
        model_id="shared-model",
        confidence_score=0.9,
        estimated_cost=0.001,
        estimated_time=0.4,
        justification="Best fit",
    )
    second_assignment = ModelAssignment(
        sub_task_id="subtask-2",
        model_id="shared-model",
        confidence_score=0.7,
        estimated_cost=0.002,
        estimated_time=0.8,
        justification="Available fallback",
    )
    result = EnsembleResult(
        task_id="ensemble-task",
        original_task=original_task,
        final_content="Combined migration plan",
        sub_task_results=[
            SubTaskResult(
                sub_task=first_subtask,
                assignment=first_assignment,
                result=ProcessingResult(
                    task_id="subtask-1",
                    model_id="shared-model",
                    content="Current-system assessment",
                    confidence=0.9,
                ),
                success=True,
            ),
            SubTaskResult(
                sub_task=second_subtask,
                assignment=second_assignment,
                result=ProcessingResult(
                    task_id="subtask-2",
                    model_id="shared-model",
                    content="Partial target-system plan",
                    confidence=0.4,
                ),
                success=False,
                error_message="Incomplete result",
            ),
        ],
        decomposition_strategy=DecompositionStrategy.PARALLEL,
        overall_quality=QualityMetrics(
            accuracy=0.5,
            consistency=0.5,
            completeness=0.5,
            relevance=0.5,
            confidence=0.5,
            coherence=0.5,
        ),
        performance_metrics=PerformanceMetrics(),
        total_cost=0.003,
        total_time=1.25,
        success_rate=0.5,
    )

    assert _serialize_ensemble_result(result) == {
        "final_result": "Combined migration plan",
        "subtask_results": [
            {
                "subtask": "Assess the current system",
                "model": "shared-model",
                "result": "Current-system assessment",
                "confidence": 0.9,
                "success": True,
            },
            {
                "subtask": "Plan the target system",
                "model": "shared-model",
                "result": "Partial target-system plan",
                "confidence": 0.4,
                "success": False,
            },
        ],
        "model_assignments": {"shared-model": "Plan the target system"},
        "reasoning_quality": {
            "overall_quality": 0.5,
            "consistency": 0.5,
            "completeness": 0.5,
        },
        "processing_time": 1.25,
        "strategy_used": "parallel",
        "success_rate": 0.5,
        "total_cost": 0.003,
    }
