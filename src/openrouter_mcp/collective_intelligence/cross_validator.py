"""
Cross-Model Validation

This module implements comprehensive validation and quality assurance mechanisms
that use multiple models to cross-validate results, detect inconsistencies,
and improve overall output quality through peer review processes.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime
import statistics
import logging

from .base import (
    CollectiveIntelligenceComponent,
    TaskContext,
    ProcessingResult,
    ModelProvider,
    ModelInfo,
    QualityMetrics,
    TaskType,
    ModelCapability
)

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
    criteria: ValidationCriteria
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
    criteria: List[ValidationCriteria] = field(default_factory=lambda: [
        ValidationCriteria.ACCURACY,
        ValidationCriteria.CONSISTENCY,
        ValidationCriteria.COMPLETENESS,
        ValidationCriteria.RELEVANCE
    ])
    confidence_threshold: float = 0.7
    require_consensus: bool = False
    consensus_threshold: float = 0.6
    include_self_validation: bool = False
    timeout_seconds: float = 30.0
    specialized_validators: Dict[ValidationCriteria, List[str]] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Final result from cross-model validation."""
    task_id: str
    original_result: ProcessingResult
    validation_report: 'ValidationReport'
    is_valid: bool
    validation_confidence: float
    improvement_suggestions: List[str]
    quality_metrics: QualityMetrics
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ValidationReport:
    """Comprehensive validation report for a result."""
    original_result: ProcessingResult
    task_context: TaskContext
    validation_strategy: ValidationStrategy
    validator_models: List[str]
    issues: List[ValidationIssue]
    overall_score: float  # 0.0 to 1.0
    criteria_scores: Dict[ValidationCriteria, float]
    consensus_level: float  # Level of agreement among validators
    recommendations: List[str]
    revised_content: Optional[str] = None  # Improved version if available
    validation_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ValidationResult:
    """Result of the complete validation process."""
    task_id: str
    original_result: ProcessingResult
    validation_report: ValidationReport
    is_valid: bool
    validation_confidence: float
    improvement_suggestions: List[str]
    quality_metrics: QualityMetrics
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class SpecializedValidator:
    """Base class for specialized validation components."""
    
    def __init__(self, criteria: ValidationCriteria, model_provider: ModelProvider):
        self.criteria = criteria
        self.model_provider = model_provider
    
    async def validate(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_model_id: str
    ) -> List[ValidationIssue]:
        """Perform specialized validation."""
        raise NotImplementedError


class FactCheckValidator(SpecializedValidator):
    """Specialized validator for fact-checking."""
    
    def __init__(self, model_provider: ModelProvider):
        super().__init__(ValidationCriteria.FACTUAL_CORRECTNESS, model_provider)
    
    async def validate(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_model_id: str
    ) -> List[ValidationIssue]:
        """Validate factual accuracy of the result."""
        
        # Create fact-checking prompt
        fact_check_prompt = f"""
        Please fact-check the following response for accuracy:
        
        Original Task: {task_context.content}
        Response to Check: {result.content}
        
        Identify any factual errors, inaccuracies, or unsupported claims.
        For each issue found, provide:
        1. Description of the error
        2. Correct information if known
        3. Confidence level (0.0-1.0)
        
        Format your response as a structured analysis.
        """
        
        fact_check_task = TaskContext(
            task_id=f"fact_check_{result.task_id}",
            task_type=TaskType.FACTUAL,
            content=fact_check_prompt
        )
        
        try:
            validation_result = await self.model_provider.process_task(
                fact_check_task, validator_model_id
            )
            
            # Parse the validation result to extract issues
            issues = self._parse_fact_check_result(validation_result, validator_model_id)
            return issues
            
        except Exception as e:
            logger.warning(f"Fact-checking failed with model {validator_model_id}: {str(e)}")
            return []
    
    def _parse_fact_check_result(
        self, 
        validation_result: ProcessingResult, 
        validator_model_id: str
    ) -> List[ValidationIssue]:
        """Parse fact-checking result to extract validation issues."""
        issues = []
        
        # Simple parsing logic (would be more sophisticated in practice)
        content = validation_result.content.lower()
        
        if "error" in content or "incorrect" in content or "inaccurate" in content:
            issues.append(
                ValidationIssue(
                    issue_id=f"fact_check_{len(issues)}",
                    criteria=ValidationCriteria.FACTUAL_CORRECTNESS,
                    severity=ValidationSeverity.HIGH,
                    description="Potential factual inaccuracy detected",
                    suggestion="Verify facts and correct any inaccuracies",
                    confidence=validation_result.confidence,
                    evidence=validation_result.content[:200] + "...",
                    validator_model_id=validator_model_id
                )
            )
        
        return issues


