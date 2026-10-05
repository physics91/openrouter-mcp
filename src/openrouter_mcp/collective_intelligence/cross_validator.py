"""
Cross-Model Validation

This module implements comprehensive validation and quality assurance mechanisms
that use multiple models to cross-validate results, detect inconsistencies,
and improve overall output quality through peer review processes.
"""

import asyncio
import json
import logging
import math
import statistics
from collections import deque
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from time import perf_counter
from typing import Any, Dict, List, Optional, Union

from ..utils.async_utils import raise_first_fatal_result
from .base import (
    CollectiveIntelligenceComponent,
    ModelCapability,
    ModelInfo,
    ModelProvider,
    ProcessingResult,
    QualityMetrics,
    TaskContext,
    TaskType,
    build_quality_metrics,
    require_complete_text,
)
from .review_response import build_review_prompt, parse_review

logger = logging.getLogger(__name__)


class ValidationStrategy(Enum):
    """Strategies for cross-model validation."""

    PEER_REVIEW = "peer_review"  # Multiple models review each other's outputs
    ADVERSARIAL = "adversarial"  # Models challenge each other's conclusions
    CONSENSUS_CHECK = "consensus_check"  # Verify agreement across models
    FACT_CHECK = "fact_check"  # Specialized fact-checking validation
    QUALITY_ASSURANCE = "quality_assurance"  # General quality assessment
    BIAS_DETECTION = "bias_detection"  # Detect potential biases in outputs


class ValidationCriteria(Enum):
    """Criteria for validation assessment."""

    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    COMPLETENESS = "completeness"
    RELEVANCE = "relevance"
    COHERENCE = "coherence"
    FACTUAL_CORRECTNESS = "factual_correctness"
    LOGICAL_SOUNDNESS = "logical_soundness"
    BIAS_NEUTRALITY = "bias_neutrality"
    CLARITY = "clarity"
    APPROPRIATENESS = "appropriateness"


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    CRITICAL = "critical"  # Major errors that invalidate the result
    HIGH = "high"  # Significant issues that need attention
    MEDIUM = "medium"  # Moderate issues that could be improved
    LOW = "low"  # Minor issues or suggestions
    INFO = "info"  # Informational feedback


