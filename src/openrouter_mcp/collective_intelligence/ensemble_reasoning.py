"""
Intelligent Ensemble Reasoning

This module implements intelligent task decomposition and specialized model routing
based on model capabilities and task requirements. It breaks down complex tasks
into smaller components and assigns them to the most suitable models.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import logging

from .base import (
    CollectiveIntelligenceComponent,
    TaskContext,
    ProcessingResult,
    ModelProvider,
    ModelInfo,
    TaskType,
    ModelCapability,
    QualityMetrics,
    PerformanceMetrics
)

logger = logging.getLogger(__name__)


class DecompositionStrategy(Enum):
    """Strategies for decomposing complex tasks."""
    SEQUENTIAL = "sequential"  # Tasks must be completed in order
    PARALLEL = "parallel"  # Tasks can be completed simultaneously
    HIERARCHICAL = "hierarchical"  # Tree-like task breakdown
    DYNAMIC = "dynamic"  # Adaptive decomposition based on results


class TaskPriority(Enum):
    """Priority levels for sub-tasks."""
    CRITICAL = "critical"  # Must succeed for overall success
    HIGH = "high"  # Important but not critical
    MEDIUM = "medium"  # Helpful but optional
    LOW = "low"  # Nice to have


@dataclass
class SubTask:
    """A decomposed sub-task with specialized requirements."""
    sub_task_id: str
    parent_task_id: str
    content: str
    task_type: TaskType
    required_capabilities: List[ModelCapability]
    priority: TaskPriority = TaskPriority.MEDIUM
    dependencies: List[str] = field(default_factory=list)  # IDs of prerequisite sub-tasks
    timeout_seconds: float = 30.0
    max_retries: int = 2
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelAssignment:
    """Assignment of a model to a specific sub-task."""
    sub_task_id: str
    model_id: str
    confidence_score: float  # How well the model fits the task
    estimated_cost: float
    estimated_time: float
    justification: str  # Why this model was selected


@dataclass
class SubTaskResult:
    """Result from processing a sub-task."""
    sub_task: SubTask
    assignment: ModelAssignment
    result: ProcessingResult
    success: bool
    retry_count: int = 0
    error_message: Optional[str] = None


@dataclass
class EnsembleTask:
    """A complex task that requires ensemble reasoning."""
    task_id: str
    original_task: TaskContext
    decomposition_strategy: DecompositionStrategy
    sub_tasks: List[SubTask] = field(default_factory=list)
    assignments: List[ModelAssignment] = field(default_factory=list)
    results: List[SubTaskResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnsembleResult:
    """Final result from ensemble reasoning process."""
    task_id: str
    original_task: TaskContext
    final_content: str
    sub_task_results: List[SubTaskResult]
    decomposition_strategy: DecompositionStrategy
    overall_quality: QualityMetrics
    performance_metrics: PerformanceMetrics
    total_cost: float
    total_time: float
    success_rate: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class TaskDecomposer:
    """Handles intelligent decomposition of complex tasks."""
    
    def __init__(self):
        self.decomposition_rules = self._initialize_decomposition_rules()
    
    def _initialize_decomposition_rules(self) -> Dict[TaskType, Dict]:
        """Initialize rules for task decomposition based on task types."""
        return {
            TaskType.REASONING: {
                "common_patterns": [
                    {"pattern": "analyze", "capabilities": [ModelCapability.REASONING, ModelCapability.ACCURACY]},
                    {"pattern": "compare", "capabilities": [ModelCapability.REASONING]},
                    {"pattern": "evaluate", "capabilities": [ModelCapability.REASONING, ModelCapability.ACCURACY]},
                    {"pattern": "conclude", "capabilities": [ModelCapability.REASONING]}
                ],
                "default_strategy": DecompositionStrategy.SEQUENTIAL
            },
            TaskType.CREATIVE: {
                "common_patterns": [
                    {"pattern": "brainstorm", "capabilities": [ModelCapability.CREATIVITY]},
                    {"pattern": "generate", "capabilities": [ModelCapability.CREATIVITY]},
                    {"pattern": "refine", "capabilities": [ModelCapability.CREATIVITY, ModelCapability.ACCURACY]},
                    {"pattern": "finalize", "capabilities": [ModelCapability.ACCURACY]}
                ],
                "default_strategy": DecompositionStrategy.HIERARCHICAL
            },
            TaskType.CODE_GENERATION: {
                "common_patterns": [
                    {"pattern": "design", "capabilities": [ModelCapability.CODE, ModelCapability.REASONING]},
                    {"pattern": "implement", "capabilities": [ModelCapability.CODE]},
                    {"pattern": "test", "capabilities": [ModelCapability.CODE, ModelCapability.ACCURACY]},
                    {"pattern": "optimize", "capabilities": [ModelCapability.CODE, ModelCapability.REASONING]}
                ],
                "default_strategy": DecompositionStrategy.SEQUENTIAL
            },
            TaskType.ANALYSIS: {
                "common_patterns": [
                    {"pattern": "collect", "capabilities": [ModelCapability.ACCURACY]},
                    {"pattern": "process", "capabilities": [ModelCapability.REASONING, ModelCapability.ACCURACY]},
                    {"pattern": "interpret", "capabilities": [ModelCapability.REASONING]},
                    {"pattern": "summarize", "capabilities": [ModelCapability.ACCURACY]}
                ],
                "default_strategy": DecompositionStrategy.PARALLEL
            }
        }
    
    async def decompose_task(self, task: TaskContext) -> EnsembleTask:
        """Decompose a complex task into manageable sub-tasks."""
        
        # Determine decomposition strategy
        strategy = self._select_decomposition_strategy(task)
        
        # Create ensemble task container
        ensemble_task = EnsembleTask(
            task_id=task.task_id,
            original_task=task,
            decomposition_strategy=strategy
        )
        
        # Decompose based on strategy
        if strategy == DecompositionStrategy.SEQUENTIAL:
            sub_tasks = await self._decompose_sequential(task)
        elif strategy == DecompositionStrategy.PARALLEL:
            sub_tasks = await self._decompose_parallel(task)
        elif strategy == DecompositionStrategy.HIERARCHICAL:
            sub_tasks = await self._decompose_hierarchical(task)
        else:  # DYNAMIC
            sub_tasks = await self._decompose_dynamic(task)
        
        ensemble_task.sub_tasks = sub_tasks
        
        logger.info(f"Decomposed task {task.task_id} into {len(sub_tasks)} sub-tasks using {strategy.value} strategy")
        
        return ensemble_task
    
    def _select_decomposition_strategy(self, task: TaskContext) -> DecompositionStrategy:
        """Select appropriate decomposition strategy based on task characteristics."""
        
        # Check task type rules
        if task.task_type in self.decomposition_rules:
            default_strategy = self.decomposition_rules[task.task_type]["default_strategy"]
        else:
            default_strategy = DecompositionStrategy.SEQUENTIAL
        
        # Consider task complexity and constraints
        content_length = len(task.content)
        has_deadline = task.deadline is not None
        
        # Adjust strategy based on constraints
        if has_deadline and content_length > 1000:
            # Prefer parallel for time-critical complex tasks
            return DecompositionStrategy.PARALLEL
        elif content_length > 2000:
            # Use hierarchical for very complex tasks
            return DecompositionStrategy.HIERARCHICAL
        
        return default_strategy
    
    async def _decompose_sequential(self, task: TaskContext) -> List[SubTask]:
        """Decompose task into sequential sub-tasks."""
        sub_tasks = []
        
        # Simple rule-based decomposition for demonstration
        content = task.content.lower()
        
        if task.task_type == TaskType.REASONING:
            phases = ["analyze the problem", "gather relevant information", "evaluate options", "draw conclusions"]
        elif task.task_type == TaskType.CODE_GENERATION:
            phases = ["understand requirements", "design solution", "implement code", "test and validate"]
        else:
            # Generic decomposition
            phases = ["understand the task", "process information", "generate response"]
        
        for i, phase in enumerate(phases):
            sub_task = SubTask(
                sub_task_id=f"{task.task_id}_seq_{i+1}",
                parent_task_id=task.task_id,
                content=f"{phase.capitalize()}: {task.content}",
                task_type=task.task_type,
                required_capabilities=self._get_phase_capabilities(phase, task.task_type),
                priority=TaskPriority.HIGH if i < 2 else TaskPriority.MEDIUM,
                dependencies=[f"{task.task_id}_seq_{i}"] if i > 0 else []
            )
            sub_tasks.append(sub_task)
        
        return sub_tasks
    
    async def _decompose_parallel(self, task: TaskContext) -> List[SubTask]:
        """Decompose task into parallel sub-tasks."""
        sub_tasks = []
        
        # Identify parallel aspects
        if task.task_type == TaskType.ANALYSIS:
            aspects = ["data collection", "statistical analysis", "trend identification", "visualization"]
        elif "compare" in task.content.lower():
            aspects = ["analyze first option", "analyze second option", "identify differences", "make recommendation"]
        else:
            # Generic parallel decomposition
            aspects = ["research background", "analyze current state", "identify key factors"]
        
        for i, aspect in enumerate(aspects):
            sub_task = SubTask(
                sub_task_id=f"{task.task_id}_par_{i+1}",
                parent_task_id=task.task_id,
                content=f"{aspect.capitalize()}: {task.content}",
                task_type=task.task_type,
                required_capabilities=self._get_aspect_capabilities(aspect, task.task_type),
                priority=TaskPriority.HIGH if i < 2 else TaskPriority.MEDIUM
            )
            sub_tasks.append(sub_task)
        
        return sub_tasks
    
    async def _decompose_hierarchical(self, task: TaskContext) -> List[SubTask]:
        """Decompose task into hierarchical sub-tasks."""
        sub_tasks = []
        
        # Create main categories first
        if task.task_type == TaskType.CREATIVE:
            categories = ["concept development", "content creation", "refinement"]
        else:
            categories = ["planning", "execution", "review"]
        
        for i, category in enumerate(categories):
            # Main category task
            main_task = SubTask(
                sub_task_id=f"{task.task_id}_hier_{i+1}",
                parent_task_id=task.task_id,
                content=f"{category.capitalize()}: {task.content}",
                task_type=task.task_type,
                required_capabilities=self._get_category_capabilities(category, task.task_type),
                priority=TaskPriority.HIGH
            )
            sub_tasks.append(main_task)
            
            # Sub-category tasks
            if category == "concept development":
                sub_categories = ["brainstorming", "evaluation"]
            elif category == "content creation":
                sub_categories = ["drafting", "structuring"]
            else:
                sub_categories = ["quality check", "final polish"]
            
            for j, sub_category in enumerate(sub_categories):
                sub_task = SubTask(
                    sub_task_id=f"{task.task_id}_hier_{i+1}_{j+1}",
                    parent_task_id=task.task_id,
                    content=f"{sub_category.capitalize()}: {task.content}",
                    task_type=task.task_type,
                    required_capabilities=self._get_subcategory_capabilities(sub_category, task.task_type),
                    priority=TaskPriority.MEDIUM,
                    dependencies=[main_task.sub_task_id]
                )
                sub_tasks.append(sub_task)
        
        return sub_tasks
    
    async def _decompose_dynamic(self, task: TaskContext) -> List[SubTask]:
        """Decompose task dynamically based on content analysis."""
        # This would use more sophisticated NLP analysis in practice
        # For now, fall back to sequential decomposition
        return await self._decompose_sequential(task)
    
    def _get_phase_capabilities(self, phase: str, task_type: TaskType) -> List[ModelCapability]:
        """Get required capabilities for a specific phase."""
        phase_lower = phase.lower()
        
        if "analyze" in phase_lower or "understand" in phase_lower:
            return [ModelCapability.REASONING, ModelCapability.ACCURACY]
        elif "implement" in phase_lower or "generate" in phase_lower:
            if task_type == TaskType.CODE_GENERATION:
                return [ModelCapability.CODE]
            else:
                return [ModelCapability.CREATIVITY]
        elif "test" in phase_lower or "validate" in phase_lower:
            return [ModelCapability.ACCURACY, ModelCapability.REASONING]
        else:
            return [ModelCapability.REASONING]
    
    def _get_aspect_capabilities(self, aspect: str, task_type: TaskType) -> List[ModelCapability]:
        """Get required capabilities for a specific aspect."""
        aspect_lower = aspect.lower()
        
        if "data" in aspect_lower or "statistical" in aspect_lower:
            return [ModelCapability.ACCURACY, ModelCapability.MATH]
        elif "trend" in aspect_lower or "visualization" in aspect_lower:
            return [ModelCapability.REASONING, ModelCapability.CREATIVITY]
        else:
            return [ModelCapability.REASONING, ModelCapability.ACCURACY]
    
    def _get_category_capabilities(self, category: str, task_type: TaskType) -> List[ModelCapability]:
        """Get required capabilities for a main category."""
        category_lower = category.lower()
        
        if "concept" in category_lower or "planning" in category_lower:
            return [ModelCapability.CREATIVITY, ModelCapability.REASONING]
        elif "creation" in category_lower or "execution" in category_lower:
            return [ModelCapability.CREATIVITY]
        else:  # review, refinement
            return [ModelCapability.ACCURACY, ModelCapability.REASONING]
    
    def _get_subcategory_capabilities(self, subcategory: str, task_type: TaskType) -> List[ModelCapability]:
        """Get required capabilities for a sub-category."""
        subcategory_lower = subcategory.lower()
        
        if "brainstorm" in subcategory_lower or "draft" in subcategory_lower:
            return [ModelCapability.CREATIVITY]
        elif "evaluation" in subcategory_lower or "quality" in subcategory_lower:
            return [ModelCapability.ACCURACY, ModelCapability.REASONING]
        else:
            return [ModelCapability.REASONING]


class ModelAssigner:
    """Assigns the most suitable models to sub-tasks."""
    
    def __init__(self, model_provider: ModelProvider):
        self.model_provider = model_provider
        self.assignment_history: List[ModelAssignment] = []
    
    async def assign_models(self, ensemble_task: EnsembleTask) -> List[ModelAssignment]:
        """Assign optimal models to all sub-tasks."""
        available_models = await self.model_provider.get_available_models()
        assignments = []
        
        for sub_task in ensemble_task.sub_tasks:
            assignment = await self._assign_single_model(sub_task, available_models)
            assignments.append(assignment)
        
        self.assignment_history.extend(assignments)
        
        logger.info(f"Assigned models to {len(assignments)} sub-tasks")
        
        return assignments
    
    async def _assign_single_model(
        self, 
        sub_task: SubTask, 
        available_models: List[ModelInfo]
    ) -> ModelAssignment:
        """Assign the best model for a single sub-task."""
        
        scored_models = []
        
        for model in available_models:
            score = self._calculate_model_score(model, sub_task)
            cost = self._estimate_cost(model, sub_task)
            time = self._estimate_time(model, sub_task)
            
            scored_models.append((model, score, cost, time))
        
        # Sort by score (descending)
        scored_models.sort(key=lambda x: x[1], reverse=True)
        
        if not scored_models:
            raise ValueError(f"No suitable model found for sub-task {sub_task.sub_task_id}")
        
        best_model, score, cost, time = scored_models[0]
        
        justification = self._generate_assignment_justification(best_model, sub_task, score)
        
        return ModelAssignment(
            sub_task_id=sub_task.sub_task_id,
            model_id=best_model.model_id,
            confidence_score=score,
            estimated_cost=cost,
            estimated_time=time,
            justification=justification
        )
    
    def _calculate_model_score(self, model: ModelInfo, sub_task: SubTask) -> float:
        """Calculate how well a model fits a sub-task."""
        base_score = 0.5
        
        # Check capability matching
        capability_scores = []
        for required_cap in sub_task.required_capabilities:
            if required_cap in model.capabilities:
                capability_scores.append(model.capabilities[required_cap])
            else:
                capability_scores.append(0.0)
        
        if capability_scores:
            capability_score = sum(capability_scores) / len(capability_scores)
        else:
            capability_score = 0.5
        
        # Factor in model reliability metrics
        availability_factor = model.availability
        accuracy_factor = model.accuracy_score
        
        # Consider task priority
        priority_multiplier = {
            TaskPriority.CRITICAL: 1.2,
            TaskPriority.HIGH: 1.1,
            TaskPriority.MEDIUM: 1.0,
            TaskPriority.LOW: 0.9
        }[sub_task.priority]
        
        final_score = (
            capability_score * 0.5 +
            availability_factor * 0.2 +
            accuracy_factor * 0.3
        ) * priority_multiplier
        
        return min(1.0, final_score)
    
    def _estimate_cost(self, model: ModelInfo, sub_task: SubTask) -> float:
        """Estimate the cost of using a model for a sub-task."""
        # Simple estimation based on content length and model cost
        estimated_tokens = len(sub_task.content.split()) * 1.3  # Rough token estimation
        return estimated_tokens * model.cost_per_token
    
    def _estimate_time(self, model: ModelInfo, sub_task: SubTask) -> float:
        """Estimate the time required for a model to complete a sub-task."""
        # Base time from model's average response time
        base_time = model.response_time_avg
        
        # Adjust for content complexity
        content_complexity = len(sub_task.content) / 1000.0  # Normalize by 1000 chars
        complexity_factor = 1.0 + (content_complexity * 0.5)
        
        return base_time * complexity_factor
    
    def _generate_assignment_justification(
        self, 
        model: ModelInfo, 
        sub_task: SubTask, 
        score: float
    ) -> str:
        """Generate a human-readable justification for the model assignment."""
        
        # Find the model's strongest capabilities that match task requirements
        matching_capabilities = []
        for cap in sub_task.required_capabilities:
            if cap in model.capabilities and model.capabilities[cap] > 0.7:
                matching_capabilities.append(cap.value)
        
        justification = f"Selected {model.name} (score: {score:.2f}) for {sub_task.sub_task_id}"
        
        if matching_capabilities:
            justification += f" due to strong {', '.join(matching_capabilities)} capabilities"
        
        if model.availability > 0.9:
            justification += " and high availability"
        
        return justification


class EnsembleReasoner(CollectiveIntelligenceComponent):
    """
    Main ensemble reasoning coordinator that orchestrates task decomposition,
    model assignment, and result aggregation.
    """
    
    def __init__(self, model_provider: ModelProvider):
        super().__init__(model_provider)
        self.decomposer = TaskDecomposer()
        self.assigner = ModelAssigner(model_provider)
        self.processing_history: List[EnsembleResult] = []
    
    async def process(self, task: TaskContext, **kwargs) -> EnsembleResult:
        """
        Process a complex task using ensemble reasoning.
        
        Args:
            task: The task to process
            **kwargs: Additional options
            
        Returns:
            EnsembleResult with comprehensive processing information
        """
        start_time = datetime.now()
        
        try:
            # Step 1: Decompose the task
            ensemble_task = await self.decomposer.decompose_task(task)
            
            # Step 2: Assign models to sub-tasks
            assignments = await self.assigner.assign_models(ensemble_task)
            ensemble_task.assignments = assignments
            
            # Step 3: Execute sub-tasks
            sub_task_results = await self._execute_sub_tasks(ensemble_task)
            
            # Step 4: Aggregate results
            final_result = await self._aggregate_results(ensemble_task, sub_task_results)
            
            # Step 5: Calculate metrics
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            final_result.total_time = processing_time
            final_result.performance_metrics = self._calculate_performance_metrics(
                sub_task_results, processing_time
            )
            
            # Store in history
            self.processing_history.append(final_result)
            
            logger.info(f"Ensemble reasoning completed for task {task.task_id} in {processing_time:.2f}s")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Ensemble reasoning failed for task {task.task_id}: {str(e)}")
            raise
    
    async def _execute_sub_tasks(self, ensemble_task: EnsembleTask) -> List[SubTaskResult]:
        """Execute all sub-tasks according to their dependencies and strategy."""
        
        if ensemble_task.decomposition_strategy == DecompositionStrategy.SEQUENTIAL:
            return await self._execute_sequential(ensemble_task)
        elif ensemble_task.decomposition_strategy == DecompositionStrategy.PARALLEL:
            return await self._execute_parallel(ensemble_task)
        elif ensemble_task.decomposition_strategy == DecompositionStrategy.HIERARCHICAL:
            return await self._execute_hierarchical(ensemble_task)
        else:  # DYNAMIC
            return await self._execute_dynamic(ensemble_task)
    
    async def _execute_sequential(self, ensemble_task: EnsembleTask) -> List[SubTaskResult]:
        """Execute sub-tasks sequentially."""
        results = []
        
        for sub_task in ensemble_task.sub_tasks:
            assignment = self._find_assignment(sub_task.sub_task_id, ensemble_task.assignments)
            result = await self._execute_single_sub_task(sub_task, assignment)
            results.append(result)
            
            # If a critical task fails, stop execution
            if not result.success and sub_task.priority == TaskPriority.CRITICAL:
                logger.warning(f"Critical sub-task {sub_task.sub_task_id} failed, stopping execution")
                break
        
        return results
    
    async def _execute_parallel(self, ensemble_task: EnsembleTask) -> List[SubTaskResult]:
        """Execute sub-tasks in parallel."""
        
        async def execute_with_assignment(sub_task: SubTask) -> SubTaskResult:
            assignment = self._find_assignment(sub_task.sub_task_id, ensemble_task.assignments)
            return await self._execute_single_sub_task(sub_task, assignment)
        
        # Execute all sub-tasks concurrently
        tasks = [execute_with_assignment(sub_task) for sub_task in ensemble_task.sub_tasks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                sub_task = ensemble_task.sub_tasks[i]
                assignment = self._find_assignment(sub_task.sub_task_id, ensemble_task.assignments)
                final_results.append(
                    SubTaskResult(
                        sub_task=sub_task,
                        assignment=assignment,
                        result=ProcessingResult(
                            task_id=sub_task.sub_task_id,
                            model_id=assignment.model_id,
                            content="",
                            confidence=0.0
                        ),
                        success=False,
                        error_message=str(result)
                    )
                )
            else:
                final_results.append(result)
        
        return final_results
    
    async def _execute_hierarchical(self, ensemble_task: EnsembleTask) -> List[SubTaskResult]:
        """Execute sub-tasks respecting hierarchical dependencies."""
        results = []
        completed_tasks = set()
        
        # Build dependency graph
        dependency_map = {}
        for sub_task in ensemble_task.sub_tasks:
            dependency_map[sub_task.sub_task_id] = sub_task.dependencies
        
        # Execute tasks in dependency order
        while len(completed_tasks) < len(ensemble_task.sub_tasks):
            ready_tasks = []
            
            for sub_task in ensemble_task.sub_tasks:
                if (sub_task.sub_task_id not in completed_tasks and
                    all(dep in completed_tasks for dep in sub_task.dependencies)):
                    ready_tasks.append(sub_task)
            
            if not ready_tasks:
                # Circular dependency or other issue
                logger.error("No ready tasks found, possible circular dependency")
                break
            
            # Execute ready tasks in parallel
            async def execute_ready_task(sub_task: SubTask) -> SubTaskResult:
                assignment = self._find_assignment(sub_task.sub_task_id, ensemble_task.assignments)
                return await self._execute_single_sub_task(sub_task, assignment)
            
            batch_tasks = [execute_ready_task(task) for task in ready_tasks]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    sub_task = ready_tasks[i]
                    assignment = self._find_assignment(sub_task.sub_task_id, ensemble_task.assignments)
                    result = SubTaskResult(
                        sub_task=sub_task,
                        assignment=assignment,
                        result=ProcessingResult(
                            task_id=sub_task.sub_task_id,
                            model_id=assignment.model_id,
                            content="",
                            confidence=0.0
                        ),
                        success=False,
                        error_message=str(result)
                    )
                
                results.append(result)
                completed_tasks.add(result.sub_task.sub_task_id)
        
        return results
    
    async def _execute_dynamic(self, ensemble_task: EnsembleTask) -> List[SubTaskResult]:
        """Execute sub-tasks with dynamic adaptation."""
        # For now, fall back to parallel execution
        # In practice, this would adapt based on intermediate results
        return await self._execute_parallel(ensemble_task)
    
    async def _execute_single_sub_task(
        self, 
        sub_task: SubTask, 
        assignment: ModelAssignment
    ) -> SubTaskResult:
        """Execute a single sub-task with the assigned model."""
        
        retry_count = 0
        last_error = None
        
        while retry_count <= sub_task.max_retries:
            try:
                # Create task context for the sub-task
                task_context = TaskContext(
                    task_id=sub_task.sub_task_id,
                    task_type=sub_task.task_type,
                    content=sub_task.content,
                    metadata=sub_task.metadata
                )
                
                # Execute with timeout
                result = await asyncio.wait_for(
                    self.model_provider.process_task(task_context, assignment.model_id),
                    timeout=sub_task.timeout_seconds
                )
                
                return SubTaskResult(
                    sub_task=sub_task,
                    assignment=assignment,
                    result=result,
                    success=True,
                    retry_count=retry_count
                )
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count <= sub_task.max_retries:
                    logger.warning(
                        f"Sub-task {sub_task.sub_task_id} failed (attempt {retry_count}), retrying: {str(e)}"
                    )
                    await asyncio.sleep(1.0 * retry_count)  # Exponential backoff
        
        # All retries failed
        logger.error(f"Sub-task {sub_task.sub_task_id} failed after {retry_count} attempts")
        
        return SubTaskResult(
            sub_task=sub_task,
            assignment=assignment,
            result=ProcessingResult(
                task_id=sub_task.sub_task_id,
                model_id=assignment.model_id,
                content="",
                confidence=0.0
            ),
            success=False,
            retry_count=retry_count,
            error_message=str(last_error)
        )
    
    def _find_assignment(self, sub_task_id: str, assignments: List[ModelAssignment]) -> ModelAssignment:
        """Find the assignment for a specific sub-task."""
        for assignment in assignments:
            if assignment.sub_task_id == sub_task_id:
                return assignment
        raise ValueError(f"No assignment found for sub-task {sub_task_id}")
    
    async def _aggregate_results(
        self, 
        ensemble_task: EnsembleTask, 
        sub_task_results: List[SubTaskResult]
    ) -> EnsembleResult:
        """Aggregate sub-task results into a final ensemble result."""
        
        # Combine successful results
        successful_results = [r for r in sub_task_results if r.success]
        failed_results = [r for r in sub_task_results if not r.success]
        
        # Generate final content
        final_content = self._synthesize_final_content(successful_results, ensemble_task)
        
        # Calculate metrics
        total_cost = sum(r.assignment.estimated_cost for r in sub_task_results)
        success_rate = len(successful_results) / len(sub_task_results) if sub_task_results else 0.0
        
        overall_quality = self._calculate_overall_quality(successful_results)
        
        return EnsembleResult(
            task_id=ensemble_task.task_id,
            original_task=ensemble_task.original_task,
            final_content=final_content,
            sub_task_results=sub_task_results,
            decomposition_strategy=ensemble_task.decomposition_strategy,
            overall_quality=overall_quality,
            performance_metrics=PerformanceMetrics(),  # Will be filled by caller
            total_cost=total_cost,
            total_time=0.0,  # Will be filled by caller
            success_rate=success_rate,
            metadata={
                "successful_sub_tasks": len(successful_results),
                "failed_sub_tasks": len(failed_results),
                "total_sub_tasks": len(sub_task_results)
            }
        )
    
    def _synthesize_final_content(
        self, 
        successful_results: List[SubTaskResult], 
        ensemble_task: EnsembleTask
    ) -> str:
        """Synthesize final content from successful sub-task results."""
        
        if not successful_results:
            return "Unable to complete task due to sub-task failures."
        
        # Group results by priority
        critical_results = [r for r in successful_results if r.sub_task.priority == TaskPriority.CRITICAL]
        high_results = [r for r in successful_results if r.sub_task.priority == TaskPriority.HIGH]
        medium_results = [r for r in successful_results if r.sub_task.priority == TaskPriority.MEDIUM]
        low_results = [r for r in successful_results if r.sub_task.priority == TaskPriority.LOW]
        
        # Build final content
        content_parts = []
        
        # Add critical results first
        for result in critical_results:
            content_parts.append(f"Critical Component: {result.result.content}")
        
        # Add high priority results
        for result in high_results:
            content_parts.append(f"Key Finding: {result.result.content}")
        
        # Add medium priority results
        for result in medium_results:
            content_parts.append(f"Supporting Analysis: {result.result.content}")
        
        # Add low priority results if space allows
        for result in low_results:
            content_parts.append(f"Additional Insight: {result.result.content}")
        
        if not content_parts:
            # Fallback: combine all content
            content_parts = [r.result.content for r in successful_results]
        
        return "\n\n".join(content_parts)
    
    def _calculate_overall_quality(self, successful_results: List[SubTaskResult]) -> QualityMetrics:
        """Calculate overall quality metrics from sub-task results."""
        
        if not successful_results:
            return QualityMetrics()
        
        confidences = [r.result.confidence for r in successful_results]
        
        accuracy = sum(confidences) / len(confidences)
        consistency = 1.0 - (max(confidences) - min(confidences)) if len(confidences) > 1 else 1.0
        completeness = len(successful_results) / len(successful_results)  # Always 1.0 for successful
        relevance = accuracy  # Simplified
        confidence = accuracy
        coherence = consistency  # Simplified
        
        return QualityMetrics(
            accuracy=accuracy,
            consistency=consistency,
            completeness=completeness,
            relevance=relevance,
            confidence=confidence,
            coherence=coherence
        )
    
    def _calculate_performance_metrics(
        self, 
        sub_task_results: List[SubTaskResult], 
        total_time: float
    ) -> PerformanceMetrics:
        """Calculate performance metrics for the ensemble process."""
        
        if not sub_task_results:
            return PerformanceMetrics()
        
        successful_results = [r for r in sub_task_results if r.success]
        
        avg_response_time = (
            sum(r.result.processing_time for r in successful_results) / len(successful_results)
            if successful_results else 0.0
        )
        
        throughput = len(successful_results) / total_time if total_time > 0 else 0.0
        success_rate = len(successful_results) / len(sub_task_results)
        error_rate = 1.0 - success_rate
        
        # Calculate cost efficiency (results per unit cost)
        total_cost = sum(r.assignment.estimated_cost for r in sub_task_results)
        cost_efficiency = len(successful_results) / max(total_cost, 0.001)
        
        # Resource utilization (successful tasks / total attempted)
        resource_utilization = success_rate
        
        return PerformanceMetrics(
            response_time=avg_response_time,
            throughput=throughput,
            success_rate=success_rate,
            error_rate=error_rate,
            cost_efficiency=cost_efficiency,
            resource_utilization=resource_utilization
        )
    
    def get_processing_history(self, limit: Optional[int] = None) -> List[EnsembleResult]:
        """Get historical ensemble processing results."""
        if limit:
            return self.processing_history[-limit:]
        return self.processing_history.copy()