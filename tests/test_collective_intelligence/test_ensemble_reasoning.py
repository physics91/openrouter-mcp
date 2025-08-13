"""
Comprehensive test suite for the Ensemble Reasoning module.

This module provides thorough testing of the intelligent task decomposition
and specialized model routing functionality.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import List
from unittest.mock import AsyncMock, Mock

from src.openrouter_mcp.collective_intelligence.ensemble_reasoning import (
    EnsembleReasoner, TaskDecomposer, ModelAssigner,
    DecompositionStrategy, TaskPriority, SubTask, ModelAssignment,
    EnsembleTask, EnsembleResult, SubTaskResult
)
from src.openrouter_mcp.collective_intelligence.base import (
    TaskContext, ProcessingResult, ModelInfo, TaskType, ModelCapability
)


class TestTaskDecomposer:
    """Test suite for the TaskDecomposer class."""

    @pytest.mark.unit
    def test_task_decomposer_initialization(self):
        """Test that TaskDecomposer initializes correctly."""
        decomposer = TaskDecomposer()
        
        assert hasattr(decomposer, 'decomposition_rules')
        assert isinstance(decomposer.decomposition_rules, dict)
        assert TaskType.REASONING in decomposer.decomposition_rules
        assert TaskType.CREATIVE in decomposer.decomposition_rules

    @pytest.mark.unit
    def test_select_decomposition_strategy_reasoning(self):
        """Test strategy selection for reasoning tasks."""
        decomposer = TaskDecomposer()
        
        task = TaskContext(
            task_id="test_reasoning",
            task_type=TaskType.REASONING,
            content="Analyze the pros and cons of renewable energy"
        )
        
        strategy = decomposer._select_decomposition_strategy(task)
        assert strategy == DecompositionStrategy.SEQUENTIAL

    @pytest.mark.unit
    def test_select_decomposition_strategy_creative(self):
        """Test strategy selection for creative tasks."""
        decomposer = TaskDecomposer()
        
        task = TaskContext(
            task_id="test_creative",
            task_type=TaskType.CREATIVE,
            content="Write a creative story about AI"
        )
        
        strategy = decomposer._select_decomposition_strategy(task)
        assert strategy == DecompositionStrategy.HIERARCHICAL

    @pytest.mark.unit
    def test_select_decomposition_strategy_complex_urgent(self):
        """Test strategy selection for complex urgent tasks."""
        decomposer = TaskDecomposer()
        
        task = TaskContext(
            task_id="test_urgent",
            task_type=TaskType.ANALYSIS,
            content="A" * 1500,  # Long content
            deadline=datetime.now() + timedelta(minutes=30)  # Urgent deadline
        )
        
        strategy = decomposer._select_decomposition_strategy(task)
        assert strategy == DecompositionStrategy.PARALLEL

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_decompose_sequential_reasoning(self):
        """Test sequential decomposition for reasoning tasks."""
        decomposer = TaskDecomposer()
        
        task = TaskContext(
            task_id="test_reasoning",
            task_type=TaskType.REASONING,
            content="Analyze the impact of climate change on agriculture"
        )
        
        sub_tasks = await decomposer._decompose_sequential(task)
        
        assert isinstance(sub_tasks, list)
        assert len(sub_tasks) >= 3
        assert all(isinstance(st, SubTask) for st in sub_tasks)
        assert all(st.parent_task_id == task.task_id for st in sub_tasks)
        
        # Check dependency chain
        for i, sub_task in enumerate(sub_tasks[1:], 1):
            assert f"{task.task_id}_seq_{i}" in sub_task.dependencies

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_decompose_parallel_analysis(self):
        """Test parallel decomposition for analysis tasks."""
        decomposer = TaskDecomposer()
        
        task = TaskContext(
            task_id="test_analysis",
            task_type=TaskType.ANALYSIS,
            content="Analyze market trends in renewable energy sector"
        )
        
        sub_tasks = await decomposer._decompose_parallel(task)
        
        assert isinstance(sub_tasks, list)
        assert len(sub_tasks) >= 3
        assert all(isinstance(st, SubTask) for st in sub_tasks)
        
        # Parallel tasks should have no dependencies
        assert all(len(st.dependencies) == 0 for st in sub_tasks)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_decompose_hierarchical_creative(self):
        """Test hierarchical decomposition for creative tasks."""
        decomposer = TaskDecomposer()
        
        task = TaskContext(
            task_id="test_creative",
            task_type=TaskType.CREATIVE,
            content="Create a comprehensive marketing campaign for a new product"
        )
        
        sub_tasks = await decomposer._decompose_hierarchical(task)
        
        assert isinstance(sub_tasks, list)
        assert len(sub_tasks) >= 6  # Main categories + sub-categories
        
        # Check that there are both main and sub-category tasks
        main_tasks = [st for st in sub_tasks if len(st.dependencies) == 0]
        sub_category_tasks = [st for st in sub_tasks if len(st.dependencies) > 0]
        
        assert len(main_tasks) >= 3
        assert len(sub_category_tasks) >= 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_decompose_task_full_process(self):
        """Test the complete task decomposition process."""
        decomposer = TaskDecomposer()
        
        task = TaskContext(
            task_id="test_full_decomposition",
            task_type=TaskType.CODE_GENERATION,
            content="Build a REST API for user management with authentication"
        )
        
        ensemble_task = await decomposer.decompose_task(task)
        
        assert isinstance(ensemble_task, EnsembleTask)
        assert ensemble_task.task_id == task.task_id
        assert ensemble_task.original_task == task
        assert isinstance(ensemble_task.decomposition_strategy, DecompositionStrategy)
        assert len(ensemble_task.sub_tasks) >= 3
        assert all(isinstance(st, SubTask) for st in ensemble_task.sub_tasks)

    @pytest.mark.unit
    def test_get_phase_capabilities(self):
        """Test capability assignment for different phases."""
        decomposer = TaskDecomposer()
        
        # Test analysis phase
        analysis_caps = decomposer._get_phase_capabilities("analyze the problem", TaskType.REASONING)
        assert ModelCapability.REASONING in analysis_caps
        assert ModelCapability.ACCURACY in analysis_caps
        
        # Test implementation phase for code
        impl_caps = decomposer._get_phase_capabilities("implement code", TaskType.CODE_GENERATION)
        assert ModelCapability.CODE in impl_caps
        
        # Test validation phase
        val_caps = decomposer._get_phase_capabilities("test and validate", TaskType.CODE_GENERATION)
        assert ModelCapability.ACCURACY in val_caps
        assert ModelCapability.REASONING in val_caps


class TestModelAssigner:
    """Test suite for the ModelAssigner class."""

    @pytest.mark.unit
    def test_model_assigner_initialization(self, mock_model_provider):
        """Test that ModelAssigner initializes correctly."""
        assigner = ModelAssigner(mock_model_provider)
        
        assert assigner.model_provider == mock_model_provider
        assert isinstance(assigner.assignment_history, list)
        assert len(assigner.assignment_history) == 0

    @pytest.mark.unit
    def test_calculate_model_score(self, mock_model_provider, sample_models):
        """Test model scoring algorithm."""
        assigner = ModelAssigner(mock_model_provider)
        
        sub_task = SubTask(
            sub_task_id="test_subtask",
            parent_task_id="test_parent",
            content="Analyze data patterns",
            task_type=TaskType.ANALYSIS,
            required_capabilities=[ModelCapability.REASONING, ModelCapability.ACCURACY],
            priority=TaskPriority.HIGH
        )
        
        # Test with a model that has matching capabilities
        model = sample_models[0]  # GPT-4 with strong reasoning
        score = assigner._calculate_model_score(model, sub_task)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be reasonably high for matching capabilities

    @pytest.mark.unit
    def test_estimate_cost(self, mock_model_provider, sample_models):
        """Test cost estimation for model assignments."""
        assigner = ModelAssigner(mock_model_provider)
        
        sub_task = SubTask(
            sub_task_id="test_subtask",
            parent_task_id="test_parent",
            content="This is a test task with some content to analyze",
            task_type=TaskType.ANALYSIS,
            required_capabilities=[ModelCapability.REASONING]
        )
        
        model = sample_models[0]
        cost = assigner._estimate_cost(model, sub_task)
        
        assert cost >= 0.0
        assert isinstance(cost, float)

    @pytest.mark.unit
    def test_estimate_time(self, mock_model_provider, sample_models):
        """Test time estimation for model assignments."""
        assigner = ModelAssigner(mock_model_provider)
        
        sub_task = SubTask(
            sub_task_id="test_subtask",
            parent_task_id="test_parent",
            content="Short task",
            task_type=TaskType.REASONING,
            required_capabilities=[ModelCapability.REASONING]
        )
        
        model = sample_models[0]
        time = assigner._estimate_time(model, sub_task)
        
        assert time > 0.0
        assert isinstance(time, float)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_assign_single_model(self, mock_model_provider, sample_models):
        """Test assignment of a single model to a sub-task."""
        assigner = ModelAssigner(mock_model_provider)
        
        sub_task = SubTask(
            sub_task_id="test_subtask",
            parent_task_id="test_parent",
            content="Analyze the given data",
            task_type=TaskType.ANALYSIS,
            required_capabilities=[ModelCapability.REASONING, ModelCapability.ACCURACY],
            priority=TaskPriority.HIGH
        )
        
        assignment = await assigner._assign_single_model(sub_task, sample_models)
        
        assert isinstance(assignment, ModelAssignment)
        assert assignment.sub_task_id == sub_task.sub_task_id
        assert assignment.model_id in [model.model_id for model in sample_models]
        assert 0.0 <= assignment.confidence_score <= 1.0
        assert assignment.estimated_cost >= 0.0
        assert assignment.estimated_time > 0.0
        assert isinstance(assignment.justification, str)
        assert len(assignment.justification) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_assign_models_multiple_subtasks(self, mock_model_provider, sample_models):
        """Test assignment of models to multiple sub-tasks."""
        assigner = ModelAssigner(mock_model_provider)
        
        # Create ensemble task with multiple sub-tasks
        ensemble_task = EnsembleTask(
            task_id="test_ensemble",
            original_task=TaskContext(
                task_id="test_original",
                task_type=TaskType.REASONING,
                content="Complex reasoning task"
            ),
            decomposition_strategy=DecompositionStrategy.PARALLEL,
            sub_tasks=[
                SubTask(
                    sub_task_id="subtask_1",
                    parent_task_id="test_ensemble",
                    content="Analyze aspect 1",
                    task_type=TaskType.ANALYSIS,
                    required_capabilities=[ModelCapability.REASONING]
                ),
                SubTask(
                    sub_task_id="subtask_2", 
                    parent_task_id="test_ensemble",
                    content="Generate creative solution",
                    task_type=TaskType.CREATIVE,
                    required_capabilities=[ModelCapability.CREATIVITY]
                ),
                SubTask(
                    sub_task_id="subtask_3",
                    parent_task_id="test_ensemble", 
                    content="Validate results",
                    task_type=TaskType.ANALYSIS,
                    required_capabilities=[ModelCapability.ACCURACY]
                )
            ]
        )
        
        assignments = await assigner.assign_models(ensemble_task)
        
        assert len(assignments) == 3
        assert all(isinstance(assignment, ModelAssignment) for assignment in assignments)
        
        # Check that all sub-tasks have assignments
        assigned_subtask_ids = {assignment.sub_task_id for assignment in assignments}
        expected_subtask_ids = {st.sub_task_id for st in ensemble_task.sub_tasks}
        assert assigned_subtask_ids == expected_subtask_ids
        
        # Check that assignments are stored in history
        assert len(assigner.assignment_history) == 3

    @pytest.mark.unit
    def test_generate_assignment_justification(self, mock_model_provider, sample_models):
        """Test generation of assignment justifications."""
        assigner = ModelAssigner(mock_model_provider)
        
        model = sample_models[0]  # GPT-4
        sub_task = SubTask(
            sub_task_id="test_subtask",
            parent_task_id="test_parent",
            content="Reasoning task",
            task_type=TaskType.REASONING,
            required_capabilities=[ModelCapability.REASONING]
        )
        score = 0.85
        
        justification = assigner._generate_assignment_justification(model, sub_task, score)
        
        assert isinstance(justification, str)
        assert len(justification) > 0
        assert model.name in justification
        assert str(score) in justification
        assert sub_task.sub_task_id in justification

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_assign_model_no_suitable_models(self, mock_model_provider):
        """Test handling when no suitable models are available."""
        assigner = ModelAssigner(mock_model_provider)
        
        sub_task = SubTask(
            sub_task_id="test_subtask",
            parent_task_id="test_parent",
            content="Test task",
            task_type=TaskType.REASONING,
            required_capabilities=[ModelCapability.REASONING]
        )
        
        # Empty model list
        with pytest.raises(ValueError, match="No suitable model found"):
            await assigner._assign_single_model(sub_task, [])


class TestEnsembleReasoner:
    """Test suite for the EnsembleReasoner class."""

    @pytest.mark.unit
    def test_ensemble_reasoner_initialization(self, mock_model_provider):
        """Test that EnsembleReasoner initializes correctly."""
        reasoner = EnsembleReasoner(mock_model_provider)
        
        assert reasoner.model_provider == mock_model_provider
        assert isinstance(reasoner.decomposer, TaskDecomposer)
        assert isinstance(reasoner.assigner, ModelAssigner)
        assert isinstance(reasoner.processing_history, list)
        assert len(reasoner.processing_history) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_ensemble_process(self, mock_model_provider, sample_task):
        """Test the complete ensemble reasoning process."""
        reasoner = EnsembleReasoner(mock_model_provider)
        
        result = await reasoner.process(sample_task)
        
        assert isinstance(result, EnsembleResult)
        assert result.task_id == sample_task.task_id
        assert result.original_task == sample_task
        assert isinstance(result.final_content, str)
        assert len(result.final_content) > 0
        assert len(result.sub_task_results) > 0
        assert isinstance(result.decomposition_strategy, DecompositionStrategy)
        assert result.total_time > 0.0
        assert 0.0 <= result.success_rate <= 1.0
        assert result.total_cost >= 0.0
        
        # Check that result is stored in history
        assert len(reasoner.processing_history) == 1
        assert reasoner.processing_history[0] == result

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_execute_sequential_strategy(self, mock_model_provider, sample_models):
        """Test sequential execution strategy."""
        reasoner = EnsembleReasoner(mock_model_provider)
        
        # Create ensemble task with sequential sub-tasks
        ensemble_task = EnsembleTask(
            task_id="test_sequential",
            original_task=TaskContext(
                task_id="test_original",
                task_type=TaskType.REASONING,
                content="Sequential reasoning task"
            ),
            decomposition_strategy=DecompositionStrategy.SEQUENTIAL,
            sub_tasks=[
                SubTask(
                    sub_task_id="seq_1",
                    parent_task_id="test_sequential",
                    content="First step",
                    task_type=TaskType.REASONING,
                    required_capabilities=[ModelCapability.REASONING],
                    priority=TaskPriority.HIGH
                ),
                SubTask(
                    sub_task_id="seq_2",
                    parent_task_id="test_sequential",
                    content="Second step",
                    task_type=TaskType.REASONING,
                    required_capabilities=[ModelCapability.REASONING],
                    dependencies=["seq_1"]
                )
            ],
            assignments=[
                ModelAssignment(
                    sub_task_id="seq_1",
                    model_id="openai/gpt-4",
                    confidence_score=0.9,
                    estimated_cost=0.01,
                    estimated_time=2.0,
                    justification="Test assignment"
                ),
                ModelAssignment(
                    sub_task_id="seq_2",
                    model_id="anthropic/claude-3-haiku",
                    confidence_score=0.8,
                    estimated_cost=0.005,
                    estimated_time=1.5,
                    justification="Test assignment"
                )
            ]
        )
        
        results = await reasoner._execute_sequential(ensemble_task)
        
        assert len(results) == 2
        assert all(isinstance(result, SubTaskResult) for result in results)
        assert results[0].sub_task.sub_task_id == "seq_1"
        assert results[1].sub_task.sub_task_id == "seq_2"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_execute_parallel_strategy(self, mock_model_provider):
        """Test parallel execution strategy."""
        reasoner = EnsembleReasoner(mock_model_provider)
        
        # Create ensemble task with parallel sub-tasks
        ensemble_task = EnsembleTask(
            task_id="test_parallel",
            original_task=TaskContext(
                task_id="test_original",
                task_type=TaskType.ANALYSIS,
                content="Parallel analysis task"
            ),
            decomposition_strategy=DecompositionStrategy.PARALLEL,
            sub_tasks=[
                SubTask(
                    sub_task_id="par_1",
                    parent_task_id="test_parallel",
                    content="Parallel task 1",
                    task_type=TaskType.ANALYSIS,
                    required_capabilities=[ModelCapability.REASONING]
                ),
                SubTask(
                    sub_task_id="par_2",
                    parent_task_id="test_parallel",
                    content="Parallel task 2", 
                    task_type=TaskType.ANALYSIS,
                    required_capabilities=[ModelCapability.ACCURACY]
                )
            ],
            assignments=[
                ModelAssignment(
                    sub_task_id="par_1",
                    model_id="openai/gpt-4",
                    confidence_score=0.9,
                    estimated_cost=0.01,
                    estimated_time=2.0,
                    justification="Test assignment"
                ),
                ModelAssignment(
                    sub_task_id="par_2",
                    model_id="anthropic/claude-3-haiku",
                    confidence_score=0.8,
                    estimated_cost=0.005,
                    estimated_time=1.5,
                    justification="Test assignment"
                )
            ]
        )
        
        results = await reasoner._execute_parallel(ensemble_task)
        
        assert len(results) == 2
        assert all(isinstance(result, SubTaskResult) for result in results)
        
        # Check that both tasks were executed (order may vary)
        executed_ids = {result.sub_task.sub_task_id for result in results}
        assert executed_ids == {"par_1", "par_2"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_execute_single_sub_task_success(self, mock_model_provider):
        """Test successful execution of a single sub-task."""
        reasoner = EnsembleReasoner(mock_model_provider)
        
        sub_task = SubTask(
            sub_task_id="test_subtask",
            parent_task_id="test_parent",
            content="Test sub-task content",
            task_type=TaskType.REASONING,
            required_capabilities=[ModelCapability.REASONING],
            timeout_seconds=5.0,
            max_retries=1
        )
        
        assignment = ModelAssignment(
            sub_task_id="test_subtask",
            model_id="openai/gpt-4",
            confidence_score=0.9,
            estimated_cost=0.01,
            estimated_time=2.0,
            justification="Test assignment"
        )
        
        result = await reasoner._execute_single_sub_task(sub_task, assignment)
        
        assert isinstance(result, SubTaskResult)
        assert result.sub_task == sub_task
        assert result.assignment == assignment
        assert isinstance(result.result, ProcessingResult)
        assert result.success is True
        assert result.retry_count == 0
        assert result.error_message is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_execute_single_sub_task_with_retries(self, mock_model_provider):
        """Test sub-task execution with retry mechanism."""
        # Create a provider that fails first time, succeeds second time
        failing_provider = AsyncMock()
        
        call_count = 0
        async def mock_process_task(task, model_id, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary failure")
            else:
                return ProcessingResult(
                    task_id=task.task_id,
                    model_id=model_id,
                    content="Success after retry",
                    confidence=0.8
                )
        
        failing_provider.process_task.side_effect = mock_process_task
        
        reasoner = EnsembleReasoner(failing_provider)
        
        sub_task = SubTask(
            sub_task_id="test_subtask",
            parent_task_id="test_parent",
            content="Test content",
            task_type=TaskType.REASONING,
            required_capabilities=[ModelCapability.REASONING],
            timeout_seconds=5.0,
            max_retries=2
        )
        
        assignment = ModelAssignment(
            sub_task_id="test_subtask",
            model_id="test_model",
            confidence_score=0.9,
            estimated_cost=0.01,
            estimated_time=2.0,
            justification="Test"
        )
        
        result = await reasoner._execute_single_sub_task(sub_task, assignment)
        
        assert result.success is True
        assert result.retry_count == 1  # One retry
        assert call_count == 2  # Called twice

    @pytest.mark.unit
    def test_find_assignment(self, mock_model_provider):
        """Test finding assignment for a specific sub-task."""
        reasoner = EnsembleReasoner(mock_model_provider)
        
        assignments = [
            ModelAssignment(
                sub_task_id="task_1",
                model_id="model_1",
                confidence_score=0.9,
                estimated_cost=0.01,
                estimated_time=2.0,
                justification="Test"
            ),
            ModelAssignment(
                sub_task_id="task_2",
                model_id="model_2",
                confidence_score=0.8,
                estimated_cost=0.005,
                estimated_time=1.5,
                justification="Test"
            )
        ]
        
        # Test finding existing assignment
        assignment = reasoner._find_assignment("task_1", assignments)
        assert assignment.sub_task_id == "task_1"
        assert assignment.model_id == "model_1"
        
        # Test non-existent assignment
        with pytest.raises(ValueError, match="No assignment found"):
            reasoner._find_assignment("task_3", assignments)

    @pytest.mark.unit
    def test_synthesize_final_content(self, mock_model_provider, sample_processing_results):
        """Test synthesis of final content from sub-task results."""
        reasoner = EnsembleReasoner(mock_model_provider)
        
        # Create sub-task results with different priorities
        sub_task_results = []
        priorities = [TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.MEDIUM]
        
        for i, (result, priority) in enumerate(zip(sample_processing_results[:3], priorities)):
            sub_task = SubTask(
                sub_task_id=f"subtask_{i}",
                parent_task_id="test_parent",
                content=f"Sub-task {i}",
                task_type=TaskType.REASONING,
                required_capabilities=[ModelCapability.REASONING],
                priority=priority
            )
            
            assignment = ModelAssignment(
                sub_task_id=f"subtask_{i}",
                model_id=result.model_id,
                confidence_score=0.8,
                estimated_cost=0.01,
                estimated_time=2.0,
                justification="Test"
            )
            
            sub_task_results.append(
                SubTaskResult(
                    sub_task=sub_task,
                    assignment=assignment,
                    result=result,
                    success=True
                )
            )
        
        ensemble_task = EnsembleTask(
            task_id="test_ensemble",
            original_task=TaskContext(
                task_id="test_original",
                task_type=TaskType.REASONING,
                content="Test task"
            ),
            decomposition_strategy=DecompositionStrategy.SEQUENTIAL
        )
        
        final_content = reasoner._synthesize_final_content(sub_task_results, ensemble_task)
        
        assert isinstance(final_content, str)
        assert len(final_content) > 0
        # Should contain content from all successful results
        for result in sub_task_results:
            assert any(part in final_content for part in result.result.content.split()[:3])

    @pytest.mark.unit
    def test_calculate_overall_quality(self, mock_model_provider, sample_processing_results):
        """Test calculation of overall quality metrics."""
        reasoner = EnsembleReasoner(mock_model_provider)
        
        # Create successful sub-task results
        successful_results = []
        for i, result in enumerate(sample_processing_results[:3]):
            sub_task = SubTask(
                sub_task_id=f"subtask_{i}",
                parent_task_id="test_parent",
                content=f"Sub-task {i}",
                task_type=TaskType.REASONING,
                required_capabilities=[ModelCapability.REASONING]
            )
            
            assignment = ModelAssignment(
                sub_task_id=f"subtask_{i}",
                model_id=result.model_id,
                confidence_score=0.8,
                estimated_cost=0.01,
                estimated_time=2.0,
                justification="Test"
            )
            
            successful_results.append(
                SubTaskResult(
                    sub_task=sub_task,
                    assignment=assignment,
                    result=result,
                    success=True
                )
            )
        
        quality = reasoner._calculate_overall_quality(successful_results)
        
        assert 0.0 <= quality.accuracy <= 1.0
        assert 0.0 <= quality.consistency <= 1.0
        assert 0.0 <= quality.completeness <= 1.0
        assert 0.0 <= quality.relevance <= 1.0
        assert 0.0 <= quality.confidence <= 1.0
        assert 0.0 <= quality.coherence <= 1.0
        assert 0.0 <= quality.overall_score() <= 1.0

    @pytest.mark.unit
    def test_calculate_performance_metrics(self, mock_model_provider):
        """Test calculation of performance metrics."""
        reasoner = EnsembleReasoner(mock_model_provider)
        
        # Create sub-task results with some successes and failures
        sub_task_results = []
        
        for i in range(4):
            sub_task = SubTask(
                sub_task_id=f"subtask_{i}",
                parent_task_id="test_parent",
                content=f"Sub-task {i}",
                task_type=TaskType.REASONING,
                required_capabilities=[ModelCapability.REASONING]
            )
            
            assignment = ModelAssignment(
                sub_task_id=f"subtask_{i}",
                model_id=f"model_{i}",
                confidence_score=0.8,
                estimated_cost=0.01,
                estimated_time=2.0,
                justification="Test"
            )
            
            # First 3 succeed, last one fails
            success = i < 3
            result = ProcessingResult(
                task_id=f"subtask_{i}",
                model_id=f"model_{i}",
                content=f"Result {i}" if success else "",
                confidence=0.8 if success else 0.0,
                processing_time=2.0 if success else 0.0
            )
            
            sub_task_results.append(
                SubTaskResult(
                    sub_task=sub_task,
                    assignment=assignment,
                    result=result,
                    success=success,
                    error_message=None if success else "Test error"
                )
            )
        
        total_time = 10.0
        metrics = reasoner._calculate_performance_metrics(sub_task_results, total_time)
        
        assert metrics.success_rate == 0.75  # 3/4 successful
        assert metrics.error_rate == 0.25   # 1/4 failed
        assert metrics.throughput > 0.0
        assert metrics.response_time > 0.0
        assert metrics.cost_efficiency > 0.0
        assert metrics.resource_utilization == 0.75

    @pytest.mark.unit
    def test_get_processing_history(self, mock_model_provider):
        """Test access to processing history."""
        reasoner = EnsembleReasoner(mock_model_provider)
        
        # Add some test results to history
        test_results = [
            EnsembleResult(
                task_id=f"task_{i}",
                original_task=TaskContext(
                    task_id=f"task_{i}",
                    task_type=TaskType.REASONING,
                    content=f"Task {i}"
                ),
                final_content=f"Result {i}",
                sub_task_results=[],
                decomposition_strategy=DecompositionStrategy.SEQUENTIAL,
                overall_quality=Mock(),
                performance_metrics=Mock(),
                total_cost=0.01,
                total_time=2.0,
                success_rate=1.0
            )
            for i in range(5)
        ]
        
        reasoner.processing_history = test_results
        
        # Test getting full history
        full_history = reasoner.get_processing_history()
        assert len(full_history) == 5
        assert full_history == test_results
        
        # Test getting limited history
        limited_history = reasoner.get_processing_history(limit=3)
        assert len(limited_history) == 3
        assert limited_history == test_results[-3:]

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_ensemble_performance_with_many_subtasks(self, performance_mock_provider):
        """Test ensemble performance with many sub-tasks."""
        reasoner = EnsembleReasoner(performance_mock_provider)
        
        # Create complex task that will generate many sub-tasks
        complex_task = TaskContext(
            task_id="complex_performance_test",
            task_type=TaskType.ANALYSIS,
            content="A" * 2000,  # Long content to trigger complex decomposition
            requirements={"detail_level": "comprehensive"}
        )
        
        start_time = datetime.now()
        result = await reasoner.process(complex_task)
        end_time = datetime.now()
        
        processing_time = (end_time - start_time).total_seconds()
        
        # Should complete within reasonable time
        assert processing_time < 10.0  # 10 seconds max
        assert isinstance(result, EnsembleResult)
        assert len(result.sub_task_results) >= 3
        assert result.success_rate > 0.0

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_ensemble_with_all_subtask_failures(self, failing_model_provider):
        """Test ensemble handling when all sub-tasks fail."""
        reasoner = EnsembleReasoner(failing_model_provider)
        
        task = TaskContext(
            task_id="failing_task",
            task_type=TaskType.REASONING,
            content="This task will fail"
        )
        
        result = await reasoner.process(task)
        
        assert isinstance(result, EnsembleResult)
        assert result.success_rate == 0.0
        assert all(not sub_result.success for sub_result in result.sub_task_results)
        assert "Unable to complete task" in result.final_content

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_ensemble_processing(self, mock_model_provider):
        """Test concurrent processing of multiple ensemble tasks."""
        reasoner = EnsembleReasoner(mock_model_provider)
        
        # Create multiple tasks
        tasks = [
            TaskContext(
                task_id=f"concurrent_task_{i}",
                task_type=TaskType.REASONING,
                content=f"Concurrent task {i} content"
            )
            for i in range(3)
        ]
        
        # Process all tasks concurrently
        results = await asyncio.gather(
            *[reasoner.process(task) for task in tasks],
            return_exceptions=True
        )
        
        # All should succeed
        assert len(results) == 3
        assert all(isinstance(result, EnsembleResult) for result in results)
        assert len(set(result.task_id for result in results)) == 3  # All unique
        
        # Check processing history
        assert len(reasoner.processing_history) == 3