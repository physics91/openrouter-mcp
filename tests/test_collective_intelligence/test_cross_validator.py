"""
Comprehensive test suite for the Cross-Model Validation module.

This module provides thorough testing of the cross-validation functionality
including peer review, adversarial validation, and specialized validators.
"""

import asyncio
import pytest
from datetime import datetime
from typing import List
from unittest.mock import AsyncMock, Mock

from src.openrouter_mcp.collective_intelligence.cross_validator import (
    CrossValidator, ValidationConfig, ValidationStrategy, ValidationCriteria,
    ValidationSeverity, ValidationIssue, ValidationReport, ValidationResult,
    FactCheckValidator, BiasDetectionValidator
)
from src.openrouter_mcp.collective_intelligence.base import (
    TaskContext, ProcessingResult, ModelInfo, TaskType, QualityMetrics
)


class TestValidationIssue:
    """Test suite for ValidationIssue dataclass."""

    @pytest.mark.unit
    def test_validation_issue_creation(self):
        """Test ValidationIssue creation and attributes."""
        issue = ValidationIssue(
            issue_id="test_issue_1",
            criteria=ValidationCriteria.ACCURACY,
            severity=ValidationSeverity.HIGH,
            description="Test validation issue",
            suggestion="Fix the issue",
            confidence=0.85,
            evidence="Supporting evidence",
            validator_model_id="test_validator"
        )
        
        assert issue.issue_id == "test_issue_1"
        assert issue.criteria == ValidationCriteria.ACCURACY
        assert issue.severity == ValidationSeverity.HIGH
        assert issue.description == "Test validation issue"
        assert issue.suggestion == "Fix the issue"
        assert issue.confidence == 0.85
        assert issue.evidence == "Supporting evidence"
        assert issue.validator_model_id == "test_validator"
        assert issue.line_numbers is None
        assert isinstance(issue.metadata, dict)


class TestValidationConfig:
    """Test suite for ValidationConfig dataclass."""

    @pytest.mark.unit
    def test_default_validation_config(self):
        """Test default ValidationConfig initialization."""
        config = ValidationConfig()
        
        assert config.strategy == ValidationStrategy.PEER_REVIEW
        assert config.min_validators == 2
        assert config.max_validators == 4
        assert ValidationCriteria.ACCURACY in config.criteria
        assert config.confidence_threshold == 0.7
        assert config.require_consensus is False
        assert config.consensus_threshold == 0.6
        assert config.include_self_validation is False
        assert config.timeout_seconds == 30.0

    @pytest.mark.unit
    def test_custom_validation_config(self):
        """Test ValidationConfig with custom values."""
        config = ValidationConfig(
            strategy=ValidationStrategy.ADVERSARIAL,
            min_validators=3,
            max_validators=6,
            criteria=[ValidationCriteria.FACTUAL_CORRECTNESS, ValidationCriteria.BIAS_NEUTRALITY],
            confidence_threshold=0.8,
            require_consensus=True,
            consensus_threshold=0.75
        )
        
        assert config.strategy == ValidationStrategy.ADVERSARIAL
        assert config.min_validators == 3
        assert config.max_validators == 6
        assert len(config.criteria) == 2
        assert ValidationCriteria.FACTUAL_CORRECTNESS in config.criteria
        assert config.confidence_threshold == 0.8
        assert config.require_consensus is True
        assert config.consensus_threshold == 0.75


