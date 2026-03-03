"""
Collaborative Problem Solving

This module implements coordinated problem-solving workflows that combine
multiple collective intelligence components to tackle complex challenges
through collaborative AI orchestration.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .adaptive_router import AdaptiveRouter
from .base import (
    CollectiveIntelligenceComponent,
    ModelProvider,
    PerformanceMetrics,
    ProcessingResult,
    QualityMetrics,
    TaskContext,
)
from .consensus_engine import ConsensusEngine
from .cross_validator import CrossValidator
from .ensemble_reasoning import EnsembleReasoner, EnsembleResult
from .operational_controls import OperationalConfig, init_operational_controls

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

    def __init__(
        self,
        model_provider: ModelProvider,
        operational_config: Optional[OperationalConfig] = None,
    ):
        super().__init__(model_provider)

        # Initialize operational controls
        controls = init_operational_controls(operational_config)
        self.operational_config = controls.config
        self.concurrency_limiter = controls.concurrency_limiter
        self.quota_tracker = controls.quota_tracker
        self.failure_controller = controls.failure_controller
        self.storage_manager = controls.storage_manager
        self.cancellation_manager = controls.cancellation_manager

        # Initialize component instances with same operational config
        self.consensus_engine = ConsensusEngine(model_provider)
        self.ensemble_reasoner = EnsembleReasoner(model_provider)
        self.adaptive_router = AdaptiveRouter(model_provider)
        self.cross_validator = CrossValidator(model_provider)

        # Session tracking
        self.active_sessions: Dict[str, SolvingSession] = {}

    @property
    def completed_sessions(self) -> List[SolvingSession]:
        """Get completed sessions as a list for backward compatibility."""
        return self.storage_manager.get_items()

    @completed_sessions.setter
    def completed_sessions(self, value: List[SolvingSession]) -> None:
        """Set completed sessions for backward compatibility."""
        from collections import deque
        from datetime import datetime

        # Clear existing items
        self.storage_manager.items = deque(
            maxlen=self.storage_manager.config.max_history_size
        )
        self.storage_manager.item_timestamps = {}
        # Add new items with generated IDs
        for i, item in enumerate(value):
            item_id = f"session_{i}_{datetime.now().timestamp()}"
            self.storage_manager.items.append((item_id, item))
            self.storage_manager.item_timestamps[item_id] = datetime.now()

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
        strategy_input = kwargs.get("strategy", SolvingStrategy.ADAPTIVE)

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
            raise RuntimeError(
                f"Failed to acquire execution slot for {session_id} - system at capacity"
            )

        # Create solving session
        session = SolvingSession(
            session_id=session_id,
            original_task=task,
            strategy=strategy,
            components_used=[],
            intermediate_results=[],
        )

        self.active_sessions[session_id] = session

        try:
            # Check circuit breaker
            if not await self.failure_controller.check_circuit_breaker(
                "collaborative_solver"
            ):
                raise RuntimeError(
                    "Circuit breaker open for CollaborativeSolver - too many recent failures"
                )

            # Check initial quota
            can_proceed, reason = await self.quota_tracker.check_and_increment(
                request_id, tokens=len(task.content), cost=0.0
            )
            if not can_proceed:
                raise RuntimeError(f"Quota check failed: {reason}")

            # Execute strategy with cancellation support
            strategy_dispatch = {
                SolvingStrategy.SEQUENTIAL: self._solve_sequential,
                SolvingStrategy.PARALLEL: self._solve_parallel,
                SolvingStrategy.HIERARCHICAL: self._solve_hierarchical,
                SolvingStrategy.ITERATIVE: self._solve_iterative,
                SolvingStrategy.ADAPTIVE: self._solve_adaptive,
            }
            handler = strategy_dispatch.get(strategy, self._solve_adaptive)
            result = await handler(session, request_id)

            # Finalize session
            session.end_time = datetime.now()
            session.final_result = result

            # Move to storage with TTL management
            del self.active_sessions[session_id]
            await self.storage_manager.add_item(session_id, session)

            # Record success for circuit breaker
            self.failure_controller.record_circuit_breaker_success(
                "collaborative_solver"
            )

            logger.info(f"Collaborative solving completed for session {session_id}")

            return result

        except asyncio.CancelledError:
            logger.warning(f"Collaborative solving cancelled for {session_id}")
            self.failure_controller.record_circuit_breaker_failure(
                "collaborative_solver"
            )
            raise

        except Exception as e:
            logger.error(
                f"Collaborative solving failed for session {session_id}: {str(e)}",
                exc_info=True,
            )

            # Record failure and check if we should cancel pending tasks
            should_cancel = await self.failure_controller.record_failure(
                request_id, str(e), is_critical=isinstance(e, RuntimeError)
            )

            if should_cancel:
                cancelled = await self.cancellation_manager.cancel_all_tasks(
                    request_id, f"Cancelling due to failure: {str(e)}"
                )
                logger.info(f"Cancelled {cancelled} pending tasks for {request_id}")

            self.failure_controller.record_circuit_breaker_failure(
                "collaborative_solver"
            )

            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            raise

        finally:
            # Always release the execution slot
            self.concurrency_limiter.release_task_slot(session_id)
            # Reset quota tracking for this request
            self.quota_tracker.reset_request(request_id)

    def _record_component(
        self, session: SolvingSession, component_name: str, result: Optional[Any] = None
    ) -> None:
        """Record component usage and optional intermediate result."""
        session.components_used.append(component_name)
        if result is not None:
            session.intermediate_results.append(result)

    def _select_best_subtask_result(
        self, ensemble_result: EnsembleResult
    ) -> Optional[ProcessingResult]:
        """Select the best sub-task result based on confidence."""
        if not ensemble_result.sub_task_results:
            return None
        best_subtask = max(
            ensemble_result.sub_task_results,
            key=lambda x: x.result.confidence if x.success else 0,
        )
        return best_subtask.result

    async def _solve_sequential(
        self, session: SolvingSession, request_id: str
    ) -> SolvingResult:
        """Solve problem using sequential component workflow."""
        task = session.original_task

        # Step 1: Route to best initial model
        router_decision = await self.adaptive_router.process(task)
        self._record_component(session, "adaptive_router", router_decision)

        # Step 2: Get initial result using ensemble reasoning
        ensemble_result = await self.ensemble_reasoner.process(task)
        self._record_component(session, "ensemble_reasoner", ensemble_result)

        # Step 3: Validate the result
        best_result = self._select_best_subtask_result(ensemble_result)
        if best_result:
            validation_result = await self.cross_validator.process(best_result, task)
        else:
            # Create a dummy result for validation
            dummy_result = ProcessingResult(
                task_id=task.task_id,
                model_id="ensemble",
                content=ensemble_result.final_content,
                confidence=0.8,
            )
            validation_result = await self.cross_validator.process(dummy_result, task)

        self._record_component(session, "cross_validator", validation_result)

        # Step 4: Build consensus if validation suggests improvements
        if not validation_result.is_valid:
            consensus_result = await self.consensus_engine.process(task)
            self._record_component(session, "consensus_engine", consensus_result)
            final_content = consensus_result.consensus_content
        else:
            final_content = ensemble_result.final_content

        return self._create_solving_result(session, final_content)

    async def _solve_parallel(
        self, session: SolvingSession, request_id: str
    ) -> SolvingResult:
        """Solve problem using parallel component workflow."""
        task = session.original_task

        # Run multiple components in parallel
        results = await asyncio.gather(
            self.ensemble_reasoner.process(task),
            self.consensus_engine.process(task),
            return_exceptions=True,
        )

        ensemble_result = results[0] if not isinstance(results[0], Exception) else None
        consensus_result = results[1] if not isinstance(results[1], Exception) else None

        self._record_component(session, "ensemble_reasoner", ensemble_result)
        self._record_component(session, "consensus_engine", consensus_result)

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

    async def _solve_hierarchical(
        self, session: SolvingSession, request_id: str
    ) -> SolvingResult:
        """Solve problem using hierarchical workflow."""
        task = session.original_task

        # Level 1: Route and decompose
        router_decision = await self.adaptive_router.process(task)
        ensemble_result = await self.ensemble_reasoner.process(task)

        self._record_component(session, "adaptive_router", router_decision)
        self._record_component(session, "ensemble_reasoner", ensemble_result)

        # Level 2: Validate and improve
        best_result = self._select_best_subtask_result(ensemble_result)
        if best_result:
            validation_result = await self.cross_validator.process(best_result, task)
            self._record_component(session, "cross_validator", validation_result)

            # Level 3: Consensus if needed
            if not validation_result.is_valid:
                consensus_result = await self.consensus_engine.process(task)
                self._record_component(session, "consensus_engine", consensus_result)
                final_content = consensus_result.consensus_content
            else:
                final_content = ensemble_result.final_content
        else:
            final_content = ensemble_result.final_content

        return self._create_solving_result(session, final_content)

    async def _solve_iterative(
        self, session: SolvingSession, request_id: str
    ) -> SolvingResult:
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
                self._record_component(
                    session, f"ensemble_reasoner_iter_{iteration}", ensemble_result
                )
            else:
                # Use consensus to refine
                consensus_result = await self.consensus_engine.process(task)
                current_content = consensus_result.consensus_content
                self._record_component(
                    session, f"consensus_engine_iter_{iteration}", consensus_result
                )

            # Validate current solution
            dummy_result = ProcessingResult(
                task_id=f"{task.task_id}_iter_{iteration}",
                model_id="iterative",
                content=current_content,
                confidence=0.8,
            )

            validation_result = await self.cross_validator.process(dummy_result, task)
            self._record_component(
                session, f"cross_validator_iter_{iteration}", validation_result
            )

            # Check if solution is good enough
            if (
                validation_result.is_valid
                and validation_result.validation_confidence > 0.8
            ):
                break

            iteration += 1

        return self._create_solving_result(session, current_content)

    async def _solve_adaptive(
        self, session: SolvingSession, request_id: str
    ) -> SolvingResult:
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
            "factual": 0.3,
        }.get(task.task_type.value, 0.5)

        complexity += type_complexity * 0.5

        return min(1.0, complexity)

    def _create_solving_result(
        self, session: SolvingSession, final_content: str
    ) -> SolvingResult:
        """Create the final solving result."""

        # Calculate quality metrics
        quality_metrics = QualityMetrics(
            accuracy=0.8,  # Default values - would be calculated from components
            consistency=0.8,
            completeness=0.8,
            relevance=0.8,
            confidence=0.8,
            coherence=0.8,
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
            solution_path=[
                f"Step {i+1}: {comp}" for i, comp in enumerate(session.components_used)
            ],
            alternative_solutions=[],  # Would be populated from intermediate results
            improvement_suggestions=[],  # Would be generated from validation results
            total_processing_time=processing_time,
            component_contributions=component_contributions,
            metadata={
                "strategy_used": session.strategy.value,
                "components_count": len(session.components_used),
                "intermediate_results_count": len(session.intermediate_results),
            },
        )

    def get_active_sessions(self) -> Dict[str, SolvingSession]:
        """Get currently active solving sessions."""
        return self.active_sessions.copy()

    def get_completed_sessions(
        self, limit: Optional[int] = None
    ) -> List[SolvingSession]:
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
            "active_sessions": len(self.active_sessions),
            "active_tasks": self.concurrency_limiter.get_active_count(),
            "at_capacity": self.concurrency_limiter.is_at_capacity(),
            "completed_sessions_count": self.storage_manager.get_count(),
            **self.operational_config.limits_snapshot(),
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown the collaborative solver."""
        logger.info("Shutting down CollaborativeSolver...")

        # Shutdown sub-components
        if hasattr(self.consensus_engine, "shutdown"):
            await self.consensus_engine.shutdown()

        await self.storage_manager.shutdown()

        # Cancel any remaining tasks
        for request_id in list(self.cancellation_manager.pending_tasks.keys()):
            await self.cancellation_manager.cancel_all_tasks(
                request_id, "Shutdown requested"
            )

        # Clean up active sessions
        self.active_sessions.clear()

        logger.info("CollaborativeSolver shutdown complete")
