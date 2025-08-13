"""
Comprehensive test suite for the Collaborative Problem Solver.

This module provides thorough testing of the collaborative problem-solving
functionality that orchestrates multiple CI components.
"""

import asyncio
import pytest
from datetime import datetime
from typing import List
from unittest.mock import AsyncMock, Mock, patch

from src.openrouter_mcp.collective_intelligence.collaborative_solver import (
    CollaborativeSolver, SolvingStrategy, SolvingSession, SolvingResult
)
from src.openrouter_mcp.collective_intelligence.base import (
    TaskContext, ProcessingResult, ModelInfo, TaskType, QualityMetrics
)


class TestSolvingSession:
    """Test suite for SolvingSession dataclass."""

    @pytest.mark.unit
    def test_solving_session_creation(self):
        """Test SolvingSession creation and attributes."""
        task = TaskContext(
            task_id="test_task",
            task_type=TaskType.REASONING,
            content="Test problem"
        )
        
        session = SolvingSession(
            session_id="session_123",
            original_task=task,
            strategy=SolvingStrategy.SEQUENTIAL,
            components_used=["router", "ensemble"],
            intermediate_results=[]
        )
        
        assert session.session_id == "session_123"
        assert session.original_task == task
        assert session.strategy == SolvingStrategy.SEQUENTIAL
        assert session.components_used == ["router", "ensemble"]
        assert session.intermediate_results == []
        assert session.final_result is None
        assert session.quality_metrics is None
        assert isinstance(session.session_metadata, dict)
        assert isinstance(session.start_time, datetime)


class TestSolvingResult:
    """Test suite for SolvingResult dataclass."""

    @pytest.mark.unit
    def test_solving_result_creation(self):
        """Test SolvingResult creation and attributes."""
        session = Mock()
        quality_metrics = QualityMetrics(
            accuracy=0.9, consistency=0.8, completeness=0.85,
            relevance=0.9, confidence=0.85, coherence=0.8
        )
        
        result = SolvingResult(
            session=session,
            final_content="Final solution",
            confidence_score=0.85,
            quality_assessment=quality_metrics,
            solution_path=["Step 1", "Step 2"],
            alternative_solutions=["Alt 1", "Alt 2"],
            improvement_suggestions=["Suggestion 1"],
            total_processing_time=5.2,
            component_contributions={"router": 0.3, "ensemble": 0.7}
        )
        
        assert result.session == session
        assert result.final_content == "Final solution"
        assert result.confidence_score == 0.85
        assert result.quality_assessment == quality_metrics
        assert result.solution_path == ["Step 1", "Step 2"]
        assert result.alternative_solutions == ["Alt 1", "Alt 2"]
        assert result.improvement_suggestions == ["Suggestion 1"]
        assert result.total_processing_time == 5.2
        assert result.component_contributions == {"router": 0.3, "ensemble": 0.7}


