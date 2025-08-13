"""
Multi-Model Consensus Engine

This module implements a consensus mechanism that aggregates responses from multiple
AI models to produce more reliable and accurate results through collective decision-making.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import statistics
import logging

from .base import (
    CollectiveIntelligenceComponent, 
    TaskContext, 
    ProcessingResult,
    ModelProvider,
    QualityMetrics
)

logger = logging.getLogger(__name__)


class ConsensusStrategy(Enum):
    """Strategies for building consensus among models."""
    MAJORITY_VOTE = "majority_vote"
    WEIGHTED_AVERAGE = "weighted_average"
    CONFIDENCE_THRESHOLD = "confidence_threshold"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    EXPERT_SELECTION = "expert_selection"


class AgreementLevel(Enum):
    """Levels of agreement among models."""
    UNANIMOUS = "unanimous"  # 100% agreement
    HIGH_CONSENSUS = "high_consensus"  # 80%+ agreement
    MODERATE_CONSENSUS = "moderate_consensus"  # 60%+ agreement
    LOW_CONSENSUS = "low_consensus"  # 40%+ agreement
    NO_CONSENSUS = "no_consensus"  # <40% agreement


@dataclass
class ConsensusConfig:
    """Configuration for consensus building."""
    strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY_VOTE
    min_models: int = 3
    max_models: int = 5
    confidence_threshold: float = 0.7
    agreement_threshold: float = 0.6
    timeout_seconds: float = 30.0
    retry_attempts: int = 2
    model_weights: Dict[str, float] = field(default_factory=dict)
    exclude_models: Set[str] = field(default_factory=set)


@dataclass
class ModelResponse:
    """Response from a single model in consensus building."""
    model_id: str
    result: ProcessingResult
    weight: float = 1.0
    reliability_score: float = 1.0


@dataclass
class ConsensusResult:
    """Result of consensus building process."""
    task_id: str
    consensus_content: str
    agreement_level: AgreementLevel
    confidence_score: float
    participating_models: List[str]
    model_responses: List[ModelResponse]
    strategy_used: ConsensusStrategy
    processing_time: float
    quality_metrics: QualityMetrics
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class ConsensusEngine(CollectiveIntelligenceComponent):
    """
    Multi-model consensus engine that aggregates responses from multiple AI models
    to produce more reliable and accurate results.
    """
    
    def __init__(self, model_provider: ModelProvider, config: Optional[ConsensusConfig] = None):
        super().__init__(model_provider)
        self.config = config or ConsensusConfig()
        self.consensus_history: List[ConsensusResult] = []
        self.model_reliability: Dict[str, float] = {}
    
    async def process(self, task: TaskContext, **kwargs) -> ConsensusResult:
        """
        Build consensus among multiple models for the given task.
        
        Args:
            task: The task to process
            **kwargs: Additional configuration options
            
        Returns:
            ConsensusResult containing the consensus and metadata
        """
        start_time = datetime.now()
        
        try:
            # Select models for consensus
            models = await self._select_models(task)
            logger.info(f"Selected {len(models)} models for consensus: {[m.model_id for m in models]}")
            
            # Get responses from all models
            model_responses = await self._get_model_responses(task, models)
            
            # Build consensus
            consensus_result = await self._build_consensus(task, model_responses)
            
            # Update metrics and history
            processing_time = (datetime.now() - start_time).total_seconds()
            consensus_result.processing_time = processing_time
            
            self._update_model_reliability(model_responses, consensus_result)
            self.consensus_history.append(consensus_result)
            
            logger.info(f"Consensus completed: {consensus_result.agreement_level.value}, "
                       f"confidence: {consensus_result.confidence_score:.3f}")
            
            return consensus_result
            
        except Exception as e:
            logger.error(f"Consensus building failed: {str(e)}")
            raise
    
    async def _select_models(self, task: TaskContext) -> List[str]:
        """Select appropriate models for consensus building."""
        available_models = await self.model_provider.get_available_models()
        
        # Filter excluded models
        eligible_models = [
            model for model in available_models 
            if model.model_id not in self.config.exclude_models
        ]
        
        # Sort by relevance to task type and reliability
        scored_models = []
        for model in eligible_models:
            relevance_score = self._calculate_model_relevance(model, task)
            reliability_score = self.model_reliability.get(model.model_id, 1.0)
            total_score = relevance_score * reliability_score
            scored_models.append((model.model_id, total_score))
        
        # Select top models within configured limits
        scored_models.sort(key=lambda x: x[1], reverse=True)
        selected_count = min(
            max(self.config.min_models, len(scored_models)),
            self.config.max_models
        )
        
        return [model_id for model_id, _ in scored_models[:selected_count]]
    
    def _calculate_model_relevance(self, model, task: TaskContext) -> float:
        """Calculate how relevant a model is for the given task."""
        # This is a simplified relevance calculation
        # In practice, this would use more sophisticated matching
        base_score = 0.5
        
        # Boost score based on task type and model capabilities
        if hasattr(model, 'capabilities'):
            task_type_mapping = {
                'reasoning': 'reasoning',
                'creative': 'creativity', 
                'factual': 'accuracy',
                'code_generation': 'code'
            }
            
            relevant_capability = task_type_mapping.get(task.task_type.value)
            if relevant_capability and relevant_capability in model.capabilities:
                base_score += model.capabilities[relevant_capability] * 0.5
        
        return min(1.0, base_score)
    
    async def _get_model_responses(
        self, 
        task: TaskContext, 
        model_ids: List[str]
    ) -> List[ModelResponse]:
        """Get responses from all selected models concurrently."""
        
        async def get_single_response(model_id: str) -> Optional[ModelResponse]:
            try:
                result = await asyncio.wait_for(
                    self.model_provider.process_task(task, model_id),
                    timeout=self.config.timeout_seconds
                )
                
                weight = self.config.model_weights.get(model_id, 1.0)
                reliability = self.model_reliability.get(model_id, 1.0)
                
                return ModelResponse(
                    model_id=model_id,
                    result=result,
                    weight=weight,
                    reliability_score=reliability
                )
                
            except Exception as e:
                logger.warning(f"Model {model_id} failed to respond: {str(e)}")
                return None
        
        # Execute all model calls concurrently
        tasks = [get_single_response(model_id) for model_id in model_ids]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out failed responses
        valid_responses = [
            response for response in responses 
            if isinstance(response, ModelResponse)
        ]
        
        if len(valid_responses) < self.config.min_models:
            raise ValueError(
                f"Insufficient responses for consensus: got {len(valid_responses)}, "
                f"need at least {self.config.min_models}"
            )
        
        return valid_responses
    
    async def _build_consensus(
        self, 
        task: TaskContext, 
        responses: List[ModelResponse]
    ) -> ConsensusResult:
        """Build consensus from model responses using the configured strategy."""
        
        if self.config.strategy == ConsensusStrategy.MAJORITY_VOTE:
            return self._majority_vote_consensus(task, responses)
        elif self.config.strategy == ConsensusStrategy.WEIGHTED_AVERAGE:
            return self._weighted_average_consensus(task, responses)
        elif self.config.strategy == ConsensusStrategy.CONFIDENCE_THRESHOLD:
            return self._confidence_threshold_consensus(task, responses)
        else:
            # Default to majority vote
            return self._majority_vote_consensus(task, responses)
    
    def _majority_vote_consensus(
        self, 
        task: TaskContext, 
        responses: List[ModelResponse]
    ) -> ConsensusResult:
        """Build consensus using majority vote strategy."""
        
        # Group similar responses (simplified approach)
        response_groups = self._group_similar_responses(responses)
        
        # Find the group with highest total weight
        best_group = max(response_groups, key=lambda g: sum(r.weight for r in g))
        
        # Calculate agreement level
        total_weight = sum(r.weight for r in responses)
        consensus_weight = sum(r.weight for r in best_group)
        agreement_ratio = consensus_weight / total_weight
        
        agreement_level = self._calculate_agreement_level(agreement_ratio)
        
        # Select best response from winning group
        best_response = max(best_group, key=lambda r: r.result.confidence * r.reliability_score)
        
        # Calculate consensus confidence
        consensus_confidence = self._calculate_consensus_confidence(best_group, responses)
        
        # Calculate quality metrics
        quality_metrics = self._calculate_quality_metrics(best_group, responses)
        
        return ConsensusResult(
            task_id=task.task_id,
            consensus_content=best_response.result.content,
            agreement_level=agreement_level,
            confidence_score=consensus_confidence,
            participating_models=[r.model_id for r in responses],
            model_responses=responses,
            strategy_used=self.config.strategy,
            processing_time=0.0,  # Will be set by caller
            quality_metrics=quality_metrics
        )
    
    def _weighted_average_consensus(
        self, 
        task: TaskContext, 
        responses: List[ModelResponse]
    ) -> ConsensusResult:
        """Build consensus using weighted average strategy."""
        # This is a simplified implementation
        # In practice, this would need semantic averaging
        
        total_weight = sum(r.weight * r.reliability_score for r in responses)
        
        if total_weight == 0:
            raise ValueError("Total weight is zero, cannot compute weighted average")
        
        # For now, select the response with highest weighted confidence
        best_response = max(
            responses, 
            key=lambda r: r.result.confidence * r.weight * r.reliability_score
        )
        
        # Calculate average confidence
        avg_confidence = sum(
            r.result.confidence * r.weight * r.reliability_score 
            for r in responses
        ) / total_weight
        
        quality_metrics = self._calculate_quality_metrics(responses, responses)
        
        return ConsensusResult(
            task_id=task.task_id,
            consensus_content=best_response.result.content,
            agreement_level=AgreementLevel.MODERATE_CONSENSUS,
            confidence_score=avg_confidence,
            participating_models=[r.model_id for r in responses],
            model_responses=responses,
            strategy_used=self.config.strategy,
            processing_time=0.0,
            quality_metrics=quality_metrics
        )
    
    def _confidence_threshold_consensus(
        self, 
        task: TaskContext, 
        responses: List[ModelResponse]
    ) -> ConsensusResult:
        """Build consensus using confidence threshold strategy."""
        
        # Filter responses by confidence threshold
        high_confidence_responses = [
            r for r in responses 
            if r.result.confidence >= self.config.confidence_threshold
        ]
        
        if not high_confidence_responses:
            # Fall back to best available response
            high_confidence_responses = [max(responses, key=lambda r: r.result.confidence)]
        
        # Use majority vote among high-confidence responses
        return self._majority_vote_consensus(task, high_confidence_responses)
    
    def _group_similar_responses(self, responses: List[ModelResponse]) -> List[List[ModelResponse]]:
        """Group similar responses together (simplified implementation)."""
        # This is a very simplified grouping based on response length similarity
        # In practice, this would use semantic similarity
        
        groups = []
        for response in responses:
            added_to_group = False
            for group in groups:
                # Simple similarity check based on content length
                if any(abs(len(response.result.content) - len(r.result.content)) < 50 
                       for r in group):
                    group.append(response)
                    added_to_group = True
                    break
            
            if not added_to_group:
                groups.append([response])
        
        return groups
    
    def _calculate_agreement_level(self, agreement_ratio: float) -> AgreementLevel:
        """Calculate agreement level based on consensus ratio."""
        if agreement_ratio >= 1.0:
            return AgreementLevel.UNANIMOUS
        elif agreement_ratio >= 0.8:
            return AgreementLevel.HIGH_CONSENSUS
        elif agreement_ratio >= 0.6:
            return AgreementLevel.MODERATE_CONSENSUS
        elif agreement_ratio >= 0.4:
            return AgreementLevel.LOW_CONSENSUS
        else:
            return AgreementLevel.NO_CONSENSUS
    
    def _calculate_consensus_confidence(
        self, 
        consensus_group: List[ModelResponse], 
        all_responses: List[ModelResponse]
    ) -> float:
        """Calculate confidence score for the consensus."""
        
        if not consensus_group:
            return 0.0
        
        # Average confidence of consensus group
        group_confidence = statistics.mean(r.result.confidence for r in consensus_group)
        
        # Weight by group size relative to total
        size_weight = len(consensus_group) / len(all_responses)
        
        # Weight by reliability scores
        reliability_weight = statistics.mean(r.reliability_score for r in consensus_group)
        
        return group_confidence * size_weight * reliability_weight
    
    def _calculate_quality_metrics(
        self, 
        consensus_group: List[ModelResponse], 
        all_responses: List[ModelResponse]
    ) -> QualityMetrics:
        """Calculate quality metrics for the consensus."""
        
        if not consensus_group:
            return QualityMetrics()
        
        # Calculate metrics based on response characteristics
        confidences = [r.result.confidence for r in consensus_group]
        
        accuracy = statistics.mean(confidences)
        consistency = 1.0 - (statistics.stdev(confidences) if len(confidences) > 1 else 0.0)
        completeness = min(1.0, len(consensus_group) / len(all_responses))
        relevance = accuracy  # Simplified
        confidence = statistics.mean(confidences)
        coherence = consistency  # Simplified
        
        return QualityMetrics(
            accuracy=accuracy,
            consistency=consistency,
            completeness=completeness,
            relevance=relevance,
            confidence=confidence,
            coherence=coherence
        )
    
    def _update_model_reliability(
        self, 
        responses: List[ModelResponse], 
        consensus: ConsensusResult
    ) -> None:
        """Update model reliability scores based on consensus participation."""
        
        for response in responses:
            current_reliability = self.model_reliability.get(response.model_id, 1.0)
            
            # Models that contributed to consensus get reliability boost
            if response.model_id in consensus.participating_models:
                # Small positive adjustment
                new_reliability = min(1.0, current_reliability + 0.01)
            else:
                # Small negative adjustment for non-contributing models
                new_reliability = max(0.1, current_reliability - 0.005)
            
            self.model_reliability[response.model_id] = new_reliability
    
    def get_consensus_history(self, limit: Optional[int] = None) -> List[ConsensusResult]:
        """Get historical consensus results."""
        if limit:
            return self.consensus_history[-limit:]
        return self.consensus_history.copy()
    
    def get_model_reliability_scores(self) -> Dict[str, float]:
        """Get current model reliability scores."""
        return self.model_reliability.copy()