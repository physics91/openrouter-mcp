from unittest.mock import Mock, call

import pytest

from src.openrouter_mcp.collective_intelligence.base import (
    ProcessingResult,
    QualityMetrics,
    TaskContext,
)
from src.openrouter_mcp.collective_intelligence.consensus_engine import (
    AgreementLevel,
    ConsensusConfig,
    ConsensusEngine,
    ConsensusStrategy,
    ModelResponse,
)


def _responses() -> list[ModelResponse]:
    return [
        ModelResponse(
            model_id="model-a",
            result=ProcessingResult(content="answer-a", confidence=0.4),
            weight=1.0,
            reliability_score=1.0,
        ),
        ModelResponse(
            model_id="model-b",
            result=ProcessingResult(content="answer-b", confidence=0.9),
            weight=2.0,
            reliability_score=0.5,
        ),
    ]


class _TrackedTask:
    def __init__(self, events):
        self.events = events

    @property
    def task_id(self):
        self.events.append("task.task_id")
        return "task-1"


class _TrackedResult:
    def __init__(self, content, events, label):
        self._content = content
        self.events = events
        self.label = label

    @property
    def content(self):
        self.events.append(f"{self.label}.content")
        return self._content


class _TrackedResponse:
    def __init__(self, model_id, content, events, label):
        self._model_id = model_id
        self._result = _TrackedResult(content, events, label)
        self.events = events
        self.label = label

    @property
    def model_id(self):
        self.events.append(f"{self.label}.model_id")
        return self._model_id

    @property
    def result(self):
        self.events.append(f"{self.label}.result")
        return self._result


class _TrackedConfig:
    def __init__(self, events):
        self.events = events

    @property
    def strategy(self):
        self.events.append("config.strategy")
        return ConsensusStrategy.MAJORITY_VOTE


@pytest.mark.unit
def test_build_consensus_result_preserves_envelope_identity_and_access_order(
    mock_model_provider,
):
    events = []
    engine = ConsensusEngine(mock_model_provider)
    engine.config = _TrackedConfig(events)
    task = _TrackedTask(events)
    responses = [
        _TrackedResponse("model-a", "answer-a", events, "first"),
        _TrackedResponse("model-b", "answer-b", events, "second"),
    ]
    quality = QualityMetrics(accuracy=0.8)

    result = engine._build_consensus_result(
        task,
        responses,
        responses[1],
        AgreementLevel.HIGH_CONSENSUS,
        0.75,
        quality,
    )

    assert events == [
        "task.task_id",
        "second.result",
        "second.content",
        "first.model_id",
        "second.model_id",
        "config.strategy",
    ]
    assert result.task_id == "task-1"
    assert result.consensus_content == "answer-b"
    assert result.participating_models == ["model-a", "model-b"]
    assert result.model_responses is responses
    assert result.quality_metrics is quality
    assert result.processing_time == 0.0


@pytest.mark.unit
def test_majority_vote_delegates_computed_result_envelope(
    mock_model_provider,
    monkeypatch,
):
    engine = ConsensusEngine(mock_model_provider)
    task = TaskContext(task_id="task-1")
    responses = _responses()
    quality = QualityMetrics(accuracy=0.7)
    expected = object()
    builder = Mock(return_value=expected)
    monkeypatch.setattr(engine, "_group_similar_responses", lambda values: [values])
    monkeypatch.setattr(engine, "_calculate_consensus_confidence", lambda *_: 0.73)
    monkeypatch.setattr(engine, "_calculate_quality_metrics", lambda *_: quality)
    monkeypatch.setattr(engine, "_build_consensus_result", builder)

    result = engine._majority_vote_consensus(task, responses)

    assert result is expected
    assert builder.call_args_list == [
        call(
            task,
            responses,
            responses[1],
            AgreementLevel.UNANIMOUS,
            0.73,
            quality,
        )
    ]


@pytest.mark.unit
def test_weighted_average_delegates_computed_result_envelope(
    mock_model_provider,
    monkeypatch,
):
    engine = ConsensusEngine(
        mock_model_provider,
        ConsensusConfig(strategy=ConsensusStrategy.WEIGHTED_AVERAGE),
    )
    task = TaskContext(task_id="task-1")
    responses = _responses()
    quality = QualityMetrics(accuracy=0.6)
    expected = object()
    builder = Mock(return_value=expected)
    monkeypatch.setattr(engine, "_calculate_quality_metrics", lambda *_: quality)
    monkeypatch.setattr(engine, "_build_consensus_result", builder)

    result = engine._weighted_average_consensus(task, responses)

    assert result is expected
    assert builder.call_args_list == [
        call(
            task,
            responses,
            responses[1],
            AgreementLevel.MODERATE_CONSENSUS,
            pytest.approx(0.65),
            quality,
        )
    ]


@pytest.mark.unit
def test_weighted_average_zero_weight_skips_result_building(
    mock_model_provider,
    monkeypatch,
):
    engine = ConsensusEngine(
        mock_model_provider,
        ConsensusConfig(strategy=ConsensusStrategy.WEIGHTED_AVERAGE),
    )
    responses = _responses()
    for response in responses:
        response.weight = 0.0
    builder = Mock()
    monkeypatch.setattr(engine, "_build_consensus_result", builder)

    with pytest.raises(ValueError, match="Total weight is zero"):
        engine._weighted_average_consensus(TaskContext(), responses)

    builder.assert_not_called()
