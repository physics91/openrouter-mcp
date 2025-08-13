"""
Base classes and interfaces for Collective Intelligence components.

This module defines the core abstractions and protocols that all CI components
must implement to ensure consistency and interoperability.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Union
from datetime import datetime
import uuid


class TaskType(Enum):
    """Types of tasks that can be processed by the collective intelligence system."""
    REASONING = "reasoning"
    ANALYSIS = "analysis"
    CREATIVE = "creative"
    FACTUAL = "factual"
    CODE_GENERATION = "code_generation"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    MATH = "math"
    CLASSIFICATION = "classification"


class ModelCapability(Enum):
    """Model capabilities for task assignment."""
    REASONING = "reasoning"
    CREATIVITY = "creativity"
    ACCURACY = "accuracy"
    SPEED = "speed"
    CONTEXT_LENGTH = "context_length"
    MULTIMODAL = "multimodal"
    CODE = "code"
    MATH = "math"


@dataclass
class ModelInfo:
    """Information about a model including its capabilities and metrics."""
    model_id: str
    name: str
    provider: str
    capabilities: Dict[ModelCapability, float] = field(default_factory=dict)
    context_length: int = 4096
    cost_per_token: float = 0.0
    response_time_avg: float = 0.0
    accuracy_score: float = 0.0
    availability: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskContext:
    """Context information for a task to be processed."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: TaskType = TaskType.REASONING
    content: str = ""
    requirements: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10 scale
    deadline: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """Result from processing a task."""
    task_id: str
    model_id: str
    content: str
    confidence: float = 0.0
    processing_time: float = 0.0
    tokens_used: int = 0
    cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class ModelProvider(Protocol):
    """Protocol for model providers that can process tasks."""
    
    async def process_task(
        self, 
        task: TaskContext, 
        model_id: str,
        **kwargs
    ) -> ProcessingResult:
        """Process a task using the specified model."""
        ...
    
    async def get_available_models(self) -> List[ModelInfo]:
        """Get list of available models."""
        ...


class CollectiveIntelligenceComponent(ABC):
    """Base class for all collective intelligence components."""
    
    def __init__(self, model_provider: ModelProvider):
        self.model_provider = model_provider
        self.metrics: Dict[str, Any] = {}
        self.config: Dict[str, Any] = {}
    
    @abstractmethod
    async def process(self, task: TaskContext, **kwargs) -> Any:
        """Process a task using this component."""
        pass
    
    def update_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update component metrics."""
        self.metrics.update(metrics)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current component metrics."""
        return self.metrics.copy()
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the component."""
        self.config.update(config)


@dataclass
class QualityMetrics:
    """Quality metrics for evaluating results."""
    accuracy: float = 0.0
    consistency: float = 0.0
    completeness: float = 0.0
    relevance: float = 0.0
    confidence: float = 0.0
    coherence: float = 0.0
    
    def overall_score(self) -> float:
        """Calculate overall quality score."""
        metrics = [
            self.accuracy, self.consistency, self.completeness,
            self.relevance, self.confidence, self.coherence
        ]
        return sum(metrics) / len(metrics)


@dataclass
class PerformanceMetrics:
    """Performance metrics for system monitoring."""
    response_time: float = 0.0
    throughput: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    cost_efficiency: float = 0.0
    resource_utilization: float = 0.0
    
    def overall_performance(self) -> float:
        """Calculate overall performance score."""
        # Weight different metrics based on importance
        weights = {
            'response_time': 0.2,
            'throughput': 0.15,
            'success_rate': 0.3,
            'error_rate': -0.2,  # Negative weight
            'cost_efficiency': 0.15,
            'resource_utilization': 0.1
        }
        
        score = (
            weights['response_time'] * min(1.0, 10.0 / max(self.response_time, 0.1)) +
            weights['throughput'] * min(1.0, self.throughput / 100.0) +
            weights['success_rate'] * self.success_rate +
            weights['error_rate'] * (1.0 - self.error_rate) +
            weights['cost_efficiency'] * self.cost_efficiency +
            weights['resource_utilization'] * self.resource_utilization
        )
        
        return max(0.0, min(1.0, score))