class TestCollaborativeSolver:
    """Test suite for the CollaborativeSolver class."""

    @pytest.mark.unit
    def test_collaborative_solver_initialization(self, mock_model_provider):
        """Test CollaborativeSolver initialization."""
        solver = CollaborativeSolver(mock_model_provider)
        
        assert solver.model_provider == mock_model_provider
        assert hasattr(solver, 'consensus_engine')
        assert hasattr(solver, 'ensemble_reasoner')
        assert hasattr(solver, 'adaptive_router')
        assert hasattr(solver, 'cross_validator')
        assert isinstance(solver.active_sessions, dict)
        assert len(solver.active_sessions) == 0
        assert isinstance(solver.completed_sessions, list)
        assert len(solver.completed_sessions) == 0

    @pytest.mark.unit
    def test_assess_task_complexity_simple(self, mock_model_provider):
        """Test task complexity assessment for simple tasks."""
        solver = CollaborativeSolver(mock_model_provider)
        
        simple_task = TaskContext(
            task_id="simple",
            task_type=TaskType.FACTUAL,
            content="What is 2+2?",
            requirements={}
        )
        
        complexity = solver._assess_task_complexity(simple_task)
        
        assert 0.0 <= complexity <= 1.0
        assert complexity < 0.5  # Should be low complexity

    @pytest.mark.unit
    def test_assess_task_complexity_complex(self, mock_model_provider):
        """Test task complexity assessment for complex tasks."""
        solver = CollaborativeSolver(mock_model_provider)
        
        complex_task = TaskContext(
            task_id="complex",
            task_type=TaskType.CODE_GENERATION,
            content="A" * 1500,  # Long content
            requirements={
                "detail": "high",
                "testing": True,
                "documentation": True,
                "optimization": True,
                "error_handling": True
            }
        )
        
        complexity = solver._assess_task_complexity(complex_task)
        
        assert 0.0 <= complexity <= 1.0
        assert complexity > 0.7  # Should be high complexity

    @pytest.mark.asyncio
    @pytest.mark.integration
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.ConsensusEngine')
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.EnsembleReasoner')
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.AdaptiveRouter')
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.CrossValidator')
    async def test_solve_sequential_strategy(
        self, mock_cross_validator_class, mock_router_class, 
        mock_ensemble_class, mock_consensus_class, mock_model_provider, sample_task
    ):
        """Test sequential solving strategy."""
        
        # Setup mocks
        mock_router = AsyncMock()
        mock_router.process.return_value = Mock(selected_model_id="best_model")
        mock_router_class.return_value = mock_router
        
        mock_ensemble = AsyncMock()
        mock_ensemble_result = Mock()
        mock_ensemble_result.final_content = "Ensemble solution"
        mock_ensemble_result.sub_task_results = [
            Mock(success=True, result=Mock(confidence=0.9))
        ]
        mock_ensemble_result.success_rate = 0.9
        mock_ensemble.process.return_value = mock_ensemble_result
        mock_ensemble_class.return_value = mock_ensemble
        
        mock_validator = AsyncMock()
        mock_validation_result = Mock()
        mock_validation_result.is_valid = True
        mock_validator.process.return_value = mock_validation_result
        mock_cross_validator_class.return_value = mock_validator
        
        mock_consensus = AsyncMock()
        mock_consensus_class.return_value = mock_consensus
        
        solver = CollaborativeSolver(mock_model_provider)
        
        result = await solver.process(sample_task, strategy=SolvingStrategy.SEQUENTIAL)
        
        assert isinstance(result, SolvingResult)
        assert result.final_content == "Ensemble solution"
        assert "adaptive_router" in result.solution_path[0]
        assert "ensemble_reasoner" in result.solution_path[1]
        assert "cross_validator" in result.solution_path[2]

    @pytest.mark.asyncio
    @pytest.mark.integration
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.ConsensusEngine')
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.EnsembleReasoner')
    async def test_solve_parallel_strategy(
        self, mock_ensemble_class, mock_consensus_class, mock_model_provider, sample_task
    ):
        """Test parallel solving strategy."""
        
        # Setup mocks
        mock_ensemble = AsyncMock()
        mock_ensemble_result = Mock()
        mock_ensemble_result.final_content = "Ensemble solution"
        mock_ensemble_result.success_rate = 0.8
        mock_ensemble.process.return_value = mock_ensemble_result
        mock_ensemble_class.return_value = mock_ensemble
        
        mock_consensus = AsyncMock()
        mock_consensus_result = Mock()
        mock_consensus_result.consensus_content = "Consensus solution"
        mock_consensus_result.confidence_score = 0.7
        mock_consensus.process.return_value = mock_consensus_result
        mock_consensus_class.return_value = mock_consensus
        
        solver = CollaborativeSolver(mock_model_provider)
        
        result = await solver.process(sample_task, strategy=SolvingStrategy.PARALLEL)
        
        assert isinstance(result, SolvingResult)
        # Should choose ensemble result due to higher success rate
        assert result.final_content == "Ensemble solution"

    @pytest.mark.asyncio
    @pytest.mark.integration
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.ConsensusEngine')
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.EnsembleReasoner')
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.AdaptiveRouter')
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.CrossValidator')
    async def test_solve_hierarchical_strategy(
        self, mock_cross_validator_class, mock_router_class,
        mock_ensemble_class, mock_consensus_class, mock_model_provider, sample_task
    ):
        """Test hierarchical solving strategy."""
        
        # Setup mocks similar to sequential but with hierarchical flow
        mock_router = AsyncMock()
        mock_router.process.return_value = Mock(selected_model_id="best_model")
        mock_router_class.return_value = mock_router
        
        mock_ensemble = AsyncMock()
        mock_ensemble_result = Mock()
        mock_ensemble_result.final_content = "Hierarchical solution"
        mock_ensemble_result.sub_task_results = [
            Mock(success=True, result=Mock(confidence=0.9))
        ]
        mock_ensemble.process.return_value = mock_ensemble_result
        mock_ensemble_class.return_value = mock_ensemble
        
        mock_validator = AsyncMock()
        mock_validation_result = Mock()
        mock_validation_result.is_valid = True
        mock_validator.process.return_value = mock_validation_result
        mock_cross_validator_class.return_value = mock_validator
        
        mock_consensus = AsyncMock()
        mock_consensus_class.return_value = mock_consensus
        
        solver = CollaborativeSolver(mock_model_provider)
        
        result = await solver.process(sample_task, strategy=SolvingStrategy.HIERARCHICAL)
        
        assert isinstance(result, SolvingResult)
        assert result.final_content == "Hierarchical solution"

    @pytest.mark.asyncio
    @pytest.mark.integration
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.ConsensusEngine')
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.EnsembleReasoner')
    @patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.CrossValidator')
    async def test_solve_iterative_strategy(
        self, mock_cross_validator_class, mock_ensemble_class, 
        mock_consensus_class, mock_model_provider, sample_task
    ):
        """Test iterative solving strategy."""
        
        # Setup mocks
        mock_ensemble = AsyncMock()
        mock_ensemble_result = Mock()
        mock_ensemble_result.final_content = "Iterative solution iteration 1"
        mock_ensemble.process.return_value = mock_ensemble_result
        mock_ensemble_class.return_value = mock_ensemble
        
        mock_consensus = AsyncMock()
        mock_consensus_result = Mock()
        mock_consensus_result.consensus_content = "Improved solution iteration 2"
        mock_consensus.process.return_value = mock_consensus_result
        mock_consensus_class.return_value = mock_consensus
        
        # Mock validator to trigger improvement in first iteration
        mock_validator = AsyncMock()
        validation_results = [
            Mock(is_valid=False, validation_confidence=0.6),  # First iteration needs improvement
            Mock(is_valid=True, validation_confidence=0.9)    # Second iteration is good
        ]
        mock_validator.process.side_effect = validation_results
        mock_cross_validator_class.return_value = mock_validator
        
        solver = CollaborativeSolver(mock_model_provider)
        
        result = await solver.process(sample_task, strategy=SolvingStrategy.ITERATIVE)
        
        assert isinstance(result, SolvingResult)
        # Should have iterated and improved
        assert "iteration" in result.final_content.lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_solve_adaptive_strategy_simple_task(self, mock_model_provider):
        """Test adaptive strategy selection for simple tasks."""
        solver = CollaborativeSolver(mock_model_provider)
        
        # Create simple task
        simple_task = TaskContext(
            task_id="simple_adaptive",
            task_type=TaskType.FACTUAL,
            content="What is the capital of France?",
            requirements={}
        )
        
        # Mock the sequential solver to avoid complex setup
        with patch.object(solver, '_solve_sequential') as mock_sequential:
            mock_sequential.return_value = Mock(final_content="Sequential solution")
            
            result = await solver.process(simple_task, strategy=SolvingStrategy.ADAPTIVE)
            
            # Should use sequential strategy for simple task
            mock_sequential.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_solve_adaptive_strategy_complex_task(self, mock_model_provider):
        """Test adaptive strategy selection for complex tasks."""
        solver = CollaborativeSolver(mock_model_provider)
        
        # Create complex task
        complex_task = TaskContext(
            task_id="complex_adaptive",
            task_type=TaskType.CODE_GENERATION,
            content="Build a distributed microservices architecture with authentication, monitoring, and auto-scaling capabilities",
            requirements={
                "scalability": "high",
                "security": "enterprise",
                "monitoring": "comprehensive",
                "documentation": "complete",
                "testing": "full_coverage"
            }
        )
        
        # Mock the iterative solver to avoid complex setup
        with patch.object(solver, '_solve_iterative') as mock_iterative:
            mock_iterative.return_value = Mock(final_content="Iterative solution")
            
            result = await solver.process(complex_task, strategy=SolvingStrategy.ADAPTIVE)
            
            # Should use iterative strategy for complex task
            mock_iterative.assert_called_once()

    @pytest.mark.unit
    def test_create_solving_result(self, mock_model_provider, sample_task):
        """Test solving result creation."""
        solver = CollaborativeSolver(mock_model_provider)
        
        # Create a mock session
        session = SolvingSession(
            session_id="test_session",
            original_task=sample_task,
            strategy=SolvingStrategy.SEQUENTIAL,
            components_used=["router", "ensemble", "validator"],
            intermediate_results=[]
        )
        session.start_time = datetime.now()
        session.end_time = datetime.now()
        
        final_content = "Test solution content"
        
        result = solver._create_solving_result(session, final_content)
        
        assert isinstance(result, SolvingResult)
        assert result.session == session
        assert result.final_content == final_content
        assert 0.0 <= result.confidence_score <= 1.0
        assert isinstance(result.quality_assessment, QualityMetrics)
        assert isinstance(result.solution_path, list)
        assert len(result.solution_path) == 3  # router, ensemble, validator
        assert isinstance(result.component_contributions, dict)
        assert result.total_processing_time >= 0.0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_management(self, mock_model_provider, sample_task):
        """Test session creation and management."""
        solver = CollaborativeSolver(mock_model_provider)
        
        # Mock all components to avoid complex setup
        with patch.object(solver, '_solve_sequential') as mock_solve:
            mock_solve.return_value = Mock(final_content="Test solution")
            
            # Check initial state
            assert len(solver.active_sessions) == 0
            assert len(solver.completed_sessions) == 0
            
            # Process a task
            result = await solver.process(sample_task, strategy=SolvingStrategy.SEQUENTIAL)
            
            # Check final state
            assert len(solver.active_sessions) == 0  # Should be moved to completed
            assert len(solver.completed_sessions) == 1
            
            # Check the completed session
            completed_session = solver.completed_sessions[0]
            assert completed_session.original_task == sample_task
            assert completed_session.strategy == SolvingStrategy.SEQUENTIAL
            assert completed_session.final_result == result
            assert completed_session.end_time is not None

    @pytest.mark.unit
    def test_get_active_sessions(self, mock_model_provider):
        """Test getting active sessions."""
        solver = CollaborativeSolver(mock_model_provider)
        
        # Add some test sessions
        test_sessions = {
            "session_1": Mock(session_id="session_1"),
            "session_2": Mock(session_id="session_2")
        }
        solver.active_sessions = test_sessions
        
        active_sessions = solver.get_active_sessions()
        
        assert len(active_sessions) == 2
        assert active_sessions == test_sessions
        
        # Ensure it's a copy
        active_sessions["session_3"] = Mock()
        assert "session_3" not in solver.active_sessions

    @pytest.mark.unit
    def test_get_completed_sessions(self, mock_model_provider):
        """Test getting completed sessions."""
        solver = CollaborativeSolver(mock_model_provider)
        
        # Add some test sessions
        test_sessions = [
            Mock(session_id=f"session_{i}") for i in range(10)
        ]
        solver.completed_sessions = test_sessions
        
        # Test getting all sessions
        all_sessions = solver.get_completed_sessions()
        assert len(all_sessions) == 10
        assert all_sessions == test_sessions
        
        # Test getting limited sessions
        limited_sessions = solver.get_completed_sessions(limit=5)
        assert len(limited_sessions) == 5
        assert limited_sessions == test_sessions[-5:]

    @pytest.mark.unit
    def test_get_session_by_id(self, mock_model_provider):
        """Test getting a session by ID."""
        solver = CollaborativeSolver(mock_model_provider)
        
        # Add test sessions to both active and completed
        active_session = Mock(session_id="active_session")
        completed_session = Mock(session_id="completed_session")
        
        solver.active_sessions["active_session"] = active_session
        solver.completed_sessions = [completed_session]
        
        # Test finding active session
        found_active = solver.get_session_by_id("active_session")
        assert found_active == active_session
        
        # Test finding completed session
        found_completed = solver.get_session_by_id("completed_session")
        assert found_completed == completed_session
        
        # Test non-existent session
        not_found = solver.get_session_by_id("non_existent")
        assert not_found is None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_handling_in_solving(self, mock_model_provider, sample_task):
        """Test error handling during solving process."""
        solver = CollaborativeSolver(mock_model_provider)
        
        # Mock solve method to raise an exception
        with patch.object(solver, '_solve_sequential') as mock_solve:
            mock_solve.side_effect = Exception("Solving failed")
            
            with pytest.raises(Exception, match="Solving failed"):
                await solver.process(sample_task, strategy=SolvingStrategy.SEQUENTIAL)
            
            # Session should be cleaned up
            assert len(solver.active_sessions) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_solving_sessions(self, mock_model_provider):
        """Test handling multiple concurrent solving sessions."""
        solver = CollaborativeSolver(mock_model_provider)
        
        # Create multiple tasks
        tasks = [
            TaskContext(
                task_id=f"concurrent_task_{i}",
                task_type=TaskType.REASONING,
                content=f"Concurrent problem {i}"
            )
            for i in range(3)
        ]
        
        # Mock solving to return different results
        def mock_solve_side_effect(session):
            return Mock(final_content=f"Solution for {session.original_task.task_id}")
        
        with patch.object(solver, '_solve_sequential', side_effect=mock_solve_side_effect):
            # Process all tasks concurrently
            results = await asyncio.gather(
                *[solver.process(task, strategy=SolvingStrategy.SEQUENTIAL) for task in tasks],
                return_exceptions=True
            )
            
            # All should succeed
            assert len(results) == 3
            assert all(isinstance(result, SolvingResult) for result in results)
            assert len(set(result.final_content for result in results)) == 3  # All unique
            
            # All sessions should be completed
            assert len(solver.active_sessions) == 0
            assert len(solver.completed_sessions) == 3

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_solving_performance(self, performance_mock_provider, sample_task):
        """Test solving performance with realistic components."""
        solver = CollaborativeSolver(performance_mock_provider)
        
        # Use simple mocking to avoid component complexity
        with patch.object(solver, '_solve_adaptive') as mock_solve:
            mock_solve.return_value = Mock(
                final_content="Performance test solution",
                total_processing_time=1.0
            )
            
            start_time = datetime.now()
            result = await solver.process(sample_task, strategy=SolvingStrategy.ADAPTIVE)
            end_time = datetime.now()
            
            processing_time = (end_time - start_time).total_seconds()
            
            # Should complete within reasonable time
            assert processing_time < 3.0  # 3 seconds max for mocked version
            assert isinstance(result, SolvingResult)

    @pytest.mark.unit
    def test_component_contributions_calculation(self, mock_model_provider, sample_task):
        """Test calculation of component contributions."""
        solver = CollaborativeSolver(mock_model_provider)
        
        # Create session with repeated component usage
        session = SolvingSession(
            session_id="test_contributions",
            original_task=sample_task,
            strategy=SolvingStrategy.ITERATIVE,
            components_used=[
                "ensemble_reasoner", "cross_validator", 
                "ensemble_reasoner", "consensus_engine",
                "cross_validator"
            ],
            intermediate_results=[]
        )
        session.start_time = datetime.now()
        session.end_time = datetime.now()
        
        result = solver._create_solving_result(session, "Test content")
        
        # Check contributions sum to 1.0
        total_contribution = sum(result.component_contributions.values())
        assert abs(total_contribution - 1.0) < 0.01
        
        # Check individual contributions
        assert result.component_contributions["ensemble_reasoner"] == 0.4  # 2/5
        assert result.component_contributions["cross_validator"] == 0.4    # 2/5
        assert result.component_contributions["consensus_engine"] == 0.2   # 1/5

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_solving_with_all_component_failures(self, mock_model_provider, sample_task):
        """Test solving when all components fail."""
        solver = CollaborativeSolver(mock_model_provider)
        
        # Mock all components to fail
        with patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.AdaptiveRouter') as mock_router:
            with patch('src.openrouter_mcp.collective_intelligence.collaborative_solver.EnsembleReasoner') as mock_ensemble:
                mock_router.return_value.process.side_effect = Exception("Router failed")
                mock_ensemble.return_value.process.side_effect = Exception("Ensemble failed")
                
                with pytest.raises(Exception):
                    await solver.process(sample_task, strategy=SolvingStrategy.SEQUENTIAL)

    @pytest.mark.unit
    def test_solving_strategies_enum(self):
        """Test that all solving strategies are properly defined."""
        strategies = list(SolvingStrategy)
        
        expected_strategies = [
            SolvingStrategy.SEQUENTIAL,
            SolvingStrategy.PARALLEL,
            SolvingStrategy.HIERARCHICAL,
            SolvingStrategy.ITERATIVE,
            SolvingStrategy.ADAPTIVE
        ]
        
        assert len(strategies) == len(expected_strategies)
        assert all(strategy in strategies for strategy in expected_strategies)