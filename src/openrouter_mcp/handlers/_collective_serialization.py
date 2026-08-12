"""Response serialization helpers for collective intelligence handlers."""

from __future__ import annotations

from typing import Any, Dict

from ..collective_intelligence import (
    ConsensusResult,
    EnsembleResult,
    RoutingDecision,
    SolvingResult,
    ValidationResult,
)


def _serialize_consensus_result(result: ConsensusResult) -> Dict[str, Any]:
    """Serialize a consensus result to the MCP response contract."""
    return {
        "consensus_response": result.consensus_content,
        "agreement_level": result.agreement_level.value,
        "confidence_score": result.confidence_score,
        "participating_models": result.participating_models,
        "individual_responses": [
            {
                "model": response.model_id,
                "content": response.result.content,
                "confidence": response.result.confidence,
            }
            for response in result.model_responses
        ],
        "strategy_used": result.strategy_used.value,
        "processing_time": result.processing_time,
        "quality_metrics": {
            "accuracy": result.quality_metrics.accuracy,
            "consistency": result.quality_metrics.consistency,
            "completeness": result.quality_metrics.completeness,
            "overall_score": result.quality_metrics.overall_score(),
        },
    }


def _serialize_cross_validation_result(result: ValidationResult) -> Dict[str, Any]:
    """Serialize a cross-validation result to the MCP response contract."""
    report = result.validation_report
    issues = report.issues
    validator_models = getattr(report, "validator_models", []) or []
    if not validator_models:
        seen_models = set()
        for issue in issues:
            model_id = getattr(issue, "validator_model_id", None)
            if model_id and model_id not in seen_models:
                seen_models.add(model_id)
                validator_models.append(model_id)

    model_validations = []
    for model_id in validator_models:
        model_issues = [
            issue for issue in issues if issue.validator_model_id == model_id
        ]
        criteria_values = {
            (
                issue.criteria.value
                if hasattr(issue.criteria, "value")
                else str(issue.criteria)
            )
            for issue in model_issues
        }
        if not criteria_values:
            criteria_label = "none"
        elif len(criteria_values) == 1:
            criteria_label = next(iter(criteria_values))
        else:
            criteria_label = "multiple"

        model_validations.append(
            {
                "model": model_id,
                "criteria": criteria_label,
                "issues_found": len(model_issues),
            }
        )

    return {
        "validation_result": "VALID" if result.is_valid else "INVALID",
        "validation_score": result.validation_confidence,
        "validation_issues": [
            {
                "criteria": issue.criteria.value,
                "severity": issue.severity.value,
                "description": issue.description,
                "suggestion": issue.suggestion,
                "confidence": issue.confidence,
            }
            for issue in issues
        ],
        "model_validations": model_validations,
        "recommendations": result.improvement_suggestions,
        "confidence": result.validation_confidence,
        "processing_time": result.processing_time,
        "quality_metrics": {
            "overall_score": result.quality_metrics.overall_score(),
            "accuracy": result.quality_metrics.accuracy,
            "consistency": result.quality_metrics.consistency,
        },
    }


def _serialize_ensemble_result(result: EnsembleResult) -> Dict[str, Any]:
    """Serialize an ensemble result to the MCP response contract."""
    return {
        "final_result": result.final_content,
        "subtask_results": [
            {
                "subtask": subtask.sub_task.content,
                "model": subtask.assignment.model_id,
                "result": subtask.result.content,
                "confidence": subtask.result.confidence,
                "success": subtask.success,
            }
            for subtask in result.sub_task_results
        ],
        "model_assignments": {
            subtask.assignment.model_id: subtask.sub_task.content
            for subtask in result.sub_task_results
        },
        "reasoning_quality": {
            "overall_quality": result.overall_quality.overall_score(),
            "consistency": result.overall_quality.consistency,
            "completeness": result.overall_quality.completeness,
        },
        "processing_time": result.total_time,
        "strategy_used": result.decomposition_strategy.value,
        "success_rate": result.success_rate,
        "total_cost": result.total_cost,
    }


def _serialize_routing_decision(decision: RoutingDecision) -> Dict[str, Any]:
    """Serialize a routing decision to the MCP response contract."""
    return {
        "selected_model": decision.selected_model_id,
        "selection_reasoning": decision.justification,
        "confidence": decision.confidence_score,
        "alternative_models": [
            {"model": alternative[0], "score": alternative[1]}
            for alternative in decision.alternative_models[:3]
        ],
        "routing_metrics": {
            "expected_performance": decision.expected_performance,
            "strategy_used": decision.strategy_used.value,
            "total_candidates": decision.metadata.get("total_candidates", 0),
            "constraints_applied": decision.metadata.get("constraints_applied", []),
            "constraints_unmet": decision.metadata.get("constraints_unmet", []),
            "filtered_candidates": decision.metadata.get("filtered_candidates", 0),
            "performance_weights": decision.metadata.get("performance_weights", {}),
            "preference_matches": decision.metadata.get("preference_matches", []),
            "thrift_feedback": decision.metadata.get("thrift_feedback"),
        },
        "selection_time": decision.routing_time,
    }


def _serialize_solving_result(result: SolvingResult) -> Dict[str, Any]:
    """Serialize a collaborative solving result to the MCP response contract."""
    return {
        "final_solution": result.final_content,
        "solution_path": result.solution_path,
        "alternative_solutions": result.alternative_solutions,
        "quality_assessment": {
            "overall_score": result.quality_assessment.overall_score(),
            "accuracy": result.quality_assessment.accuracy,
            "consistency": result.quality_assessment.consistency,
            "completeness": result.quality_assessment.completeness,
        },
        "component_contributions": result.component_contributions,
        "confidence": result.confidence_score,
        "improvement_suggestions": result.improvement_suggestions,
        "processing_time": result.total_processing_time,
        "session_id": result.session.session_id,
        "strategy_used": result.session.strategy.value,
        "components_used": result.session.components_used,
    }