class BiasDetectionValidator(SpecializedValidator):
    """Specialized validator for bias detection."""
    
    def __init__(self, model_provider: ModelProvider):
        super().__init__(ValidationCriteria.BIAS_NEUTRALITY, model_provider)
    
    async def validate(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_model_id: str
    ) -> List[ValidationIssue]:
        """Detect potential biases in the result."""
        
        bias_check_prompt = f"""
        Analyze the following response for potential biases:
        
        Original Task: {task_context.content}
        Response to Analyze: {result.content}
        
        Look for:
        1. Cultural, gender, racial, or other demographic biases
        2. Political or ideological biases
        3. Unfair generalizations or stereotypes
        4. Lack of diverse perspectives
        
        Identify any biases found and suggest improvements.
        """
        
        bias_check_task = TaskContext(
            task_id=f"bias_check_{result.task_id}",
            task_type=TaskType.ANALYSIS,
            content=bias_check_prompt
        )
        
        try:
            validation_result = await self.model_provider.process_task(
                bias_check_task, validator_model_id
            )
            
            issues = self._parse_bias_result(validation_result, validator_model_id)
            return issues
            
        except Exception as e:
            logger.warning(f"Bias detection failed with model {validator_model_id}: {str(e)}")
            return []
    
    def _parse_bias_result(
        self, 
        validation_result: ProcessingResult, 
        validator_model_id: str
    ) -> List[ValidationIssue]:
        """Parse bias detection result to extract issues."""
        issues = []
        
        content = validation_result.content.lower()
        
        bias_indicators = ["bias", "stereotype", "unfair", "prejudice", "discrimination"]
        
        if any(indicator in content for indicator in bias_indicators):
            issues.append(
                ValidationIssue(
                    issue_id=f"bias_check_{len(issues)}",
                    criteria=ValidationCriteria.BIAS_NEUTRALITY,
                    severity=ValidationSeverity.MEDIUM,
                    description="Potential bias detected in the response",
                    suggestion="Review and revise to ensure neutrality and fairness",
                    confidence=validation_result.confidence,
                    evidence=validation_result.content[:200] + "...",
                    validator_model_id=validator_model_id
                )
            )
        
        return issues


