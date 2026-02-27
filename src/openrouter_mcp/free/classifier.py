"""Task type classification for optimized model selection."""

from enum import Enum
from typing import Dict, List


class FreeTaskType(Enum):
    """Categories of user tasks for model affinity matching."""

    CODING = "coding"
    TRANSLATION = "translation"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    GENERAL = "general"


TASK_PATTERNS: Dict[FreeTaskType, List[str]] = {
    FreeTaskType.CODING: [
        "코드",
        "code",
        "함수",
        "function",
        "class",
        "버그",
        "bug",
        "debug",
        "python",
        "javascript",
        "typescript",
        "java",
        "구현",
        "implement",
        "리팩토링",
        "refactor",
        "컴파일",
        "compile",
        "api",
        "알고리즘",
    ],
    FreeTaskType.TRANSLATION: [
        "번역",
        "translate",
        "영어로",
        "한국어로",
        "일본어",
        "중국어",
        "translation",
        "통역",
        "언어로",
    ],
    FreeTaskType.CREATIVE: [
        "이야기",
        "story",
        "시",
        "poem",
        "소설",
        "novel",
        "작성해",
        "써줘",
        "creative",
        "상상",
        "캐릭터",
        "character",
        "대본",
        "script",
    ],
    FreeTaskType.ANALYSIS: [
        "분석",
        "analyze",
        "비교",
        "compare",
        "설명",
        "explain",
        "요약",
        "summarize",
        "평가",
        "evaluate",
        "리뷰",
        "review",
    ],
}

TASK_MODEL_AFFINITY: Dict[FreeTaskType, Dict[str, float]] = {
    FreeTaskType.CODING: {"deepseek": 0.15, "qwen": 0.10},
    FreeTaskType.CREATIVE: {"google": 0.10, "meta": 0.10},
    FreeTaskType.TRANSLATION: {"google": 0.10, "qwen": 0.10},
    FreeTaskType.ANALYSIS: {"google": 0.10, "deepseek": 0.10},
    FreeTaskType.GENERAL: {},
}


class TaskClassifier:
    """Classifies user messages into task types using keyword matching."""

    def classify(self, message: str, system_prompt: str = "") -> FreeTaskType:
        """Classify a message into a FreeTaskType based on keyword matching.

        Args:
            message: The user message to classify.
            system_prompt: Optional system prompt providing additional context.

        Returns:
            The detected FreeTaskType, defaulting to GENERAL if no patterns match.
        """
        text = f"{system_prompt} {message}".lower()
        best_type = FreeTaskType.GENERAL
        best_count = 0
        for task_type, patterns in TASK_PATTERNS.items():
            count = sum(1 for p in patterns if p.lower() in text)
            if count > best_count:
                best_count = count
                best_type = task_type
        return best_type
