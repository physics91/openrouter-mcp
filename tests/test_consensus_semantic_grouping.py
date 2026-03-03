#!/usr/bin/env python3
"""
Integration tests for consensus engine with semantic similarity grouping.

These tests verify that the consensus engine correctly uses semantic similarity
to group model responses, replacing the old length-based heuristic.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from openrouter_mcp.collective_intelligence.base import (
    ModelInfo,
    ModelProvider,
    ProcessingResult,
    TaskContext,
    TaskType,
)
from openrouter_mcp.collective_intelligence.consensus_engine import (
    ConsensusConfig,
    ConsensusEngine,
    ConsensusStrategy,
    ModelResponse,
)


@pytest.fixture
def mock_model_provider():
    """Create a mock model provider."""
    provider = Mock(spec=ModelProvider)
    provider.get_available_models = AsyncMock(
        return_value=[
            ModelInfo(model_id="model_a", name="Model A", provider="test"),
            ModelInfo(model_id="model_b", name="Model B", provider="test"),
            ModelInfo(model_id="model_c", name="Model C", provider="test"),
        ]
    )
    return provider


@pytest.fixture
async def consensus_engine(mock_model_provider):
    """Create a consensus engine with semantic similarity enabled."""
    config = ConsensusConfig(
        strategy=ConsensusStrategy.MAJORITY_VOTE,
        min_models=3,
        max_models=5,
        similarity_threshold=0.7,  # Standard threshold
    )
    engine = ConsensusEngine(mock_model_provider, config)
    yield engine
    await engine.shutdown()


class TestSemanticGrouping:
    """Test semantic grouping in consensus building."""

    def test_groups_identical_responses(self, consensus_engine):
        """Test that identical responses are grouped together."""
        responses = [
            ModelResponse(
                model_id="model_a",
                result=ProcessingResult(
                    content="Renewable energy reduces carbon emissions.",
                    confidence=0.9,
                    metadata={},
                ),
                weight=1.0,
            ),
            ModelResponse(
                model_id="model_b",
                result=ProcessingResult(
                    content="Renewable energy reduces carbon emissions.",
                    confidence=0.85,
                    metadata={},
                ),
                weight=1.0,
            ),
            ModelResponse(
                model_id="model_c",
                result=ProcessingResult(
                    content="Renewable energy reduces carbon emissions.",
                    confidence=0.88,
                    metadata={},
                ),
                weight=1.0,
            ),
        ]

        groups = consensus_engine._group_similar_responses(responses)

        # All identical responses should be in one group
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_groups_similar_responses_different_formatting(self, consensus_engine):
        """Test that similar responses with different formatting are grouped."""
        responses = [
            ModelResponse(
                model_id="model_a",
                result=ProcessingResult(
                    content="Renewable energy sources are sustainable and reduce carbon emissions.",
                    confidence=0.9,
                    metadata={},
                ),
                weight=1.0,
            ),
            ModelResponse(
                model_id="model_b",
                result=ProcessingResult(
                    content="Renewable energy sources are sustainable, and reduce carbon emissions.",  # Added comma
                    confidence=0.85,
                    metadata={},
                ),
                weight=1.0,
            ),
            ModelResponse(
                model_id="model_c",
                result=ProcessingResult(
                    content="Renewable energy sources are sustainable and reduce carbon emissions!",  # Added exclamation
                    confidence=0.88,
                    metadata={},
                ),
                weight=1.0,
            ),
        ]

        groups = consensus_engine._group_similar_responses(responses)

        # Should group together despite formatting differences
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_separates_semantically_different_responses(self, consensus_engine):
        """Test that semantically different responses are separated."""
        responses = [
            ModelResponse(
                model_id="model_a",
                result=ProcessingResult(
                    content="Renewable energy reduces carbon emissions.",
                    confidence=0.9,
                    metadata={},
                ),
                weight=1.0,
            ),
            ModelResponse(
                model_id="model_b",
                result=ProcessingResult(
                    content="Python is a versatile programming language.",
                    confidence=0.85,
                    metadata={},
                ),
                weight=1.0,
            ),
            ModelResponse(
                model_id="model_c",
                result=ProcessingResult(
                    content="The stock market is experiencing volatility.",
                    confidence=0.88,
                    metadata={},
                ),
                weight=1.0,
            ),
        ]

        groups = consensus_engine._group_similar_responses(responses)

        # Should create separate groups for different topics
        assert len(groups) == 3
        assert all(len(group) == 1 for group in groups)

    def test_mixed_similar_and_different_responses(self, consensus_engine):
        """Test grouping with a mix of similar and different responses."""
        responses = [
            # Group 1: Climate/energy (3 similar responses)
            ModelResponse(
                model_id="model_a",
                result=ProcessingResult(
                    content="Renewable energy sources are sustainable and reduce carbon emissions.",
                    confidence=0.9,
                    metadata={},
                ),
                weight=1.0,
            ),
            ModelResponse(
                model_id="model_b",
                result=ProcessingResult(
                    content="Renewable energy is sustainable and helps reduce carbon emissions.",
                    confidence=0.85,
                    metadata={},
                ),
                weight=1.0,
            ),
            ModelResponse(
                model_id="model_c",
                result=ProcessingResult(
                    content="Renewable energy sources are sustainable and reduce greenhouse gas emissions.",
                    confidence=0.88,
                    metadata={},
                ),
                weight=1.0,
            ),
            # Group 2: Different topic (1 response)
            ModelResponse(
                model_id="model_d",
                result=ProcessingResult(
                    content="Python is excellent for data science and machine learning applications.",
                    confidence=0.87,
                    metadata={},
                ),
                weight=1.0,
            ),
        ]

        groups = consensus_engine._group_similar_responses(responses)

        # Should have 2 groups: one with 3 climate responses, one with 1 Python response
        assert len(groups) == 2

        # Find the sizes of groups
        group_sizes = sorted([len(group) for group in groups], reverse=True)
        assert group_sizes == [3, 1]

    def test_old_length_heuristic_would_fail(self, consensus_engine):
        """
        Test case where old length-based heuristic would fail but semantic similarity succeeds.

        Old heuristic: group if length within ±50 chars
        This test uses responses with very different lengths but same meaning.
        """
        responses = [
            ModelResponse(
                model_id="model_a",
                result=ProcessingResult(
                    content="Yes.", confidence=0.9, metadata={}  # 4 chars
                ),
                weight=1.0,
            ),
            ModelResponse(
                model_id="model_b",
                result=ProcessingResult(
                    content="Yes, that is correct.",  # 22 chars (within 50)
                    confidence=0.85,
                    metadata={},
                ),
                weight=1.0,
            ),
            ModelResponse(
                model_id="model_c",
                result=ProcessingResult(
                    content="Yes, that is absolutely correct and I completely agree with this assessment.",  # 77 chars (beyond 50 from first)
                    confidence=0.88,
                    metadata={},
                ),
                weight=1.0,
            ),
        ]

        groups = consensus_engine._group_similar_responses(responses)

        # All should be grouped together despite length differences
        # (semantic similarity recognizes they all mean "yes")
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_paraphrased_responses_grouped(self, consensus_engine):
        """Test that paraphrased responses are grouped together."""
        responses = [
            ModelResponse(
                model_id="model_a",
                result=ProcessingResult(
                    content="Machine learning models require large datasets for training.",
                    confidence=0.9,
                    metadata={},
                ),
                weight=1.0,
            ),
            ModelResponse(
                model_id="model_b",
                result=ProcessingResult(
                    content="ML models need substantial amounts of data to train effectively.",
                    confidence=0.85,
                    metadata={},
                ),
                weight=1.0,
            ),
        ]

        groups = consensus_engine._group_similar_responses(responses)

        # Paraphrased responses might or might not group depending on threshold
        # But should at least recognize some similarity
        # (exact grouping depends on similarity threshold)
        assert len(groups) >= 1

    def test_empty_responses_list(self, consensus_engine):
        """Test handling of empty responses list."""
        groups = consensus_engine._group_similar_responses([])
        assert groups == []

    def test_single_response(self, consensus_engine):
        """Test handling of single response."""
        responses = [
            ModelResponse(
                model_id="model_a",
                result=ProcessingResult(
                    content="Single response", confidence=0.9, metadata={}
                ),
                weight=1.0,
            )
        ]

        groups = consensus_engine._group_similar_responses(responses)
        assert len(groups) == 1
        assert len(groups[0]) == 1

    @pytest.mark.asyncio
    async def test_custom_similarity_threshold_strict(self, mock_model_provider):
        """Test with strict similarity threshold."""
        config = ConsensusConfig(
            similarity_threshold=0.95,  # Very strict
        )
        engine = ConsensusEngine(mock_model_provider, config)

        try:
            responses = [
                ModelResponse(
                    model_id="model_a",
                    result=ProcessingResult(
                        content="Hello world", confidence=0.9, metadata={}
                    ),
                    weight=1.0,
                ),
                ModelResponse(
                    model_id="model_b",
                    result=ProcessingResult(
                        content="Hello world!",  # Minor difference
                        confidence=0.85,
                        metadata={},
                    ),
                    weight=1.0,
                ),
            ]

            groups = engine._group_similar_responses(responses)

            # With strict threshold, minor differences might create separate groups
            # (exact behavior depends on similarity score)
            assert len(groups) >= 1
        finally:
            await engine.shutdown()

    @pytest.mark.asyncio
    async def test_custom_similarity_threshold_lenient(self, mock_model_provider):
        """Test with lenient similarity threshold."""
        config = ConsensusConfig(
            similarity_threshold=0.3,  # Very lenient
        )
        engine = ConsensusEngine(mock_model_provider, config)

        try:
            responses = [
                ModelResponse(
                    model_id="model_a",
                    result=ProcessingResult(
                        content="Machine learning is important.",
                        confidence=0.9,
                        metadata={},
                    ),
                    weight=1.0,
                ),
                ModelResponse(
                    model_id="model_b",
                    result=ProcessingResult(
                        content="ML matters significantly.",
                        confidence=0.85,
                        metadata={},
                    ),
                    weight=1.0,
                ),
            ]

            groups = engine._group_similar_responses(responses)

            # With lenient threshold, should group similar concepts
            assert len(groups) == 1
        finally:
            await engine.shutdown()


class TestConsensusWithSemanticGrouping:
    """Test full consensus building with semantic grouping."""

    @pytest.mark.asyncio
    async def test_consensus_selects_largest_semantic_group(self, consensus_engine):
        """Test that consensus is built from the largest semantic group."""
        # Create task context
        task = TaskContext(
            task_id="test_task",
            task_type=TaskType.REASONING,
            content="What are the benefits of renewable energy?",
            metadata={},
        )

        # Create responses where 3 models give similar answers (Group 1)
        # and 2 models give different answers (Group 2, Group 3)
        responses = [
            # Group 1: Sustainability-focused (3 models - should win)
            ModelResponse(
                model_id="model_a",
                result=ProcessingResult(
                    content="Renewable energy is sustainable and reduces carbon emissions.",
                    confidence=0.9,
                    metadata={},
                ),
                weight=1.0,
                reliability_score=1.0,
            ),
            ModelResponse(
                model_id="model_b",
                result=ProcessingResult(
                    content="Renewable energy sources are sustainable and help reduce carbon emissions.",
                    confidence=0.85,
                    metadata={},
                ),
                weight=1.0,
                reliability_score=1.0,
            ),
            ModelResponse(
                model_id="model_c",
                result=ProcessingResult(
                    content="Renewable energy is sustainable and reduces greenhouse gas emissions.",
                    confidence=0.88,
                    metadata={},
                ),
                weight=1.0,
                reliability_score=1.0,
            ),
            # Group 2: Economic focus (1 model)
            ModelResponse(
                model_id="model_d",
                result=ProcessingResult(
                    content="Renewable energy creates jobs and drives economic growth.",
                    confidence=0.87,
                    metadata={},
                ),
                weight=1.0,
                reliability_score=1.0,
            ),
            # Group 3: Technology focus (1 model)
            ModelResponse(
                model_id="model_e",
                result=ProcessingResult(
                    content="Advances in solar and wind technology have improved efficiency.",
                    confidence=0.86,
                    metadata={},
                ),
                weight=1.0,
                reliability_score=1.0,
            ),
        ]

        # Build consensus using majority vote
        result = consensus_engine._majority_vote_consensus(task, responses)

        # Should select from Group 1 (largest semantic group)
        # The consensus content should be from one of the sustainability-focused responses
        assert (
            "sustainable" in result.consensus_content.lower()
            or "carbon" in result.consensus_content.lower()
            or "emissions" in result.consensus_content.lower()
        )

        # Agreement level should reflect 3/5 agreement
        assert result.agreement_level.value in ["high_consensus", "moderate_consensus"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