@dataclass
class ValidationIssue:
    """A specific validation issue found during cross-validation."""

    issue_id: str
    criteria: ValidationCriteria | str
    severity: ValidationSeverity
    description: str
    suggestion: str
    confidence: float  # Confidence in the issue detection
    evidence: str  # Supporting evidence for the issue
    validator_model_id: str
    line_numbers: Optional[List[int]] = None  # Specific lines if applicable
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationConfig:
    """Configuration for cross-model validation."""

    strategy: ValidationStrategy = ValidationStrategy.PEER_REVIEW
    min_validators: int = 2
    max_validators: int = 4
    criteria: List[ValidationCriteria] = field(
        default_factory=lambda: [
            ValidationCriteria.ACCURACY,
            ValidationCriteria.CONSISTENCY,
            ValidationCriteria.COMPLETENESS,
            ValidationCriteria.RELEVANCE,
        ]
    )
    confidence_threshold: float = 0.7
    require_consensus: bool = False
    consensus_threshold: float = 0.6
    include_self_validation: bool = False
    timeout_seconds: float = 30.0
    specialized_validators: Dict[ValidationCriteria, List[str]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if any(
            type(count) is not int or count < 1
            for count in (self.min_validators, self.max_validators)
        ):
            raise ValueError("Validator counts must be positive integers")
        if self.min_validators > self.max_validators:
            raise ValueError("min_validators must not exceed max_validators")
        for name in ("confidence_threshold", "consensus_threshold"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be finite and between 0 and 1")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")


@dataclass
class ValidationResult:
    """Final result from cross-model validation."""

    task_id: str
    original_result: ProcessingResult
    validation_report: "ValidationReport"
    is_valid: bool
    validation_confidence: float
    improvement_suggestions: List[str]
    quality_metrics: QualityMetrics
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ValidatorFailureRecord:
    """Structured validator failure metadata."""

    validator_model_id: str
    criteria: ValidationCriteria
    error: str

    def to_metadata(self) -> Dict[str, str]:
        """Serialize the failure for report and process metadata."""
        return {
            "validator_model_id": self.validator_model_id,
            "criteria": self.criteria.value,
            "error": self.error,
        }


@dataclass
class ValidationReport:
    """Comprehensive validation report for a result."""

    original_result: ProcessingResult
    task_context: TaskContext
    validation_strategy: ValidationStrategy
    validator_models: List[str]
    issues: List[ValidationIssue]
    overall_score: float  # 0.0 to 1.0
    criteria_scores: dict[ValidationCriteria | str, float]
    consensus_level: float  # Level of agreement among validators
    recommendations: List[str]
    revised_content: Optional[str] = None  # Improved version if available
    validation_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


def _copy_validation_report_with_strategy(
    report: ValidationReport,
    strategy: ValidationStrategy,
) -> ValidationReport:
    return ValidationReport(
        original_result=report.original_result,
        task_context=report.task_context,
        validation_strategy=strategy,
        validator_models=report.validator_models,
        issues=report.issues,
        overall_score=report.overall_score,
        criteria_scores=report.criteria_scores,
        consensus_level=report.consensus_level,
        recommendations=report.recommendations,
        metadata=dict(report.metadata),
    )


@dataclass
class ValidatorAssessment:
    """Explicit evidence or a failure for one reviewer, without shared score state."""

    issues: list[ValidationIssue]
    scores: dict[str, float]
    failure: ValidatorFailureRecord | None = None


def _parse_review_assessment(
    result: ProcessingResult, model_id: str, criteria: list[str]
) -> ValidatorAssessment:
    require_complete_text(result)
    review = parse_review(result.content, criteria)
    issues = []
    for index, issue in enumerate(review.issues):
        try:
            criterion = ValidationCriteria(issue.criterion)
        except ValueError:
            criterion = issue.criterion
        issues.append(
            ValidationIssue(
                issue_id=f"review_{index}_{model_id}",
                criteria=criterion,
                severity=ValidationSeverity(issue.severity),
                description=issue.description,
                suggestion=issue.suggestion,
                confidence=result.confidence,
                evidence=issue.evidence,
                validator_model_id=model_id,
            )
        )
    return ValidatorAssessment(issues, review.scores)


class SpecializedValidator:
    """A focused reviewer using the same explicit evidence contract as peer review."""

    instructions = ""

    def __init__(self, criteria: ValidationCriteria, model_provider: ModelProvider):
        self.criteria = criteria
        self.model_provider = model_provider
        self._last_failure: ContextVar[ValidatorFailureRecord | None] = ContextVar(
            f"{criteria.value}_failure", default=None
        )

    async def assess(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_model_id: str,
        *,
        criteria: list[str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> ValidatorAssessment:
        criteria = criteria or [self.criteria.value]
        task = TaskContext(
            task_id=f"{self.criteria.value}_{result.task_id}_{validator_model_id}",
            task_type=TaskType.ANALYSIS,
            content=build_review_prompt(
                task_context.content, result.content, criteria, self.instructions
            ),
            requirements={**task_context.requirements, "validation_criteria": criteria},
            constraints=dict(task_context.constraints),
            metadata={"validation_type": "peer_review", "focus": self.criteria.value},
        )
        self._last_failure.set(None)
        try:
            response = await asyncio.wait_for(
                self.model_provider.process_task(task, validator_model_id),
                timeout=timeout_seconds,
            )
            return _parse_review_assessment(response, validator_model_id, criteria)
        except Exception as exc:
            failure = ValidatorFailureRecord(
                validator_model_id=validator_model_id,
                criteria=self.criteria,
                error=str(exc),
            )
            self._last_failure.set(failure)
            return ValidatorAssessment([], {}, failure)

    async def validate_with_metadata(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_model_id: str,
    ) -> tuple[list[ValidationIssue], ValidatorFailureRecord | None]:
        assessment = await self.assess(result, task_context, validator_model_id)
        return assessment.issues, assessment.failure

    async def validate(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_model_id: str,
    ) -> list[ValidationIssue]:
        issues, _ = await self.validate_with_metadata(
            result, task_context, validator_model_id
        )
        return issues

    def consume_last_failure(self) -> ValidatorFailureRecord | None:
        failure = self._last_failure.get()
        self._last_failure.set(None)
        return failure


class FactCheckValidator(SpecializedValidator):
    """Review factual claims and distinguish unsupported claims from verified facts."""

    instructions = (
        "Fact-check factual claims, inaccuracies, and unsupported statements. "
        "Identify specific evidence and corrections; do not invent citations."
    )

    def __init__(self, model_provider: ModelProvider):
        super().__init__(ValidationCriteria.FACTUAL_CORRECTNESS, model_provider)


class BiasDetectionValidator(SpecializedValidator):
    """Review unfair generalizations, stereotypes, and demographic or ideological bias."""

    instructions = (
        "Assess cultural, gender, racial, political, and ideological bias, "
        "unfair generalizations, stereotypes, and missing perspectives. "
        "Do not infer bias merely because the response mentions the word bias."
    )

    def __init__(self, model_provider: ModelProvider):
        super().__init__(ValidationCriteria.BIAS_NEUTRALITY, model_provider)


class CrossValidator(CollectiveIntelligenceComponent):
    """
    Cross-model validation system that uses multiple models to validate
    and improve the quality of AI-generated content.
    """

    def __init__(
        self,
        model_provider: ModelProvider,
        config: Optional[ValidationConfig] = None,
        max_history_size: int = 1000,
    ):
        super().__init__(model_provider)
        self.config = config or ValidationConfig()

        # Specialized validators
        self.specialized_validators = {
            ValidationCriteria.FACTUAL_CORRECTNESS: FactCheckValidator(model_provider),
            ValidationCriteria.BIAS_NEUTRALITY: BiasDetectionValidator(model_provider),
        }

        # Validation history with bounded size
        self._validation_history: deque = deque(maxlen=max_history_size)
        self.validator_performance: Dict[str, Dict[str, float]] = {}
        self.max_history_size = max_history_size

    @property
    def validation_history(self) -> List[ValidationResult]:
        """Get validation history as a list for backward compatibility."""
        return list(self._validation_history)

    @validation_history.setter
    def validation_history(self, value: List[ValidationResult]) -> None:
        """Set validation history for backward compatibility."""
        self._validation_history = deque(value, maxlen=self.max_history_size)

    def _build_validator_failure_metadata(
        self, failures: List[ValidatorFailureRecord]
    ) -> Dict[str, Any]:
        """Normalize validator failures for reports and process results."""
        serialized_failures = [failure.to_metadata() for failure in failures]
        return (
            {"validator_failures": serialized_failures} if serialized_failures else {}
        )

    async def process(
        self, result: ProcessingResult, task_context: TaskContext, **kwargs: Any
    ) -> ValidationResult:
        """
        Perform cross-model validation on a result.

        Args:
            result: The result to validate
            task_context: Original task context
            **kwargs: Additional validation options

        Returns:
            ValidationResult with comprehensive validation analysis
        """
        start_time = perf_counter()

        try:
            # Select validator models
            validator_models = await self._select_validator_models(result, task_context)

            # Perform validation using selected strategy
            validation_report = await self._perform_validation(
                result, task_context, validator_models
            )
            self._apply_evidence_status(validation_report)

            # Calculate overall validation metrics
            validation_confidence = self._calculate_validation_confidence(
                validation_report
            )
            is_valid = self._determine_validity(validation_report, task_context)
            improvement_suggestions = self._generate_improvement_suggestions(
                validation_report
            )
            quality_metrics = self._calculate_validation_quality_metrics(
                validation_report
            )

            # Create final validation result
            processing_time = perf_counter() - start_time
            metadata = {
                "validator_count": len(validator_models),
                "total_issues": len(validation_report.issues),
                "critical_issues": len(
                    [
                        i
                        for i in validation_report.issues
                        if i.severity == ValidationSeverity.CRITICAL
                    ]
                ),
            }
            if "validator_failures" in validation_report.metadata:
                metadata["validator_failures"] = validation_report.metadata[
                    "validator_failures"
                ]
            metadata["validation_status"] = validation_report.metadata[
                "validation_status"
            ]
            metadata["successful_validators"] = validation_report.metadata[
                "successful_validators"
            ]

            validation_result = ValidationResult(
                task_id=task_context.task_id,
                original_result=result,
                validation_report=validation_report,
                is_valid=is_valid,
                validation_confidence=validation_confidence,
                improvement_suggestions=improvement_suggestions,
                quality_metrics=quality_metrics,
                processing_time=processing_time,
                metadata=metadata,
            )

            # Update validation history and metrics
            self._validation_history.append(validation_result)
            self._update_validator_performance(validation_report)

            logger.info(
                f"Validation completed for task {task_context.task_id}: "
                f"{'VALID' if is_valid else 'INVALID'} "
                f"(confidence: {validation_confidence:.3f}, "
                f"issues: {len(validation_report.issues)})"
            )

            return validation_result

        except Exception as e:
            logger.error(f"Validation failed for task {task_context.task_id}: {e!s}")
            raise

    def _apply_evidence_status(self, report: ValidationReport) -> None:
        """A missing review is not a successful review with no issues."""
        failures = report.metadata.get("validator_failures", [])
        failed_models = {failure["validator_model_id"] for failure in failures}
        successful = set(report.validator_models) - failed_models
        report.metadata["successful_validators"] = len(successful)
        if len(successful) < max(1, self.config.min_validators):
            report.metadata["validation_status"] = "incomplete"
            report.overall_score = 0.0
            report.consensus_level = 0.0
            report.criteria_scores = {
                criterion: 0.0 for criterion in report.criteria_scores
            }
            report.recommendations.append(
                "Retry validation: insufficient successful reviewers."
            )
        else:
            report.metadata["validation_status"] = (
                "degraded" if failures else "complete"
            )

    async def _select_validator_models(
        self, result: ProcessingResult, task_context: TaskContext
    ) -> List[str]:
        """Select appropriate validator models."""
        available_models = await self.model_provider.get_available_models()
        preferred = task_context.requirements.get("preferred_models")
        if preferred:
            available_models = [
                model for model in available_models if model.model_id in preferred
            ]

        # Filter out the original model if self-validation is disabled
        if not self.config.include_self_validation:
            available_models = [
                model for model in available_models if model.model_id != result.model_id
            ]

        # Check for specialized validators
        specialized_models = []
        for criteria in self.config.criteria:
            if criteria in self.config.specialized_validators:
                specialized_models.extend(self.config.specialized_validators[criteria])

        # Score models for validation suitability
        scored_models = []
        for model in available_models:
            score = self._calculate_validator_suitability(model, task_context, result)
            scored_models.append((model.model_id, score))

        # Add specialized models with high scores
        for model_id in specialized_models:
            if model_id not in {model.model_id for model in available_models}:
                continue
            scored_models = [
                (candidate, max(score, 0.9) if candidate == model_id else score)
                for candidate, score in scored_models
            ]

        # Sort by score and select top validators
        scored_models.sort(key=lambda x: x[1], reverse=True)

        selected_count = min(
            max(self.config.min_validators, len(scored_models)),
            self.config.max_validators,
        )

        validator_models = list(
            dict.fromkeys(model_id for model_id, _ in scored_models)
        )[:selected_count]

        logger.info(f"Selected {len(validator_models)} validators: {validator_models}")

        return validator_models

    def _calculate_validator_suitability(
        self, model: ModelInfo, task_context: TaskContext, result: ProcessingResult
    ) -> float:
        """Calculate how suitable a model is for validation."""
        base_score = 0.5

        # Higher accuracy models are better validators
        accuracy_bonus = model.accuracy_score * 0.3

        # Models with relevant capabilities score higher
        capability_bonus = 0.0
        relevant_capabilities = [ModelCapability.ACCURACY, ModelCapability.REASONING]

        for cap in relevant_capabilities:
            if cap in model.capabilities:
                capability_bonus += model.capabilities[cap] * 0.1

        # Check historical validation performance
        performance_bonus = 0.0
        if model.model_id in self.validator_performance:
            perf = self.validator_performance[model.model_id]
            performance_bonus = perf.get("accuracy", 0.0) * 0.2

        return min(
            1.0, base_score + accuracy_bonus + capability_bonus + performance_bonus
        )

    async def _perform_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str],
    ) -> ValidationReport:
        """Perform the actual validation using selected models."""

        strategy_dispatch = {
            ValidationStrategy.PEER_REVIEW: self._peer_review_validation,
            ValidationStrategy.ADVERSARIAL: self._adversarial_validation,
            ValidationStrategy.CONSENSUS_CHECK: self._consensus_validation,
            ValidationStrategy.FACT_CHECK: self._fact_check_validation,
            ValidationStrategy.QUALITY_ASSURANCE: self._quality_assurance_validation,
            ValidationStrategy.BIAS_DETECTION: self._bias_detection_validation,
        }
        handler = strategy_dispatch.get(
            self.config.strategy, self._peer_review_validation
        )
        return await handler(result, task_context, validator_models)

    def _build_issue_validation_report(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str],
        issues: List[ValidationIssue],
        validator_failures: List[ValidatorFailureRecord],
        *,
        strategy: ValidationStrategy,
    ) -> ValidationReport:
        """Build a validation report from collected issues and failures."""
        criteria_scores: Dict[ValidationCriteria, float] = {}
        for criteria in self.config.criteria:
            criteria_issues = [issue for issue in issues if issue.criteria == criteria]
            criteria_scores[criteria] = self._calculate_criteria_score(criteria_issues)

        overall_score = self._calculate_overall_score(criteria_scores)
        consensus_level = self._calculate_consensus_level(issues, validator_models)

        return ValidationReport(
            original_result=result,
            task_context=task_context,
            validation_strategy=strategy,
            validator_models=validator_models,
            issues=issues,
            overall_score=overall_score,
            criteria_scores=criteria_scores,
            consensus_level=consensus_level,
            recommendations=self._generate_recommendations(issues),
            metadata=self._build_validator_failure_metadata(validator_failures),
        )

    async def _peer_review_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str],
        *,
        strategy: ValidationStrategy = ValidationStrategy.PEER_REVIEW,
        instructions: str = "",
    ) -> ValidationReport:
        """Run bounded reviews and aggregate only explicitly parsed evidence."""
        tasks = [
            self._create_peer_review_task(result, task_context, model_id, instructions)
            for model_id in validator_models
        ]
        responses = await asyncio.gather(
            *(
                self._execute_validation_task(model_id, task)
                for model_id, task in zip(validator_models, tasks)
            ),
            return_exceptions=True,
        )
        raise_first_fatal_result(responses)
        criteria = self._review_criteria(task_context)
        issues, failures, scores = self._collect_peer_review_results(
            responses, validator_models, criteria
        )
        if strategy is ValidationStrategy.ADVERSARIAL:
            for failure in failures:
                failure.criteria = ValidationCriteria.LOGICAL_SOUNDNESS
        return self._build_scored_validation_report(
            result,
            task_context,
            validator_models,
            issues,
            failures,
            scores,
            criteria,
            strategy=strategy,
        )

    def _build_scored_validation_report(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: list[str],
        issues: list[ValidationIssue],
        failures: list[ValidatorFailureRecord],
        review_scores: dict[str, dict[str, float]],
        criteria: list[str],
        *,
        strategy: ValidationStrategy,
    ) -> ValidationReport:
        report = self._build_issue_validation_report(
            result, task_context, validator_models, issues, failures, strategy=strategy
        )
        criteria_scores = {}
        for name in criteria:
            values = [scores[name] for scores in review_scores.values()]
            try:
                criterion = ValidationCriteria(name)
            except ValueError:
                criterion = name
            criteria_scores[criterion] = statistics.mean(values) if values else 0.0
        report.criteria_scores = criteria_scores
        report.overall_score = self._calculate_overall_score(criteria_scores)
        report.metadata["review_scores"] = review_scores
        report.consensus_level = self._calculate_score_agreement(review_scores)
        return report

    @staticmethod
    def _calculate_score_agreement(review_scores: dict[str, dict[str, float]]) -> float:
        """One minus mean pairwise rating distance; unrelated issue counts are not votes."""
        scores = list(review_scores.values())
        if not scores:
            return 0.0
        distances = [
            abs(first[criterion] - second[criterion])
            for index, first in enumerate(scores)
            for second in scores[index + 1 :]
            for criterion in first
        ]
        return 1.0 - statistics.mean(distances) if distances else 1.0

    def _collect_peer_review_results(
        self,
        validation_results: List[Union[ProcessingResult, BaseException]],
        validator_models: List[str],
        criteria: list[str] | None = None,
    ) -> tuple[
        list[ValidationIssue], list[ValidatorFailureRecord], dict[str, dict[str, float]]
    ]:
        """Collect peer review issues and transport failures in result order."""
        all_issues: List[ValidationIssue] = []
        validator_failures: List[ValidatorFailureRecord] = []
        review_scores: dict[str, dict[str, float]] = {}

        for i, validation_result in enumerate(validation_results):
            if not isinstance(validation_result, BaseException):
                try:
                    issues, scores = self._parse_peer_review_result(
                        validation_result, validator_models[i], criteria
                    )
                except ValueError as exc:
                    validation_result = exc
                else:
                    all_issues.extend(issues)
                    review_scores[validator_models[i]] = scores
                    continue
            if isinstance(validation_result, BaseException):
                logger.warning(
                    f"Validation failed for validator {validator_models[i]}: {validation_result!s}"
                )
                validator_failures.append(
                    ValidatorFailureRecord(
                        validator_model_id=validator_models[i],
                        criteria=ValidationCriteria.ACCURACY,
                        error=str(validation_result),
                    )
                )
                continue

        return all_issues, validator_failures, review_scores

    def _review_criteria(self, task: TaskContext | None = None) -> list[str]:
        requested = task.requirements.get("validation_criteria") if task else None
        if requested is None:
            return [criterion.value for criterion in self.config.criteria]
        if (
            not isinstance(requested, list)
            or not requested
            or any(not isinstance(name, str) or not name.strip() for name in requested)
        ):
            raise ValueError(
                "validation_criteria must contain nonempty criterion names"
            )
        return list(dict.fromkeys(name.strip() for name in requested))

    def _create_peer_review_task(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_model_id: str,
        instructions: str = "",
    ) -> TaskContext:
        criteria = self._review_criteria(task_context)
        return TaskContext(
            task_id=f"peer_review_{result.task_id}_{validator_model_id}",
            task_type=TaskType.ANALYSIS,
            content=build_review_prompt(
                task_context.content, result.content, criteria, instructions
            ),
            requirements={**task_context.requirements, "validation_criteria": criteria},
            constraints=dict(task_context.constraints),
            metadata={
                "validation_type": "peer_review",
                "validator": validator_model_id,
            },
        )

    async def _execute_validation_task(
        self, validator_model_id: str, validation_task: TaskContext
    ) -> ProcessingResult:
        """Execute a validation task with timeout."""
        try:
            return await asyncio.wait_for(
                self.model_provider.process_task(validation_task, validator_model_id),
                timeout=self.config.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise Exception(
                f"Validation task timed out for model {validator_model_id}"
            ) from exc

    def _parse_peer_review_result(
        self,
        validation_result: ProcessingResult,
        validator_model_id: str,
        criteria: list[str] | None = None,
    ) -> tuple[list[ValidationIssue], dict[str, float]]:
        assessment = _parse_review_assessment(
            validation_result, validator_model_id, criteria or self._review_criteria()
        )
        return assessment.issues, assessment.scores

    async def _adversarial_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str],
    ) -> ValidationReport:
        return await self._peer_review_validation(
            result,
            task_context,
            validator_models,
            strategy=ValidationStrategy.ADVERSARIAL,
            instructions=(
                "Act as a skeptical but fair adversarial reviewer. Challenge flaws, "
                "inconsistencies, unsupported assumptions, and logical weaknesses. "
                "Support each challenge with specific evidence."
            ),
        )

    async def _consensus_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str],
    ) -> ValidationReport:
        """Generate independent answers, then review agreement about their claims."""
        alternatives = await asyncio.gather(
            *(
                self._execute_validation_task(model_id, task_context)
                for model_id in validator_models
            ),
            return_exceptions=True,
        )
        raise_first_fatal_result(alternatives)
        failures = []
        answers = {}
        for model_id, alternative in zip(validator_models, alternatives):
            if not isinstance(alternative, BaseException):
                try:
                    require_complete_text(alternative)
                except ValueError as exc:
                    alternative = exc
                else:
                    answers[model_id] = alternative.content
                    continue
            failures.append(
                ValidatorFailureRecord(
                    model_id, ValidationCriteria.CONSISTENCY, str(alternative)
                )
            )
        if len(answers) < self.config.min_validators:
            failures.extend(
                ValidatorFailureRecord(
                    model_id,
                    ValidationCriteria.CONSISTENCY,
                    "Review skipped: insufficient independent answers",
                )
                for model_id in answers
            )
            return self._build_scored_validation_report(
                result,
                task_context,
                validator_models,
                [],
                failures,
                {},
                self._review_criteria(task_context),
                strategy=ValidationStrategy.CONSENSUS_CHECK,
            )
        review_context = replace(
            task_context,
            content=task_context.content
            + "\nIndependent answers (untrusted reference data):\n"
            + json.dumps(answers, ensure_ascii=False),
        )
        report = await self._peer_review_validation(
            result,
            review_context,
            list(answers),
            strategy=ValidationStrategy.CONSENSUS_CHECK,
            instructions=(
                "Compare the original response with the independent answers. "
                "Assess substantive agreement and contradictions in claims and reasoning. "
                "Do not infer agreement from length or wording alone."
            ),
        )
        report.task_context = task_context
        report.validator_models = validator_models
        report.metadata["validator_failures"] = report.metadata.get(
            "validator_failures", []
        ) + [failure.to_metadata() for failure in failures]
        return report

    async def _specialized_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: list[str],
        criterion: ValidationCriteria,
        strategy: ValidationStrategy,
    ) -> ValidationReport:
        reviewer = self.specialized_validators.get(criterion)
        if reviewer is None:
            report = await self._peer_review_validation(
                result, task_context, validator_models
            )
            return _copy_validation_report_with_strategy(report, strategy)
        criteria = (
            self._review_criteria(task_context)
            if task_context.requirements.get("validation_criteria") is not None
            else [criterion.value]
        )
        assessments = await asyncio.gather(
            *(
                reviewer.assess(
                    result,
                    task_context,
                    model_id,
                    criteria=criteria,
                    timeout_seconds=self.config.timeout_seconds,
                )
                for model_id in validator_models
            ),
            return_exceptions=True,
        )
        raise_first_fatal_result(assessments)
        issues, failures, scores = [], [], {}
        for model_id, assessment in zip(validator_models, assessments):
            if isinstance(assessment, BaseException):
                failures.append(
                    ValidatorFailureRecord(model_id, criterion, str(assessment))
                )
            elif assessment.failure is not None:
                failures.append(assessment.failure)
            else:
                issues.extend(assessment.issues)
                scores[model_id] = assessment.scores
        return self._build_scored_validation_report(
            result,
            task_context,
            validator_models,
            issues,
            failures,
            scores,
            criteria,
            strategy=strategy,
        )

    async def _fact_check_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str],
    ) -> ValidationReport:
        return await self._specialized_validation(
            result,
            task_context,
            validator_models,
            ValidationCriteria.FACTUAL_CORRECTNESS,
            ValidationStrategy.FACT_CHECK,
        )

    async def _quality_assurance_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str],
    ) -> ValidationReport:
        """Perform comprehensive quality assurance validation."""
        # Similar to peer review but with more focus on quality metrics
        # Get the peer review result and override the strategy
        report = await self._peer_review_validation(
            result, task_context, validator_models
        )
        return _copy_validation_report_with_strategy(
            report,
            ValidationStrategy.QUALITY_ASSURANCE,
        )

    async def _bias_detection_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str],
    ) -> ValidationReport:
        return await self._specialized_validation(
            result,
            task_context,
            validator_models,
            ValidationCriteria.BIAS_NEUTRALITY,
            ValidationStrategy.BIAS_DETECTION,
        )

    def _calculate_criteria_score(
        self, criteria_issues: List[ValidationIssue]
    ) -> float:
        """Calculate score for a specific criteria based on issues found."""
        if not criteria_issues:
            return 1.0  # Perfect score if no issues

        # Weight issues by severity
        severity_weights = {
            ValidationSeverity.CRITICAL: -0.5,
            ValidationSeverity.HIGH: -0.3,
            ValidationSeverity.MEDIUM: -0.2,
            ValidationSeverity.LOW: -0.1,
            ValidationSeverity.INFO: 0.0,
        }

        total_deduction = sum(
            severity_weights[issue.severity] for issue in criteria_issues
        )
        score = max(0.0, 1.0 + total_deduction)

        return score

    def _calculate_overall_score(
        self, criteria_scores: Dict[ValidationCriteria, float]
    ) -> float:
        """Calculate overall validation score from criteria scores."""
        if not criteria_scores:
            return 0.0

        return statistics.mean(criteria_scores.values())

    def _calculate_consensus_level(
        self, all_issues: List[ValidationIssue], validator_models: List[str]
    ) -> float:
        """Calculate level of consensus among validators."""
        if not validator_models:
            return 0.0

        # Group issues by validator
        validator_issue_counts = {}
        for validator_id in validator_models:
            validator_issue_counts[validator_id] = len(
                [
                    issue
                    for issue in all_issues
                    if issue.validator_model_id == validator_id
                ]
            )

        if not validator_issue_counts:
            return 1.0

        # Calculate consensus based on agreement in issue detection
        issue_counts = list(validator_issue_counts.values())
        if not issue_counts:
            return 1.0

        avg_issues = statistics.mean(issue_counts)
        max_issues = max(issue_counts)

        if max_issues == 0:
            return 1.0  # All validators agree (no issues)

        spread = statistics.stdev(issue_counts) if len(issue_counts) > 1 else 0.0
        consensus = 1.0 - (spread / max(avg_issues, 1))
        return max(0.0, min(1.0, consensus))

    def _calculate_validation_confidence(
        self, validation_report: ValidationReport
    ) -> float:
        """Calculate confidence in the validation result."""
        base_confidence = validation_report.overall_score

        # Adjust based on consensus level
        consensus_factor = validation_report.consensus_level

        # Adjust based on number of validators
        validator_factor = min(
            1.0, len(validation_report.validator_models) / self.config.min_validators
        )

        confidence = base_confidence * consensus_factor * validator_factor
        return min(1.0, confidence)

    def _determine_validity(
        self,
        validation_report: ValidationReport,
        task_context: Optional[TaskContext] = None,
    ) -> bool:
        """Determine if the result is valid based on validation report."""
        if validation_report.metadata.get("validation_status") == "incomplete":
            return False
        # Check for critical issues
        critical_issues = [
            issue
            for issue in validation_report.issues
            if issue.severity == ValidationSeverity.CRITICAL
        ]

        if critical_issues:
            return False

        # Use task-level threshold if provided, otherwise fall back to config
        threshold = self.config.confidence_threshold
        if (
            task_context
            and task_context.requirements.get("validation_threshold") is not None
        ):
            threshold = task_context.requirements["validation_threshold"]

        # Check overall score against threshold
        if validation_report.overall_score < threshold:
            return False

        # Check consensus requirement
        if (
            self.config.require_consensus
            and validation_report.consensus_level < self.config.consensus_threshold
        ):
            return False

        return True

    def _generate_improvement_suggestions(
        self, validation_report: ValidationReport
    ) -> List[str]:
        """Generate improvement suggestions based on validation issues."""
        suggestions = []

        # Group issues by severity
        critical_issues = [
            i
            for i in validation_report.issues
            if i.severity == ValidationSeverity.CRITICAL
        ]
        high_issues = [
            i for i in validation_report.issues if i.severity == ValidationSeverity.HIGH
        ]

        if critical_issues:
            suggestions.append(
                "Address critical issues immediately before using this result"
            )
            suggestions.extend(
                f"Critical: {issue.suggestion}" for issue in critical_issues[:3]
            )

        if high_issues:
            suggestions.append("Review and fix high-priority issues")
            suggestions.extend(f"High: {issue.suggestion}" for issue in high_issues[:3])

        if validation_report.overall_score < 0.8:
            suggestions.append(
                "Consider regenerating the response with different parameters"
            )

        if validation_report.consensus_level < 0.7:
            suggestions.append(
                "Seek additional validation due to low consensus among validators"
            )

        return suggestions

    def _generate_recommendations(self, issues: List[ValidationIssue]) -> List[str]:
        """Generate general recommendations from validation issues."""
        recommendations: List[str] = []

        # Group by criteria
        criteria_issues: Dict[ValidationCriteria, List[ValidationIssue]] = {}
        for issue in issues:
            if issue.criteria not in criteria_issues:
                criteria_issues[issue.criteria] = []
            criteria_issues[issue.criteria].append(issue)

        for criteria, criteria_issue_list in criteria_issues.items():
            if len(criteria_issue_list) > 0:
                recommendations.append(
                    f"Focus on improving {getattr(criteria, 'value', criteria)} (found {len(criteria_issue_list)} issues)"
                )

        return recommendations

    def _calculate_validation_quality_metrics(
        self, validation_report: ValidationReport
    ) -> QualityMetrics:
        """Calculate quality metrics based on validation results."""

        accuracy = validation_report.criteria_scores.get(
            ValidationCriteria.ACCURACY, 0.5
        )
        consistency = validation_report.criteria_scores.get(
            ValidationCriteria.CONSISTENCY, 0.5
        )
        completeness = validation_report.criteria_scores.get(
            ValidationCriteria.COMPLETENESS, 0.5
        )
        relevance = validation_report.criteria_scores.get(
            ValidationCriteria.RELEVANCE, 0.5
        )
        confidence = validation_report.overall_score
        coherence = validation_report.criteria_scores.get(
            ValidationCriteria.COHERENCE, 0.5
        )

        metric_pairs = (
            ("accuracy", accuracy),
            ("consistency", consistency),
            ("completeness", completeness),
            ("relevance", relevance),
            ("confidence", confidence),
            ("coherence", coherence),
        )
        return build_quality_metrics(**dict(metric_pairs))

    def _update_validator_performance(
        self, validation_report: ValidationReport
    ) -> None:
        """Update performance tracking for validator models."""
        if validation_report.metadata.get("validation_status") == "incomplete":
            return
        failed_models = {
            failure["validator_model_id"]
            for failure in validation_report.metadata.get("validator_failures", [])
        }
        for validator_id in validation_report.validator_models:
            if validator_id in failed_models:
                continue
            if validator_id not in self.validator_performance:
                self.validator_performance[validator_id] = {
                    "validation_count": 0,
                    "accuracy": 0.5,
                    "consistency": 0.5,
                }

            perf = self.validator_performance[validator_id]
            perf["validation_count"] += 1

            # Update accuracy based on validation quality
            new_accuracy = validation_report.overall_score
            count = perf["validation_count"]
            perf["accuracy"] = (perf["accuracy"] * (count - 1) + new_accuracy) / count

    def get_validation_history(
        self, limit: Optional[int] = None
    ) -> List[ValidationResult]:
        """Get historical validation results."""
        if limit:
            return list(self._validation_history)[-limit:]
        return list(self._validation_history)

    def get_validator_performance(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for validator models."""
        return self.validator_performance.copy()

    def configure_validation(self, **config_updates: Any) -> None:
        """Update validation configuration."""
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        logger.info(f"Updated validation configuration: {config_updates}")