class TestFactCheckValidator:
    """Test suite for FactCheckValidator."""

    @pytest.mark.unit
    def test_fact_check_validator_initialization(self, mock_model_provider):
        """Test FactCheckValidator initialization."""
        validator = FactCheckValidator(mock_model_provider)
        
        assert validator.criteria == ValidationCriteria.FACTUAL_CORRECTNESS
        assert validator.model_provider == mock_model_provider

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_fact_check_validate_success(self, mock_model_provider, sample_task, sample_processing_results):
        """Test successful fact-checking validation."""
        validator = FactCheckValidator(mock_model_provider)
        result = sample_processing_results[0]
        
        # Mock fact-check response indicating issues
        fact_check_response = ProcessingResult(
            task_id="fact_check_test",
            model_id="fact_checker",
            content="Found several factual errors and inaccuracies in the response",
            confidence=0.9
        )
        
        mock_model_provider.process_task.return_value = fact_check_response
        
        issues = await validator.validate(result, sample_task, "fact_checker_model")
        
        assert isinstance(issues, list)
        assert len(issues) > 0  # Should find issues based on content
        
        for issue in issues:
            assert isinstance(issue, ValidationIssue)
            assert issue.criteria == ValidationCriteria.FACTUAL_CORRECTNESS
            assert issue.validator_model_id == "fact_checker_model"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_fact_check_validate_no_issues(self, mock_model_provider, sample_task, sample_processing_results):
        """Test fact-checking when no issues are found."""
        validator = FactCheckValidator(mock_model_provider)
        result = sample_processing_results[0]
        
        # Mock fact-check response indicating no issues
        fact_check_response = ProcessingResult(
            task_id="fact_check_test",
            model_id="fact_checker",
            content="The response appears to be factually accurate with no errors detected",
            confidence=0.9
        )
        
        mock_model_provider.process_task.return_value = fact_check_response
        
        issues = await validator.validate(result, sample_task, "fact_checker_model")
        
        assert isinstance(issues, list)
        assert len(issues) == 0  # Should find no issues

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_fact_check_validate_failure(self, mock_model_provider, sample_task, sample_processing_results):
        """Test fact-checking when validation fails."""
        validator = FactCheckValidator(mock_model_provider)
        result = sample_processing_results[0]
        
        # Mock provider failure
        mock_model_provider.process_task.side_effect = Exception("Validation failed")
        
        issues = await validator.validate(result, sample_task, "fact_checker_model")
        
        assert isinstance(issues, list)
        assert len(issues) == 0  # Should return empty list on failure


class TestBiasDetectionValidator:
    """Test suite for BiasDetectionValidator."""

    @pytest.mark.unit
    def test_bias_detection_validator_initialization(self, mock_model_provider):
        """Test BiasDetectionValidator initialization."""
        validator = BiasDetectionValidator(mock_model_provider)
        
        assert validator.criteria == ValidationCriteria.BIAS_NEUTRALITY
        assert validator.model_provider == mock_model_provider

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_bias_detection_validate_bias_found(self, mock_model_provider, sample_task, sample_processing_results):
        """Test bias detection when bias is found."""
        validator = BiasDetectionValidator(mock_model_provider)
        result = sample_processing_results[0]
        
        # Mock bias detection response indicating bias
        bias_check_response = ProcessingResult(
            task_id="bias_check_test",
            model_id="bias_detector",
            content="The response shows cultural bias and unfair stereotypes in its analysis",
            confidence=0.8
        )
        
        mock_model_provider.process_task.return_value = bias_check_response
        
        issues = await validator.validate(result, sample_task, "bias_detector_model")
        
        assert isinstance(issues, list)
        assert len(issues) > 0  # Should find bias issues
        
        for issue in issues:
            assert isinstance(issue, ValidationIssue)
            assert issue.criteria == ValidationCriteria.BIAS_NEUTRALITY
            assert issue.validator_model_id == "bias_detector_model"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_bias_detection_validate_no_bias(self, mock_model_provider, sample_task, sample_processing_results):
        """Test bias detection when no bias is found."""
        validator = BiasDetectionValidator(mock_model_provider)
        result = sample_processing_results[0]
        
        # Mock bias detection response indicating no bias
        bias_check_response = ProcessingResult(
            task_id="bias_check_test",
            model_id="bias_detector",
            content="The response appears neutral and fair with no detectable bias",
            confidence=0.9
        )
        
        mock_model_provider.process_task.return_value = bias_check_response
        
        issues = await validator.validate(result, sample_task, "bias_detector_model")
        
        assert isinstance(issues, list)
        assert len(issues) == 0  # Should find no bias issues


