"""
Collective Intelligence Module for OpenRouter MCP

This module provides advanced AI orchestration capabilities through collective intelligence,
enabling multiple models to work together for enhanced problem-solving and decision-making.

Components:
- ConsensusEngine: Multi-model consensus building and agreement validation
- EnsembleReasoning: Intelligent task decomposition and specialized model routing
- AdaptiveRouter: Dynamic model selection based on context and performance
- CrossValidator: Inter-model validation and quality assurance
- CollaborativeSolver: Coordinated problem-solving workflows

Features:
- TDD-driven development with comprehensive test coverage
- Performance monitoring and benchmarking
- Error handling and fallback mechanisms
- Scalable architecture for production use
"""

from .consensus_engine import ConsensusEngine, ConsensusResult, ConsensusConfig, ConsensusStrategy, AgreementLevel
from .ensemble_reasoning import EnsembleReasoner, EnsembleTask, EnsembleResult
from .adaptive_router import AdaptiveRouter, RoutingDecision, RoutingMetrics
from .cross_validator import CrossValidator, ValidationResult, ValidationConfig
from .collaborative_solver import CollaborativeSolver, SolvingSession, SolvingResult
from .base import TaskContext, TaskType, ModelInfo, ProcessingResult, ModelProvider

__all__ = [
    'ConsensusEngine',
    'ConsensusResult', 
    'ConsensusConfig',
    'ConsensusStrategy',
    'AgreementLevel',
    'EnsembleReasoner',
    'EnsembleTask',
    'EnsembleResult',
    'AdaptiveRouter',
    'RoutingDecision',
    'RoutingMetrics',
    'CrossValidator',
    'ValidationResult',
    'ValidationConfig',
    'CollaborativeSolver',
    'SolvingSession',
    'SolvingResult',
    'TaskContext',
    'TaskType',
    'ModelInfo',
    'ProcessingResult',
    'ModelProvider',
]

__version__ = "1.0.0"