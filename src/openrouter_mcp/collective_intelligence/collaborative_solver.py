"""
Collaborative Problem Solving

This module implements coordinated problem-solving workflows that combine
multiple collective intelligence components to tackle complex challenges
through collaborative AI orchestration.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from .base import (
    CollectiveIntelligenceComponent,
    TaskContext,
    ProcessingResult,
    ModelProvider,
    QualityMetrics,
    PerformanceMetrics
)
from .consensus_engine import ConsensusEngine, ConsensusResult
from .ensemble_reasoning import EnsembleReasoner, EnsembleResult
from .adaptive_router import AdaptiveRouter, RoutingDecision
from .cross_validator import CrossValidator, ValidationResult
from .operational_controls import (
    OperationalConfig,
    ConcurrencyLimiter,
    QuotaTracker,
    FailureController,
    StorageManager,
    TaskCancellationManager
)

logger = logging.getLogger(__name__)


class SolvingStrategy(Enum):
    """Strategies for collaborative problem solving."""
    SEQUENTIAL = "sequential"  # Components work in sequence
    PARALLEL = "parallel"  # Components work simultaneously
    HIERARCHICAL = "hierarchical"  # Structured problem decomposition
    ITERATIVE = "iterative"  # Iterative refinement approach
    ADAPTIVE = "adaptive"  # Dynamic strategy selection


@dataclass
class SolvingSession:
    """A collaborative problem-solving session."""
    session_id: str
    original_task: TaskContext
    strategy: SolvingStrategy
    components_used: List[str]
    intermediate_results: List[Any]
    final_result: Optional[Any] = None
    quality_metrics: Optional[QualityMetrics] = None
    performance_metrics: Optional[PerformanceMetrics] = None
    session_metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None


@dataclass
class SolvingResult:
    """Final result from collaborative problem solving."""
    session: SolvingSession
    final_content: str
    confidence_score: float
    quality_assessment: QualityMetrics
    solution_path: List[str]  # Steps taken to reach solution
    alternative_solutions: List[str]
    improvement_suggestions: List[str]
    total_processing_time: float
    component_contributions: Dict[str, float]  # How much each component contributed
    metadata: Dict[str, Any] = field(default_factory=dict)


class CollaborativeSolver(CollectiveIntelligenceComponent):
    """
    Orchestrates multiple collective intelligence components to solve
    complex problems through collaborative AI workflows.
    """
    
    def __init__(self, model_provider: ModelProvider, operational_config: Optional[OperationalConfig] = None):
        super().__init__(model_provider)

        # Initialize operational controls
        self.operational_config = operational_config or OperationalConfig.conservative()
        self.concurrency_limiter = ConcurrencyLimiter(self.operational_config.concurrency)
        self.quota_tracker = QuotaTracker(self.operational_config.quota)
        self.failure_controller = FailureController(self.operational_config.failure)
        self.storage_manager = StorageManager(self.operational_config.storage)
        self.cancellation_manager = TaskCancellationManager()

        # Initialize component instances with same operational config
        self.consensus_engine = ConsensusEngine(model_provider)
        self.ensemble_reasoner = EnsembleReasoner(model_provider)
        self.adaptive_router = AdaptiveRouter(model_provider)
        self.cross_validator = CrossValidator(model_provider)

        # Session tracking
        self.active_sessions: Dict[str, SolvingSession] = {}
    
    async def process(self, task: TaskContext, **kwargs) -> SolvingResult:
        """
        Solve a complex problem using collaborative AI components.

        Args:
            task: The problem to solve
            **kwargs: Additional solving options

        Returns:
            SolvingResult with comprehensive solution analysis

        Raises:
            RuntimeError: If quota exceeded or operational limits hit
            asyncio.CancelledError: If execution cancelled due to failures
        """
        strategy_input = kwargs.get('strategy', SolvingStrategy.ADAPTIVE)

        # Convert string strategy to enum if needed
        if isinstance(strategy_input, str):
            try:
                strategy = SolvingStrategy(strategy_input.lower())
            except ValueError:
                logger.warning(f"Unknown strategy '{strategy_input}', using ADAPTIVE")
                strategy = SolvingStrategy.ADAPTIVE
        else:
            strategy = strategy_input

        session_id = f"session_{task.task_id}_{datetime.now().timestamp()}"
        request_id = task.task_id

        # Acquire task execution slot
        if not await self.concurrency_limiter.acquire_task_slot(session_id):
            raise RuntimeError(f"Failed to acquire execution slot for {session_id} - system at capacity")

        # Create solving session
        session = SolvingSession(
            session_id=session_id,
            original_task=task,
            strategy=strategy,
            components_used=[],
            intermediate_results=[]
        )

        self.active_sessions[session_id] = session

        try:
            # Check circuit breaker
            if not await self.failure_controller.check_circuit_breaker("collaborative_solver"):
                raise RuntimeError("Circuit breaker open for CollaborativeSolver - too many recent failures")

            # Check initial quota
            can_proceed, reason = await self.quota_tracker.check_and_increment(
                request_id,
                tokens=len(task.content),
                cost=0.0
            )
            if not can_proceed:
                raise RuntimeError(f"Quota check failed: {reason}")

            # Execute strategy with cancellation support
            if strategy == SolvingStrategy.SEQUENTIAL:
                result = await self._solve_sequential(session, request_id)
            elif strategy == SolvingStrategy.PARALLEL:
                result = await self._solve_parallel(session, request_id)
            elif strategy == SolvingStrategy.HIERARCHICAL:
                result = await self._solve_hierarchical(session, request_id)
            elif strategy == SolvingStrategy.ITERATIVE:
                result = await self._solve_iterative(session, request_id)
            else:  # ADAPTIVE
                result = await self._solve_adaptive(session, request_id)

            # Finalize session
            session.end_time = datetime.now()
            session.final_result = result

            # Move to storage with TTL management
            del self.active_sessions[session_id]
            await self.storage_manager.add_item(session_id, session)

            # Record success for circuit breaker
            self.failure_controller.record_circuit_breaker_success("collaborative_solver")

            logger.info(f"Collaborative solving completed for session {session_id}")

            return result

        except asyncio.CancelledError:
            logger.warning(f"Collaborative solving cancelled for {session_id}")
            self.failure_controller.record_circuit_breaker_failure("collaborative_solver")
            raise

        except Exception as e:
            logger.error(f"Collaborative solving failed for session {session_id}: {str(e)}", exc_info=True)

            # Record failure and check if we should cancel pending tasks
            should_cancel = await self.failure_controller.record_failure(
                request_id,
                str(e),
                is_critical=isinstance(e, RuntimeError)
            )

            if should_cancel:
                cancelled = await self.cancellation_manager.cancel_all_tasks(
                    request_id,
                    f"Cancelling due to failure: {str(e)}"
                )
                logger.info(f"Cancelled {cancelled} pending tasks for {request_id}")

            self.failure_controller.record_circuit_breaker_failure("collaborative_solver")

            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            raise

        finally:
            # Always release the execution slot
            self.concurrency_limiter.release_task_slot(session_id)
            # Reset quota tracking for this request
            self.quota_tracker.reset_request(request_id)
    
    async def _solve_sequential(self, session: SolvingSession, request_id: str) -> SolvingResult:
        """Solve problem using sequential component workflow."""
        task = session.original_task
        
        # Step 1: Route to best initial model
        router_decision = await self.adaptive_router.process(task)
        session.components_used.append("adaptive_router")
        session.intermediate_results.append(router_decision)
        
        # Step 2: Get initial result using ensemble reasoning
        ensemble_result = await self.ensemble_reasoner.process(task)
        session.components_used.append("ensemble_reasoner")
        session.intermediate_results.append(ensemble_result)
        
        # Step 3: Validate the result
        if ensemble_result.sub_task_results:
            # Use the best sub-task result for validation
            best_subtask = max(
                ensemble_result.sub_task_results,
                key=lambda x: x.result.confidence if x.success else 0
            )
            validation_result = await self.cross_validator.process(
                best_subtask.result, task
            )
        else:
            # Create a dummy result for validation
            dummy_result = ProcessingResult(
                task_id=task.task_id,
                model_id="ensemble",
                content=ensemble_result.final_content,
                confidence=0.8
            )
            validation_result = await self.cross_validator.process(dummy_result, task)
        
        session.components_used.append("cross_validator")
        session.intermediate_results.append(validation_result)
        
        # Step 4: Build consensus if validation suggests improvements
        if not validation_result.is_valid:
            consensus_result = await self.consensus_engine.process(task)
            session.components_used.append("consensus_engine")
            session.intermediate_results.append(consensus_result)
            final_content = consensus_result.consensus_content
        else:
            final_content = ensemble_result.final_content
        
        return self._create_solving_result(session, final_content)
    
    async def _solve_parallel(self, session: SolvingSession, request_id: str) -> SolvingResult:
        """Solve problem using parallel component workflow."""
        task = session.original_task
        
        # Run multiple components in parallel
        results = await asyncio.gather(
            self.ensemble_reasoner.process(task),
            self.consensus_engine.process(task),
            return_exceptions=True
        )
        
        ensemble_result = results[0] if not isinstance(results[0], Exception) else None
        consensus_result = results[1] if not isinstance(results[1], Exception) else None
        
        session.components_used.extend(["ensemble_reasoner", "consensus_engine"])
        session.intermediate_results.extend([r for r in results if not isinstance(r, Exception)])
        
        # Choose best result or combine them
        if ensemble_result and consensus_result:
            # Combine results based on confidence
            if ensemble_result.success_rate > consensus_result.confidence_score:
                final_content = ensemble_result.final_content
            else:
                final_content = consensus_result.consensus_content
        elif ensemble_result:
            final_content = ensemble_result.final_content
        elif consensus_result:
            final_content = consensus_result.consensus_content
        else:
            final_content = "Unable to generate solution due to component failures"
        
        return self._create_solving_result(session, final_content)
    
    async def _solve_hierarchical(self, session: SolvingSession, request_id: str) -> SolvingResult:
        """Solve problem using hierarchical workflow."""
        task = session.original_task
        
        # Level 1: Route and decompose
        router_decision = await self.adaptive_router.process(task)
        ensemble_result = await self.ensemble_reasoner.process(task)
        
        session.components_used.extend(["adaptive_router", "ensemble_reasoner"])
        session.intermediate_results.extend([router_decision, ensemble_result])
        
        # Level 2: Validate and improve
        if ensemble_result.sub_task_results:
            best_subtask = max(
                ensemble_result.sub_task_results,
                key=lambda x: x.result.confidence if x.success else 0
            )
            validation_result = await self.cross_validator.process(
                best_subtask.result, task
            )
            session.components_used.append("cross_validator")
            session.intermediate_results.append(validation_result)
            
            # Level 3: Consensus if needed
            if not validation_result.is_valid:
                consensus_result = await self.consensus_engine.process(task)
                session.components_used.append("consensus_engine")
                session.intermediate_results.append(consensus_result)
                final_content = consensus_result.consensus_content
            else:
                final_content = ensemble_result.final_content
        else:
            final_content = ensemble_result.final_content
        
        return self._create_solving_result(session, final_content)
    
    async def _solve_iterative(self, session: SolvingSession, request_id: str) -> SolvingResult:
        """Solve problem using iterative refinement."""
        task = session.original_task
        current_content = ""
        iteration = 0
        max_iterations = 3
        
        while iteration < max_iterations:
            # Get current best solution
            if iteration == 0:
                # Start with ensemble reasoning
                ensemble_result = await self.ensemble_reasoner.process(task)
                current_content = ensemble_result.final_content
                session.components_used.append(f"ensemble_reasoner_iter_{iteration}")
                session.intermediate_results.append(ensemble_result)
            else:
                # Use consensus to refine
                consensus_result = await self.consensus_engine.process(task)
                current_content = consensus_result.consensus_content
                session.components_used.append(f"consensus_engine_iter_{iteration}")
                session.intermediate_results.append(consensus_result)
            
            # Validate current solution
            dummy_result = ProcessingResult(
                task_id=f"{task.task_id}_iter_{iteration}",
                model_id="iterative",
                content=current_content,
                confidence=0.8
            )
            
            validation_result = await self.cross_validator.process(dummy_result, task)
            session.components_used.append(f"cross_validator_iter_{iteration}")
            session.intermediate_results.append(validation_result)
            
            # Check if solution is good enough
            if validation_result.is_valid and validation_result.validation_confidence > 0.8:
                break
            
            iteration += 1
        
        return self._create_solving_result(session, current_content)
    
    async def _solve_adaptive(self, session: SolvingSession, request_id: str) -> SolvingResult:
        """Solve problem using adaptive strategy selection."""
        task = session.original_task

        # Analyze task to determine best strategy
        complexity = self._assess_task_complexity(task)

        if complexity < 0.3:
            # Simple task - use sequential
            return await self._solve_sequential(session, request_id)
        elif complexity < 0.7:
            # Medium complexity - use hierarchical
            return await self._solve_hierarchical(session, request_id)
        else:
            # High complexity - use iterative
            return await self._solve_iterative(session, request_id)
    
    def _assess_task_complexity(self, task: TaskContext) -> float:
        """Assess the complexity of a task (0.0 to 1.0)."""
        complexity = 0.0
        
        # Content length factor
        content_complexity = min(1.0, len(task.content) / 1000.0)
        complexity += content_complexity * 0.3
        
        # Requirements complexity
        req_complexity = len(task.requirements) / 10.0
        complexity += min(1.0, req_complexity) * 0.2
        
        # Task type complexity
        type_complexity = {
            "reasoning": 0.8,
            "creative": 0.7,
            "analysis": 0.6,
            "code_generation": 0.9,
            "factual": 0.3
        }.get(task.task_type.value, 0.5)
        
        complexity += type_complexity * 0.5
        
        return min(1.0, complexity)
    
    def _create_solving_result(self, session: SolvingSession, final_content: str) -> SolvingResult:
        """Create the final solving result."""
        
        # Calculate quality metrics
        quality_metrics = QualityMetrics(
            accuracy=0.8,  # Default values - would be calculated from components
            consistency=0.8,
            completeness=0.8,
            relevance=0.8,
            confidence=0.8,
            coherence=0.8
        )
        
        # Calculate component contributions
        component_contributions = {}
        total_components = len(session.components_used)
        for component in set(session.components_used):
            contribution = session.components_used.count(component) / total_components
            component_contributions[component] = contribution
        
        # Calculate processing time
        if session.end_time and session.start_time:
            processing_time = (session.end_time - session.start_time).total_seconds()
        else:
            processing_time = 0.0
        
        return SolvingResult(
            session=session,
            final_content=final_content,
            confidence_score=quality_metrics.overall_score(),
            quality_assessment=quality_metrics,
            solution_path=[f"Step {i+1}: {comp}" for i, comp in enumerate(session.components_used)],
            alternative_solutions=[],  # Would be populated from intermediate results
            improvement_suggestions=[],  # Would be generated from validation results
            total_processing_time=processing_time,
            component_contributions=component_contributions,
            metadata={
                'strategy_used': session.strategy.value,
                'components_count': len(session.components_used),
                'intermediate_results_count': len(session.intermediate_results)
            }
        )
    
    def get_active_sessions(self) -> Dict[str, SolvingSession]:
        """Get currently active solving sessions."""
        return self.active_sessions.copy()

    def get_completed_sessions(self, limit: Optional[int] = None) -> List[SolvingSession]:
        """Get completed solving sessions with TTL enforcement."""
        return self.storage_manager.get_items(limit)

    def get_session_by_id(self, session_id: str) -> Optional[SolvingSession]:
        """Get a specific session by ID."""
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]

        # Check storage for completed sessions
        for session in self.storage_manager.get_items():
            if session.session_id == session_id:
                return session

        return None

    def get_operational_metrics(self) -> Dict[str, Any]:
        """Get operational metrics and limits status."""
        return {
            'active_sessions': len(self.active_sessions),
            'active_tasks': self.concurrency_limiter.get_active_count(),
            'at_capacity': self.concurrency_limiter.is_at_capacity(),
            'completed_sessions_count': self.storage_manager.get_count(),
            'max_history_size': self.operational_config.storage.max_history_size,
            'concurrency_config': {
                'max_concurrent_tasks': self.operational_config.concurrency.max_concurrent_tasks,
                'max_concurrent_models': self.operational_config.concurrency.max_concurrent_models,
            },
            'quota_config': {
                'max_api_calls_per_request': self.operational_config.quota.max_api_calls_per_request,
                'max_tokens_per_request': self.operational_config.quota.max_tokens_per_request,
                'max_cost_per_request': self.operational_config.quota.max_cost_per_request,
            }
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown the collaborative solver."""
        logger.info("Shutting down CollaborativeSolver...")

        # Shutdown sub-components
        if hasattr(self.consensus_engine, 'shutdown'):
            await self.consensus_engine.shutdown()

        await self.storage_manager.shutdown()

        # Cancel any remaining tasks
        for request_id in list(self.cancellation_manager.pending_tasks.keys()):
            await self.cancellation_manager.cancel_all_tasks(request_id, "Shutdown requested")

        # Clean up active sessions
        self.active_sessions.clear()

        logger.info("CollaborativeSolver shutdown complete")