class TestCrossValidator:
    """Test suite for the CrossValidator class."""

    @pytest.mark.unit
    def test_cross_validator_initialization(self, mock_model_provider):
        """Test CrossValidator initialization."""
        validator = CrossValidator(mock_model_provider)
        
        assert validator.model_provider == mock_model_provider
        assert isinstance(validator.config, ValidationConfig)
        assert isinstance(validator.specialized_validators, dict)
        assert ValidationCriteria.FACTUAL_CORRECTNESS in validator.specialized_validators
        assert ValidationCriteria.BIAS_NEUTRALITY in validator.specialized_validators
        assert isinstance(validator.validation_history, list)
        assert len(validator.validation_history) == 0

    @pytest.mark.unit
    def test_cross_validator_with_custom_config(self, mock_model_provider):
        """Test CrossValidator with custom configuration."""
        config = ValidationConfig(
            strategy=ValidationStrategy.FACT_CHECK,
            min_validators=1,
            max_validators=2
        )
        
        validator = CrossValidator(mock_model_provider, config)
        
        assert validator.config == config
        assert validator.config.strategy == ValidationStrategy.FACT_CHECK

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_select_validator_models(self, mock_model_provider, sample_models, sample_task, sample_processing_results):
        """Test validator model selection."""
        validator = CrossValidator(mock_model_provider)
        result = sample_processing_results[0]
        
        mock_model_provider.get_available_models.return_value = sample_models
        
        validator_models = await validator._select_validator_models(result, sample_task)
        
        assert isinstance(validator_models, list)
        assert len(validator_models) >= validator.config.min_validators
        assert len(validator_models) <= validator.config.max_validators
        assert all(isinstance(model_id, str) for model_id in validator_models)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_select_validator_models_exclude_self(self, mock_model_provider, sample_models, sample_task, sample_processing_results):
        """Test that validator selection excludes the original model when self-validation is disabled."""
        config = ValidationConfig(include_self_validation=False)
        validator = CrossValidator(mock_model_provider, config)
        result = sample_processing_results[0]
        
        mock_model_provider.get_available_models.return_value = sample_models
        
        validator_models = await validator._select_validator_models(result, sample_task)
        
        # Should not include the original model
        assert result.model_id not in validator_models

    @pytest.mark.unit
    def test_calculate_validator_suitability(self, mock_model_provider, sample_models, sample_task, sample_processing_results):
        """Test validator suitability calculation."""
        validator = CrossValidator(mock_model_provider)
        model = sample_models[0]
        result = sample_processing_results[0]
        
        suitability = validator._calculate_validator_suitability(model, sample_task, result)
        
        assert isinstance(suitability, float)
        assert 0.0 <= suitability <= 1.0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_peer_review_validation(self, mock_model_provider, sample_task, sample_processing_results):
        """Test peer review validation strategy."""
        validator = CrossValidator(mock_model_provider)
        result = sample_processing_results[0]
        
        # Mock validator models
        validator_models = ["validator_1", "validator_2"]
        
        # Mock validation responses
        validation_responses = [
            ProcessingResult(
                task_id="peer_review_1",
                model_id="validator_1",
                content="The response has some accuracy issues and could be improved",
                confidence=0.8
            ),
            ProcessingResult(
                task_id="peer_review_2",
                model_id="validator_2",
                content="Overall good response with minor suggestions for clarity",
                confidence=0.85
            )
        ]
        
        mock_model_provider.process_task.side_effect = validation_responses
        
        validation_report = await validator._peer_review_validation(result, sample_task, validator_models)
        
        assert isinstance(validation_report, ValidationReport)
        assert validation_report.validation_strategy == ValidationStrategy.PEER_REVIEW
        assert validation_report.validator_models == validator_models
        assert len(validation_report.issues) >= 0
        assert 0.0 <= validation_report.overall_score <= 1.0
        assert 0.0 <= validation_report.consensus_level <= 1.0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_adversarial_validation(self, mock_model_provider, sample_task, sample_processing_results):
        """Test adversarial validation strategy."""
        validator = CrossValidator(mock_model_provider)
        result = sample_processing_results[0]
        validator_models = ["adversary_1", "adversary_2"]
        
        # Mock adversarial responses
        adversarial_responses = [
            ProcessingResult(
                task_id="adversarial_1",
                model_id="adversary_1",
                content="I challenge this response because it has logical flaws and inconsistencies",
                confidence=0.9
            ),
            ProcessingResult(
                task_id="adversarial_2",
                model_id="adversary_2",
                content="The response seems weak in its argumentation and lacks evidence",
                confidence=0.85
            )
        ]
        
        mock_model_provider.process_task.side_effect = adversarial_responses
        
        validation_report = await validator._adversarial_validation(result, sample_task, validator_models)
        
        assert isinstance(validation_report, ValidationReport)
        assert validation_report.validation_strategy == ValidationStrategy.ADVERSARIAL
        assert len(validation_report.issues) > 0  # Should find challenges

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_consensus_validation(self, mock_model_provider, sample_task, sample_processing_results):
        """Test consensus validation strategy."""
        validator = CrossValidator(mock_model_provider)
        result = sample_processing_results[0]
        validator_models = ["consensus_1", "consensus_2"]
        
        # Mock alternative responses for consensus
        alternative_responses = [
            ProcessingResult(
                task_id=sample_task.task_id,
                model_id="consensus_1",
                content="Alternative response with similar length and content",
                confidence=0.8
            ),
            ProcessingResult(
                task_id=sample_task.task_id,
                model_id="consensus_2",
                content="Another alternative response for consensus comparison",
                confidence=0.85
            )
        ]
        
        mock_model_provider.process_task.side_effect = alternative_responses
        
        validation_report = await validator._consensus_validation(result, sample_task, validator_models)
        
        assert isinstance(validation_report, ValidationReport)
        assert validation_report.validation_strategy == ValidationStrategy.CONSENSUS_CHECK
        assert 0.0 <= validation_report.consensus_level <= 1.0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fact_check_validation_strategy(self, mock_model_provider, sample_task, sample_processing_results):
        """Test fact-check validation strategy."""
        config = ValidationConfig(strategy=ValidationStrategy.FACT_CHECK)
        validator = CrossValidator(mock_model_provider, config)
        result = sample_processing_results[0]
        validator_models = ["fact_checker"]
        
        # Mock fact-check response
        fact_check_response = ProcessingResult(
            task_id="fact_check",
            model_id="fact_checker",
            content="Found factual errors in the response",
            confidence=0.9
        )
        
        mock_model_provider.process_task.return_value = fact_check_response
        
        validation_report = await validator._fact_check_validation(result, sample_task, validator_models)
        
        assert isinstance(validation_report, ValidationReport)
        assert validation_report.validation_strategy == ValidationStrategy.FACT_CHECK

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_validation_process(self, mock_model_provider, sample_task, sample_processing_results):
        """Test the complete validation process end-to-end."""
        validator = CrossValidator(mock_model_provider)
        result = sample_processing_results[0]
        
        # Mock validation response
        mock_model_provider.process_task.return_value = ProcessingResult(
            task_id="validation_test",
            model_id="validator",
            content="The response appears to be accurate with minor issues",
            confidence=0.85
        )
        
        validation_result = await validator.process(result, sample_task)
        
        assert isinstance(validation_result, ValidationResult)
        assert validation_result.task_id == sample_task.task_id
        assert validation_result.original_result == result
        assert isinstance(validation_result.validation_report, ValidationReport)
        assert isinstance(validation_result.is_valid, bool)
        assert 0.0 <= validation_result.validation_confidence <= 1.0
        assert isinstance(validation_result.improvement_suggestions, list)
        assert isinstance(validation_result.quality_metrics, QualityMetrics)
        assert validation_result.processing_time > 0.0
        
        # Check that validation is stored in history
        assert len(validator.validation_history) == 1
        assert validator.validation_history[0] == validation_result

    @pytest.mark.unit
    def test_calculate_criteria_score_no_issues(self, mock_model_provider):
        """Test criteria score calculation with no issues."""
        validator = CrossValidator(mock_model_provider)
        
        score = validator._calculate_criteria_score([])
        
        assert score == 1.0  # Perfect score with no issues

    @pytest.mark.unit
    def test_calculate_criteria_score_with_issues(self, mock_model_provider):
        """Test criteria score calculation with various issues."""
        validator = CrossValidator(mock_model_provider)
        
        issues = [
            ValidationIssue(
                issue_id="test_1",
                criteria=ValidationCriteria.ACCURACY,
                severity=ValidationSeverity.HIGH,
                description="High severity issue",
                suggestion="Fix it",
                confidence=0.9,
                evidence="Evidence",
                validator_model_id="validator_1"
            ),
            ValidationIssue(
                issue_id="test_2",
                criteria=ValidationCriteria.ACCURACY,
                severity=ValidationSeverity.LOW,
                description="Low severity issue",
                suggestion="Minor fix",
                confidence=0.8,
                evidence="Evidence",
                validator_model_id="validator_2"
            )
        ]
        
        score = validator._calculate_criteria_score(issues)
        
        assert 0.0 <= score < 1.0  # Should be reduced due to issues
        assert isinstance(score, float)

    @pytest.mark.unit
    def test_calculate_overall_score(self, mock_model_provider):
        """Test overall score calculation from criteria scores."""
        validator = CrossValidator(mock_model_provider)
        
        criteria_scores = {
            ValidationCriteria.ACCURACY: 0.9,
            ValidationCriteria.CONSISTENCY: 0.8,
            ValidationCriteria.COMPLETENESS: 0.85
        }
        
        overall_score = validator._calculate_overall_score(criteria_scores)
        
        assert 0.0 <= overall_score <= 1.0
        assert abs(overall_score - 0.85) < 0.01  # Should be close to the average

    @pytest.mark.unit
    def test_calculate_consensus_level(self, mock_model_provider):
        """Test consensus level calculation."""
        validator = CrossValidator(mock_model_provider)
        
        # Issues from different validators
        issues = [
            ValidationIssue("1", ValidationCriteria.ACCURACY, ValidationSeverity.HIGH, 
                          "", "", 0.9, "", "validator_1"),
            ValidationIssue("2", ValidationCriteria.ACCURACY, ValidationSeverity.LOW, 
                          "", "", 0.8, "", "validator_1"),
            ValidationIssue("3", ValidationCriteria.CONSISTENCY, ValidationSeverity.MEDIUM, 
                          "", "", 0.85, "", "validator_2")
        ]
        
        validator_models = ["validator_1", "validator_2", "validator_3"]
        
        consensus_level = validator._calculate_consensus_level(issues, validator_models)
        
        assert 0.0 <= consensus_level <= 1.0
        assert isinstance(consensus_level, float)

    @pytest.mark.unit
    def test_determine_validity_valid_result(self, mock_model_provider):
        """Test validity determination for a valid result."""
        config = ValidationConfig(confidence_threshold=0.7)
        validator = CrossValidator(mock_model_provider, config)
        
        # Create a validation report with good scores and no critical issues
        validation_report = ValidationReport(
            original_result=Mock(),
            task_context=Mock(),
            validation_strategy=ValidationStrategy.PEER_REVIEW,
            validator_models=["validator_1"],
            issues=[],  # No issues
            overall_score=0.85,  # Above threshold
            criteria_scores={},
            consensus_level=0.9,
            recommendations=[]
        )
        
        is_valid = validator._determine_validity(validation_report)
        
        assert is_valid is True

    @pytest.mark.unit
    def test_determine_validity_invalid_result(self, mock_model_provider):
        """Test validity determination for an invalid result."""
        config = ValidationConfig(confidence_threshold=0.7)
        validator = CrossValidator(mock_model_provider, config)
        
        # Create a validation report with critical issues
        critical_issue = ValidationIssue(
            issue_id="critical_1",
            criteria=ValidationCriteria.ACCURACY,
            severity=ValidationSeverity.CRITICAL,
            description="Critical error",
            suggestion="Fix immediately",
            confidence=0.95,
            evidence="Strong evidence",
            validator_model_id="validator_1"
        )
        
        validation_report = ValidationReport(
            original_result=Mock(),
            task_context=Mock(),
            validation_strategy=ValidationStrategy.PEER_REVIEW,
            validator_models=["validator_1"],
            issues=[critical_issue],  # Critical issue present
            overall_score=0.85,
            criteria_scores={},
            consensus_level=0.9,
            recommendations=[]
        )
        
        is_valid = validator._determine_validity(validation_report)
        
        assert is_valid is False

    @pytest.mark.unit
    def test_generate_improvement_suggestions(self, mock_model_provider):
        """Test improvement suggestions generation."""
        validator = CrossValidator(mock_model_provider)
        
        # Create validation report with various issues
        issues = [
            ValidationIssue("1", ValidationCriteria.ACCURACY, ValidationSeverity.CRITICAL,
                          "Critical issue", "Fix immediately", 0.95, "", "validator_1"),
            ValidationIssue("2", ValidationCriteria.CONSISTENCY, ValidationSeverity.HIGH,
                          "High issue", "Review carefully", 0.9, "", "validator_2")
        ]
        
        validation_report = ValidationReport(
            original_result=Mock(),
            task_context=Mock(),
            validation_strategy=ValidationStrategy.PEER_REVIEW,
            validator_models=["validator_1", "validator_2"],
            issues=issues,
            overall_score=0.5,  # Low score
            criteria_scores={},
            consensus_level=0.6,  # Low consensus
            recommendations=[]
        )
        
        suggestions = validator._generate_improvement_suggestions(validation_report)
        
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert any("critical" in suggestion.lower() for suggestion in suggestions)

    @pytest.mark.unit
    def test_get_validation_history(self, mock_model_provider):
        """Test getting validation history."""
        validator = CrossValidator(mock_model_provider)
        
        # Add some test validation results
        test_results = [
            ValidationResult(
                task_id=f"task_{i}",
                original_result=Mock(),
                validation_report=Mock(),
                is_valid=True,
                validation_confidence=0.8,
                improvement_suggestions=[],
                quality_metrics=Mock(),
                processing_time=1.0
            )
            for i in range(5)
        ]
        
        validator.validation_history = test_results
        
        # Test getting full history
        full_history = validator.get_validation_history()
        assert len(full_history) == 5
        assert full_history == test_results
        
        # Test getting limited history
        limited_history = validator.get_validation_history(limit=3)
        assert len(limited_history) == 3
        assert limited_history == test_results[-3:]

    @pytest.mark.unit
    def test_configure_validation(self, mock_model_provider):
        """Test validation configuration updates."""
        validator = CrossValidator(mock_model_provider)
        
        original_threshold = validator.config.confidence_threshold
        original_timeout = validator.config.timeout_seconds
        
        validator.configure_validation(
            confidence_threshold=0.9,
            timeout_seconds=60.0,
            min_validators=3
        )
        
        assert validator.config.confidence_threshold == 0.9
        assert validator.config.timeout_seconds == 60.0
        assert validator.config.min_validators == 3
        assert validator.config.confidence_threshold != original_threshold
        assert validator.config.timeout_seconds != original_timeout

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_validation_performance(self, performance_mock_provider, sample_task):
        """Test validation performance with multiple validators."""
        validator = CrossValidator(performance_mock_provider)
        
        # Create a test result
        test_result = ProcessingResult(
            task_id=sample_task.task_id,
            model_id="test_model",
            content="Test content for validation",
            confidence=0.8
        )
        
        start_time = datetime.now()
        validation_result = await validator.process(test_result, sample_task)
        end_time = datetime.now()
        
        processing_time = (end_time - start_time).total_seconds()
        
        # Should complete validation within reasonable time
        assert processing_time < 5.0  # 5 seconds max
        assert isinstance(validation_result, ValidationResult)

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_validation_with_no_available_models(self, mock_model_provider, sample_task, sample_processing_results):
        """Test validation when no models are available."""
        mock_model_provider.get_available_models.return_value = []
        
        validator = CrossValidator(mock_model_provider)
        result = sample_processing_results[0]
        
        # Should handle gracefully or raise appropriate error
        with pytest.raises(Exception):
            await validator.process(result, sample_task)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_validations(self, mock_model_provider, sample_task):
        """Test concurrent validation requests."""
        validator = CrossValidator(mock_model_provider)
        
        # Create multiple test results
        test_results = [
            ProcessingResult(
                task_id=f"concurrent_task_{i}",
                model_id=f"model_{i}",
                content=f"Test content {i}",
                confidence=0.8
            )
            for i in range(3)
        ]
        
        # Mock validation responses
        mock_model_provider.process_task.return_value = ProcessingResult(
            task_id="validation",
            model_id="validator",
            content="Validation response",
            confidence=0.8
        )
        
        # Run validations concurrently
        validation_results = await asyncio.gather(
            *[validator.process(result, sample_task) for result in test_results],
            return_exceptions=True
        )
        
        # All should succeed
        assert len(validation_results) == 3
        assert all(isinstance(result, ValidationResult) for result in validation_results)
        assert len(set(result.task_id for result in validation_results)) == 3  # All unique