class CrossValidator(CollectiveIntelligenceComponent):
    """
    Cross-model validation system that uses multiple models to validate
    and improve the quality of AI-generated content.
    """
    
    def __init__(
        self,
        model_provider: ModelProvider,
        config: Optional[ValidationConfig] = None
    ):
        super().__init__(model_provider)
        self.config = config or ValidationConfig()
        
        # Specialized validators
        self.specialized_validators = {
            ValidationCriteria.FACTUAL_CORRECTNESS: FactCheckValidator(model_provider),
            ValidationCriteria.BIAS_NEUTRALITY: BiasDetectionValidator(model_provider)
        }
        
        # Validation history
        self.validation_history: List[ValidationResult] = []
        self.validator_performance: Dict[str, Dict[str, float]] = {}
    
    async def process(
        self, 
        result: ProcessingResult, 
        task_context: TaskContext,
        **kwargs
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
        start_time = datetime.now()
        
        try:
            # Select validator models
            validator_models = await self._select_validator_models(result, task_context)
            
            # Perform validation using selected strategy
            validation_report = await self._perform_validation(
                result, task_context, validator_models
            )
            
            # Calculate overall validation metrics
            validation_confidence = self._calculate_validation_confidence(validation_report)
            is_valid = self._determine_validity(validation_report)
            improvement_suggestions = self._generate_improvement_suggestions(validation_report)
            quality_metrics = self._calculate_validation_quality_metrics(validation_report)
            
            # Create final validation result
            processing_time = (datetime.now() - start_time).total_seconds()
            
            validation_result = ValidationResult(
                task_id=task_context.task_id,
                original_result=result,
                validation_report=validation_report,
                is_valid=is_valid,
                validation_confidence=validation_confidence,
                improvement_suggestions=improvement_suggestions,
                quality_metrics=quality_metrics,
                processing_time=processing_time,
                metadata={
                    'validator_count': len(validator_models),
                    'total_issues': len(validation_report.issues),
                    'critical_issues': len([i for i in validation_report.issues 
                                          if i.severity == ValidationSeverity.CRITICAL])
                }
            )
            
            # Update validation history and metrics
            self.validation_history.append(validation_result)
            self._update_validator_performance(validation_report)
            
            logger.info(
                f"Validation completed for task {task_context.task_id}: "
                f"{'VALID' if is_valid else 'INVALID'} "
                f"(confidence: {validation_confidence:.3f}, "
                f"issues: {len(validation_report.issues)})"
            )
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Validation failed for task {task_context.task_id}: {str(e)}")
            raise
    
    async def _select_validator_models(
        self, 
        result: ProcessingResult, 
        task_context: TaskContext
    ) -> List[str]:
        """Select appropriate validator models."""
        available_models = await self.model_provider.get_available_models()
        
        # Filter out the original model if self-validation is disabled
        if not self.config.include_self_validation:
            available_models = [
                model for model in available_models 
                if model.model_id != result.model_id
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
            if model_id not in [m[0] for m in scored_models]:
                scored_models.append((model_id, 0.9))  # High score for specialized validators
        
        # Sort by score and select top validators
        scored_models.sort(key=lambda x: x[1], reverse=True)
        
        selected_count = min(
            max(self.config.min_validators, len(scored_models)),
            self.config.max_validators
        )
        
        validator_models = [model_id for model_id, _ in scored_models[:selected_count]]
        
        logger.info(f"Selected {len(validator_models)} validators: {validator_models}")
        
        return validator_models
    
    def _calculate_validator_suitability(
        self, 
        model: ModelInfo, 
        task_context: TaskContext, 
        result: ProcessingResult
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
            performance_bonus = perf.get('accuracy', 0.0) * 0.2
        
        return min(1.0, base_score + accuracy_bonus + capability_bonus + performance_bonus)
    
    async def _perform_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str]
    ) -> ValidationReport:
        """Perform the actual validation using selected models."""
        
        if self.config.strategy == ValidationStrategy.PEER_REVIEW:
            return await self._peer_review_validation(result, task_context, validator_models)
        elif self.config.strategy == ValidationStrategy.ADVERSARIAL:
            return await self._adversarial_validation(result, task_context, validator_models)
        elif self.config.strategy == ValidationStrategy.CONSENSUS_CHECK:
            return await self._consensus_validation(result, task_context, validator_models)
        elif self.config.strategy == ValidationStrategy.FACT_CHECK:
            return await self._fact_check_validation(result, task_context, validator_models)
        elif self.config.strategy == ValidationStrategy.QUALITY_ASSURANCE:
            return await self._quality_assurance_validation(result, task_context, validator_models)
        elif self.config.strategy == ValidationStrategy.BIAS_DETECTION:
            return await self._bias_detection_validation(result, task_context, validator_models)
        else:
            # Default to peer review
            return await self._peer_review_validation(result, task_context, validator_models)
    
    async def _peer_review_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str]
    ) -> ValidationReport:
        """Perform peer review validation."""
        
        all_issues = []
        criteria_scores = {}
        
        # Create validation tasks for each validator
        validation_tasks = []
        for validator_model_id in validator_models:
            task = self._create_peer_review_task(result, task_context, validator_model_id)
            validation_tasks.append((validator_model_id, task))
        
        # Execute validation tasks concurrently
        validation_results = await asyncio.gather(
            *[self._execute_validation_task(model_id, task) 
              for model_id, task in validation_tasks],
            return_exceptions=True
        )
        
        # Process validation results
        for i, validation_result in enumerate(validation_results):
            if isinstance(validation_result, Exception):
                logger.warning(f"Validation failed for validator {validator_models[i]}: {str(validation_result)}")
                continue
            
            validator_model_id = validator_models[i]
            issues = self._parse_peer_review_result(validation_result, validator_model_id)
            all_issues.extend(issues)
        
        # Calculate criteria scores
        for criteria in self.config.criteria:
            criteria_issues = [issue for issue in all_issues if issue.criteria == criteria]
            criteria_scores[criteria] = self._calculate_criteria_score(criteria_issues)
        
        # Calculate overall score and consensus
        overall_score = self._calculate_overall_score(criteria_scores)
        consensus_level = self._calculate_consensus_level(all_issues, validator_models)
        
        return ValidationReport(
            original_result=result,
            task_context=task_context,
            validation_strategy=self.config.strategy,
            validator_models=validator_models,
            issues=all_issues,
            overall_score=overall_score,
            criteria_scores=criteria_scores,
            consensus_level=consensus_level,
            recommendations=self._generate_recommendations(all_issues)
        )
    
    def _create_peer_review_task(
        self, 
        result: ProcessingResult, 
        task_context: TaskContext, 
        validator_model_id: str
    ) -> TaskContext:
        """Create a peer review validation task."""
        
        criteria_text = ", ".join([c.value for c in self.config.criteria])
        
        review_prompt = f"""
        Please review the following AI-generated response for quality and accuracy:
        
        Original Task: {task_context.content}
        Response to Review: {result.content}
        
        Evaluate the response based on these criteria: {criteria_text}
        
        For each criterion, provide:
        1. A score from 0.0 to 1.0
        2. Specific issues or concerns (if any)
        3. Suggestions for improvement
        
        Focus on being constructive and specific in your feedback.
        """
        
        return TaskContext(
            task_id=f"peer_review_{result.task_id}_{validator_model_id}",
            task_type=TaskType.ANALYSIS,
            content=review_prompt,
            metadata={'validation_type': 'peer_review', 'validator': validator_model_id}
        )
    
    async def _execute_validation_task(
        self, 
        validator_model_id: str, 
        validation_task: TaskContext
    ) -> ProcessingResult:
        """Execute a validation task with timeout."""
        try:
            return await asyncio.wait_for(
                self.model_provider.process_task(validation_task, validator_model_id),
                timeout=self.config.timeout_seconds
            )
        except asyncio.TimeoutError:
            raise Exception(f"Validation task timed out for model {validator_model_id}")
    
    def _parse_peer_review_result(
        self, 
        validation_result: ProcessingResult, 
        validator_model_id: str
    ) -> List[ValidationIssue]:
        """Parse peer review result to extract validation issues."""
        issues = []
        content = validation_result.content.lower()
        
        # Simple parsing logic (would be more sophisticated in practice)
        issue_indicators = {
            "error": ValidationSeverity.HIGH,
            "incorrect": ValidationSeverity.HIGH,
            "inaccurate": ValidationSeverity.MEDIUM,
            "unclear": ValidationSeverity.MEDIUM,
            "improve": ValidationSeverity.LOW,
            "suggest": ValidationSeverity.LOW
        }
        
        for indicator, severity in issue_indicators.items():
            if indicator in content:
                # Extract context around the indicator
                start_idx = max(0, content.find(indicator) - 50)
                end_idx = min(len(content), content.find(indicator) + 100)
                context = validation_result.content[start_idx:end_idx]
                
                issues.append(
                    ValidationIssue(
                        issue_id=f"peer_review_{len(issues)}_{validator_model_id}",
                        criteria=ValidationCriteria.ACCURACY,  # Default, would be more specific
                        severity=severity,
                        description=f"Peer reviewer identified: {indicator}",
                        suggestion="Review and address the identified concern",
                        confidence=validation_result.confidence,
                        evidence=context,
                        validator_model_id=validator_model_id
                    )
                )
        
        return issues
    
    async def _adversarial_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str]
    ) -> ValidationReport:
        """Perform adversarial validation where models challenge the result."""
        
        adversarial_prompt = f"""
        Act as a critical reviewer and challenge the following response:
        
        Original Task: {task_context.content}
        Response to Challenge: {result.content}
        
        Your goal is to find flaws, inconsistencies, or weaknesses in the response.
        Be thorough and skeptical, but fair in your criticism.
        Identify specific issues and provide evidence for your challenges.
        """
        
        all_issues = []
        
        for validator_model_id in validator_models:
            adversarial_task = TaskContext(
                task_id=f"adversarial_{result.task_id}_{validator_model_id}",
                task_type=TaskType.ANALYSIS,
                content=adversarial_prompt
            )
            
            try:
                validation_result = await self._execute_validation_task(
                    validator_model_id, adversarial_task
                )
                issues = self._parse_adversarial_result(validation_result, validator_model_id)
                all_issues.extend(issues)
                
            except Exception as e:
                logger.warning(f"Adversarial validation failed for {validator_model_id}: {str(e)}")
        
        # Create validation report
        criteria_scores = {}
        for criteria in self.config.criteria:
            criteria_issues = [issue for issue in all_issues if issue.criteria == criteria]
            criteria_scores[criteria] = self._calculate_criteria_score(criteria_issues)
        
        overall_score = self._calculate_overall_score(criteria_scores)
        consensus_level = self._calculate_consensus_level(all_issues, validator_models)
        
        return ValidationReport(
            original_result=result,
            task_context=task_context,
            validation_strategy=self.config.strategy,
            validator_models=validator_models,
            issues=all_issues,
            overall_score=overall_score,
            criteria_scores=criteria_scores,
            consensus_level=consensus_level,
            recommendations=self._generate_recommendations(all_issues)
        )
    
    def _parse_adversarial_result(
        self, 
        validation_result: ProcessingResult, 
        validator_model_id: str
    ) -> List[ValidationIssue]:
        """Parse adversarial validation result."""
        issues = []
        content = validation_result.content.lower()
        
        # Look for adversarial challenge indicators
        challenge_indicators = ["flaw", "inconsist", "weak", "question", "challenge", "doubt"]
        
        for indicator in challenge_indicators:
            if indicator in content:
                issues.append(
                    ValidationIssue(
                        issue_id=f"adversarial_{len(issues)}_{validator_model_id}",
                        criteria=ValidationCriteria.LOGICAL_SOUNDNESS,
                        severity=ValidationSeverity.MEDIUM,
                        description=f"Adversarial challenge: {indicator} identified",
                        suggestion="Address the adversarial challenge raised",
                        confidence=validation_result.confidence,
                        evidence=validation_result.content[:300] + "...",
                        validator_model_id=validator_model_id
                    )
                )
        
        return issues
    
    async def _consensus_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str]
    ) -> ValidationReport:
        """Validate by checking consensus among multiple responses."""
        
        # Generate alternative responses from validators
        alternative_responses = []
        
        for validator_model_id in validator_models:
            try:
                alternative_result = await self.model_provider.process_task(
                    task_context, validator_model_id
                )
                alternative_responses.append((validator_model_id, alternative_result))
                
            except Exception as e:
                logger.warning(f"Failed to generate alternative response from {validator_model_id}: {str(e)}")
        
        # Compare original result with alternatives
        issues = self._compare_for_consensus(result, alternative_responses)
        
        # Calculate consensus metrics
        consensus_level = len(alternative_responses) / max(len(validator_models), 1)
        
        criteria_scores = {criteria: 0.8 for criteria in self.config.criteria}  # Default scores
        overall_score = consensus_level
        
        return ValidationReport(
            original_result=result,
            task_context=task_context,
            validation_strategy=self.config.strategy,
            validator_models=validator_models,
            issues=issues,
            overall_score=overall_score,
            criteria_scores=criteria_scores,
            consensus_level=consensus_level,
            recommendations=self._generate_recommendations(issues)
        )
    
    def _compare_for_consensus(
        self, 
        original_result: ProcessingResult, 
        alternative_responses: List[Tuple[str, ProcessingResult]]
    ) -> List[ValidationIssue]:
        """Compare original result with alternatives to find consensus issues."""
        issues = []
        
        if len(alternative_responses) < 2:
            issues.append(
                ValidationIssue(
                    issue_id="consensus_insufficient",
                    criteria=ValidationCriteria.CONSISTENCY,
                    severity=ValidationSeverity.MEDIUM,
                    description="Insufficient alternative responses for consensus validation",
                    suggestion="Increase the number of validator models",
                    confidence=1.0,
                    evidence="",
                    validator_model_id="system"
                )
            )
            return issues
        
        # Simple consensus check based on response length similarity
        original_length = len(original_result.content)
        alternative_lengths = [len(resp[1].content) for resp in alternative_responses]
        
        avg_alternative_length = statistics.mean(alternative_lengths)
        length_diff_ratio = abs(original_length - avg_alternative_length) / max(avg_alternative_length, 1)
        
        if length_diff_ratio > 0.5:  # Significant length difference
            issues.append(
                ValidationIssue(
                    issue_id="consensus_length_outlier",
                    criteria=ValidationCriteria.COMPLETENESS,
                    severity=ValidationSeverity.MEDIUM,
                    description="Response length significantly differs from consensus",
                    suggestion="Review completeness compared to alternative responses",
                    confidence=0.7,
                    evidence=f"Original: {original_length} chars, Average alternative: {avg_alternative_length:.0f} chars",
                    validator_model_id="consensus_checker"
                )
            )
        
        return issues
    
    async def _fact_check_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str]
    ) -> ValidationReport:
        """Perform specialized fact-checking validation."""
        
        if ValidationCriteria.FACTUAL_CORRECTNESS in self.specialized_validators:
            fact_checker = self.specialized_validators[ValidationCriteria.FACTUAL_CORRECTNESS]
            all_issues = []
            
            for validator_model_id in validator_models:
                try:
                    issues = await fact_checker.validate(result, task_context, validator_model_id)
                    all_issues.extend(issues)
                except Exception as e:
                    logger.warning(f"Fact-checking failed with {validator_model_id}: {str(e)}")
            
            criteria_scores = {ValidationCriteria.FACTUAL_CORRECTNESS: self._calculate_criteria_score(all_issues)}
            overall_score = criteria_scores[ValidationCriteria.FACTUAL_CORRECTNESS]
            
            return ValidationReport(
                original_result=result,
                task_context=task_context,
                validation_strategy=self.config.strategy,
                validator_models=validator_models,
                issues=all_issues,
                overall_score=overall_score,
                criteria_scores=criteria_scores,
                consensus_level=1.0,  # Single criteria validation
                recommendations=self._generate_recommendations(all_issues)
            )
        else:
            # Fallback to peer review
            return await self._peer_review_validation(result, task_context, validator_models)
    
    async def _quality_assurance_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str]
    ) -> ValidationReport:
        """Perform comprehensive quality assurance validation."""
        # Similar to peer review but with more focus on quality metrics
        return await self._peer_review_validation(result, task_context, validator_models)
    
    async def _bias_detection_validation(
        self,
        result: ProcessingResult,
        task_context: TaskContext,
        validator_models: List[str]
    ) -> ValidationReport:
        """Perform bias detection validation."""
        
        if ValidationCriteria.BIAS_NEUTRALITY in self.specialized_validators:
            bias_detector = self.specialized_validators[ValidationCriteria.BIAS_NEUTRALITY]
            all_issues = []
            
            for validator_model_id in validator_models:
                try:
                    issues = await bias_detector.validate(result, task_context, validator_model_id)
                    all_issues.extend(issues)
                except Exception as e:
                    logger.warning(f"Bias detection failed with {validator_model_id}: {str(e)}")
            
            criteria_scores = {ValidationCriteria.BIAS_NEUTRALITY: self._calculate_criteria_score(all_issues)}
            overall_score = criteria_scores[ValidationCriteria.BIAS_NEUTRALITY]
            
            return ValidationReport(
                original_result=result,
                task_context=task_context,
                validation_strategy=self.config.strategy,
                validator_models=validator_models,
                issues=all_issues,
                overall_score=overall_score,
                criteria_scores=criteria_scores,
                consensus_level=1.0,
                recommendations=self._generate_recommendations(all_issues)
            )
        else:
            return await self._peer_review_validation(result, task_context, validator_models)
    
    def _calculate_criteria_score(self, criteria_issues: List[ValidationIssue]) -> float:
        """Calculate score for a specific criteria based on issues found."""
        if not criteria_issues:
            return 1.0  # Perfect score if no issues
        
        # Weight issues by severity
        severity_weights = {
            ValidationSeverity.CRITICAL: -0.5,
            ValidationSeverity.HIGH: -0.3,
            ValidationSeverity.MEDIUM: -0.2,
            ValidationSeverity.LOW: -0.1,
            ValidationSeverity.INFO: 0.0
        }
        
        total_deduction = sum(severity_weights[issue.severity] for issue in criteria_issues)
        score = max(0.0, 1.0 + total_deduction)
        
        return score
    
    def _calculate_overall_score(self, criteria_scores: Dict[ValidationCriteria, float]) -> float:
        """Calculate overall validation score from criteria scores."""
        if not criteria_scores:
            return 0.0
        
        return statistics.mean(criteria_scores.values())
    
    def _calculate_consensus_level(
        self, 
        all_issues: List[ValidationIssue], 
        validator_models: List[str]
    ) -> float:
        """Calculate level of consensus among validators."""
        if not validator_models:
            return 0.0
        
        # Group issues by validator
        validator_issue_counts = {}
        for validator_id in validator_models:
            validator_issue_counts[validator_id] = len([
                issue for issue in all_issues 
                if issue.validator_model_id == validator_id
            ])
        
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
        
        consensus = 1.0 - (statistics.stdev(issue_counts) / max(avg_issues, 1))
        return max(0.0, min(1.0, consensus))
    
    def _calculate_validation_confidence(self, validation_report: ValidationReport) -> float:
        """Calculate confidence in the validation result."""
        base_confidence = validation_report.overall_score
        
        # Adjust based on consensus level
        consensus_factor = validation_report.consensus_level
        
        # Adjust based on number of validators
        validator_factor = min(1.0, len(validation_report.validator_models) / self.config.min_validators)
        
        confidence = base_confidence * consensus_factor * validator_factor
        return min(1.0, confidence)
    
    def _determine_validity(self, validation_report: ValidationReport) -> bool:
        """Determine if the result is valid based on validation report."""
        # Check for critical issues
        critical_issues = [
            issue for issue in validation_report.issues 
            if issue.severity == ValidationSeverity.CRITICAL
        ]
        
        if critical_issues:
            return False
        
        # Check overall score against threshold
        if validation_report.overall_score < self.config.confidence_threshold:
            return False
        
        # Check consensus requirement
        if self.config.require_consensus:
            if validation_report.consensus_level < self.config.consensus_threshold:
                return False
        
        return True
    
    def _generate_improvement_suggestions(self, validation_report: ValidationReport) -> List[str]:
        """Generate improvement suggestions based on validation issues."""
        suggestions = []
        
        # Group issues by severity
        critical_issues = [i for i in validation_report.issues if i.severity == ValidationSeverity.CRITICAL]
        high_issues = [i for i in validation_report.issues if i.severity == ValidationSeverity.HIGH]
        
        if critical_issues:
            suggestions.append("Address critical issues immediately before using this result")
            for issue in critical_issues[:3]:  # Top 3 critical issues
                suggestions.append(f"Critical: {issue.suggestion}")
        
        if high_issues:
            suggestions.append("Review and fix high-priority issues")
            for issue in high_issues[:3]:  # Top 3 high issues
                suggestions.append(f"High: {issue.suggestion}")
        
        if validation_report.overall_score < 0.8:
            suggestions.append("Consider regenerating the response with different parameters")
        
        if validation_report.consensus_level < 0.7:
            suggestions.append("Seek additional validation due to low consensus among validators")
        
        return suggestions
    
    def _generate_recommendations(self, issues: List[ValidationIssue]) -> List[str]:
        """Generate general recommendations from validation issues."""
        recommendations = []
        
        # Group by criteria
        criteria_issues = {}
        for issue in issues:
            if issue.criteria not in criteria_issues:
                criteria_issues[issue.criteria] = []
            criteria_issues[issue.criteria].append(issue)
        
        for criteria, criteria_issue_list in criteria_issues.items():
            if len(criteria_issue_list) > 0:
                recommendations.append(
                    f"Focus on improving {criteria.value} (found {len(criteria_issue_list)} issues)"
                )
        
        return recommendations
    
    def _calculate_validation_quality_metrics(self, validation_report: ValidationReport) -> QualityMetrics:
        """Calculate quality metrics based on validation results."""
        
        accuracy = validation_report.criteria_scores.get(ValidationCriteria.ACCURACY, 0.5)
        consistency = validation_report.criteria_scores.get(ValidationCriteria.CONSISTENCY, 0.5)
        completeness = validation_report.criteria_scores.get(ValidationCriteria.COMPLETENESS, 0.5)
        relevance = validation_report.criteria_scores.get(ValidationCriteria.RELEVANCE, 0.5)
        confidence = validation_report.overall_score
        coherence = validation_report.criteria_scores.get(ValidationCriteria.COHERENCE, 0.5)
        
        return QualityMetrics(
            accuracy=accuracy,
            consistency=consistency,
            completeness=completeness,
            relevance=relevance,
            confidence=confidence,
            coherence=coherence
        )
    
    def _update_validator_performance(self, validation_report: ValidationReport) -> None:
        """Update performance tracking for validator models."""
        for validator_id in validation_report.validator_models:
            if validator_id not in self.validator_performance:
                self.validator_performance[validator_id] = {
                    'validation_count': 0,
                    'accuracy': 0.5,
                    'consistency': 0.5
                }
            
            perf = self.validator_performance[validator_id]
            perf['validation_count'] += 1
            
            # Update accuracy based on validation quality
            new_accuracy = validation_report.overall_score
            count = perf['validation_count']
            perf['accuracy'] = (perf['accuracy'] * (count - 1) + new_accuracy) / count
    
    def get_validation_history(self, limit: Optional[int] = None) -> List[ValidationResult]:
        """Get historical validation results."""
        if limit:
            return self.validation_history[-limit:]
        return self.validation_history.copy()
    
    def get_validator_performance(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for validator models."""
        return self.validator_performance.copy()
    
    def configure_validation(self, **config_updates) -> None:
        """Update validation configuration."""
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        logger.info(f"Updated validation configuration: {config_updates}")