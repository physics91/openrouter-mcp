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

from .adaptive_router import AdaptiveRouter, RoutingDecision, RoutingMetrics
from .base import ModelInfo, ModelProvider, ProcessingResult, TaskContext, TaskType
from .collaborative_solver import CollaborativeSolver, SolvingResult, SolvingSession
from .consensus_engine import (
    AgreementLevel,
    ConsensusConfig,
    ConsensusEngine,
    ConsensusResult,
    ConsensusStrategy,
)
from .cross_validator import CrossValidator, ValidationConfig, ValidationResult
from .ensemble_reasoning import EnsembleReasoner, EnsembleResult, EnsembleTask
from .lifecycle_manager import (
    CollectiveIntelligenceLifecycleManager,
    get_lifecycle_manager,
    shutdown_lifecycle_manager,
)
from .operational_controls import (
    ConcurrencyConfig,
    ConcurrencyLimiter,
    FailureConfig,
    FailureController,
    OperationalConfig,
    OperationalControls,
    QuotaConfig,
    QuotaTracker,
    StorageConfig,
    StorageManager,
    TaskCancellationManager,
    init_operational_controls,
)
from .protocols import (
    CancellationAware,
    ConcurrencyAware,
    FailureAware,
    QuotaAware,
    StorageAware,
)
from .semantic_similarity import (
    ResponseGrouper,
    SemanticSimilarityCalculator,
    SimilarityScore,
    calculate_response_similarity,
)

__all__ = [
    "AdaptiveRouter",
    "AgreementLevel",
    "CancellationAware",
    "CollaborativeSolver",
    "CollectiveIntelligenceLifecycleManager",
    "ConcurrencyAware",
    "ConcurrencyConfig",
    "ConcurrencyLimiter",
    "ConsensusConfig",
    "ConsensusEngine",
    "ConsensusResult",
    "ConsensusStrategy",
    "CrossValidator",
    "EnsembleReasoner",
    "EnsembleResult",
    "EnsembleTask",
    "FailureAware",
    "FailureConfig",
    "FailureController",
    "ModelInfo",
    "ModelProvider",
    "OperationalConfig",
    "OperationalControls",
    "ProcessingResult",
    "QuotaAware",
    "QuotaConfig",
    "QuotaTracker",
    "ResponseGrouper",
    "RoutingDecision",
    "RoutingMetrics",
    "SemanticSimilarityCalculator",
    "SimilarityScore",
    "SolvingResult",
    "SolvingSession",
    "StorageAware",
    "StorageConfig",
    "StorageManager",
    "TaskCancellationManager",
    "TaskContext",
    "TaskType",
    "ValidationConfig",
    "ValidationResult",
    "calculate_response_similarity",
    "get_lifecycle_manager",
    "init_operational_controls",
    "shutdown_lifecycle_manager",
]

__version__ = "1.4.0"
