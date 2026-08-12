"""Focused tests for collective-intelligence handler mapping helpers."""

from typing import Any

from openrouter_mcp.collective_intelligence.adaptive_router import (
    RoutingDecision,
    RoutingStrategy,
)
from openrouter_mcp.collective_intelligence.base import (
    PerformanceMetrics,
    ProcessingResult,
    QualityMetrics,
    TaskContext,
    TaskType,
)
from openrouter_mcp.collective_intelligence.collaborative_solver import (
    SolvingResult,
    SolvingSession,
    SolvingStrategy,
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
from openrouter_mcp.config.constants import CollectiveDefaults, ModelDefaults
from openrouter_mcp.handlers._collective_serialization import (
    _serialize_consensus_result,
    _serialize_cross_validation_result,
    _serialize_ensemble_result,
    _serialize_routing_decision,
    _serialize_solving_result,
)
from openrouter_mcp.handlers.collective_intelligence import (
    EnsembleReasoningRequest,
    _build_collective_request_requirements,
)


def test_collective_request_requirements_preserve_precedence_and_zeroes() -> None:
    request = EnsembleReasoningRequest(
        problem="test",
        temperature=0.0,
        max_tokens=0,
        models=["request-model"],
        system_prompt="request prompt",
    )

    assert _build_collective_request_requirements(
        request,
        base={
            "base_only": True,
            "temperature": 1.0,
            "system_prompt": "base prompt",
        },
        extras={
            "extra_only": True,
            "max_tokens": 99,
            "preferred_models": ["extra-model"],
            "system_prompt": "extra prompt",
        },
    ) == {
        "base_only": True,
        "extra_only": True,
        "temperature": 0.0,
        "max_tokens": 0,
        "preferred_models": ["request-model"],
        "system_prompt": "request prompt",
    }


def test_collective_request_requirements_preserve_falsy_defaults() -> None:
    request = EnsembleReasoningRequest(
        problem="test",
        max_tokens=None,
        models=[],
        system_prompt="",
    )

    assert _build_collective_request_requirements(request) == {
        "temperature": ModelDefaults.TEMPERATURE,
        "max_tokens": CollectiveDefaults.DEFAULT_MAX_TOKENS,
    }


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


def _routing_decision(*, metadata: dict[str, Any]) -> RoutingDecision:
    return RoutingDecision(
        task_id="routing-task",
        selected_model_id="selected-model",
        strategy_used=RoutingStrategy.ADAPTIVE,
        confidence_score=0.88,
        expected_performance={"quality": 0.91},
        alternative_models=[
            ("model-a", 0.8),
            ("model-b", 0.7),
            ("model-c", 0.6),
            ("model-d", 0.5),
        ],
        justification="Best overall fit",
        routing_time=0.02,
        metadata=metadata,
    )


def test_serialize_solving_result_preserves_independent_fields() -> None:
    session = SolvingSession(
        session_id="session-1",
        original_task=TaskContext(task_id="solve-task", content="Plan migration"),
        strategy=SolvingStrategy.ITERATIVE,
        components_used=["consensus", "validator"],
        intermediate_results=[],
    )
    result = SolvingResult(
        session=session,
        final_content="Final migration solution",
        confidence_score=0.84,
        quality_assessment=QualityMetrics(
            accuracy=0.8,
            consistency=0.7,
            completeness=0.6,
            relevance=0.9,
            confidence=0.85,
            coherence=0.75,
        ),
        solution_path=["Assess", "Migrate"],
        alternative_solutions=["Replace", "Retire"],
        improvement_suggestions=["Add rollback drill"],
        total_processing_time=2.4,
        component_contributions={"router": 0.4, "reasoner": 0.6},
    )

    assert _serialize_solving_result(result) == {
        "final_solution": "Final migration solution",
        "solution_path": ["Assess", "Migrate"],
        "alternative_solutions": ["Replace", "Retire"],
        "quality_assessment": {
            "overall_score": 0.7666666666666666,
            "accuracy": 0.8,
            "consistency": 0.7,
            "completeness": 0.6,
        },
        "component_contributions": {"router": 0.4, "reasoner": 0.6},
        "confidence": 0.84,
        "improvement_suggestions": ["Add rollback drill"],
        "processing_time": 2.4,
        "session_id": "session-1",
        "strategy_used": "iterative",
        "components_used": ["consensus", "validator"],
    }


def test_serialize_routing_decision_preserves_metadata_values() -> None:
    decision = _routing_decision(
        metadata={
            "total_candidates": 7,
            "constraints_applied": ["max_cost"],
            "constraints_unmet": ["preferred_provider"],
            "filtered_candidates": 2,
            "performance_weights": {"accuracy": 0.8},
            "preference_matches": ["model_family"],
            "thrift_feedback": {"source": "provider"},
        }
    )

    assert _serialize_routing_decision(decision) == {
        "selected_model": "selected-model",
        "selection_reasoning": "Best overall fit",
        "confidence": 0.88,
        "alternative_models": [
            {"model": "model-a", "score": 0.8},
            {"model": "model-b", "score": 0.7},
            {"model": "model-c", "score": 0.6},
        ],
        "routing_metrics": {
            "expected_performance": {"quality": 0.91},
            "strategy_used": "adaptive",
            "total_candidates": 7,
            "constraints_applied": ["max_cost"],
            "constraints_unmet": ["preferred_provider"],
            "filtered_candidates": 2,
            "performance_weights": {"accuracy": 0.8},
            "preference_matches": ["model_family"],
            "thrift_feedback": {"source": "provider"},
        },
        "selection_time": 0.02,
    }


def test_serialize_routing_decision_uses_metadata_defaults() -> None:
    decision = _routing_decision(metadata={})

    assert _serialize_routing_decision(decision) == {
        "selected_model": "selected-model",
        "selection_reasoning": "Best overall fit",
        "confidence": 0.88,
        "alternative_models": [
            {"model": "model-a", "score": 0.8},
            {"model": "model-b", "score": 0.7},
            {"model": "model-c", "score": 0.6},
        ],
        "routing_metrics": {
            "expected_performance": {"quality": 0.91},
            "strategy_used": "adaptive",
            "total_candidates": 0,
            "constraints_applied": [],
            "constraints_unmet": [],
            "filtered_candidates": 0,
            "performance_weights": {},
            "preference_matches": [],
            "thrift_feedback": None,
        },
        "selection_time": 0.02,
    }


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
