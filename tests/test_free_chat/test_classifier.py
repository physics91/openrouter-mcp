"""Tests for TaskClassifier keyword-based task type detection."""

import pytest

from src.openrouter_mcp.free.classifier import TaskClassifier, FreeTaskType


class TestTaskClassifier:
    @pytest.fixture
    def classifier(self):
        return TaskClassifier()

    @pytest.mark.unit
    def test_classify_coding(self, classifier):
        assert classifier.classify("파이썬 함수를 작성해줘") == FreeTaskType.CODING

    @pytest.mark.unit
    def test_classify_coding_english(self, classifier):
        assert classifier.classify("Write a Python function") == FreeTaskType.CODING

    @pytest.mark.unit
    def test_classify_translation(self, classifier):
        assert classifier.classify("이 문장을 영어로 번역해줘") == FreeTaskType.TRANSLATION

    @pytest.mark.unit
    def test_classify_creative(self, classifier):
        assert classifier.classify("짧은 이야기를 써줘") == FreeTaskType.CREATIVE

    @pytest.mark.unit
    def test_classify_analysis(self, classifier):
        assert classifier.classify("이 데이터를 분석해줘") == FreeTaskType.ANALYSIS

    @pytest.mark.unit
    def test_classify_general_default(self, classifier):
        assert classifier.classify("안녕하세요") == FreeTaskType.GENERAL

    @pytest.mark.unit
    def test_classify_uses_system_prompt(self, classifier):
        result = classifier.classify("도와줘", system_prompt="You are a python developer")
        assert result == FreeTaskType.CODING

    @pytest.mark.unit
    def test_classify_case_insensitive(self, classifier):
        assert classifier.classify("Write PYTHON code") == FreeTaskType.CODING

    @pytest.mark.unit
    def test_task_type_values(self):
        assert FreeTaskType.CODING.value == "coding"
        assert FreeTaskType.TRANSLATION.value == "translation"
        assert FreeTaskType.CREATIVE.value == "creative"
        assert FreeTaskType.ANALYSIS.value == "analysis"
        assert FreeTaskType.GENERAL.value == "general"
