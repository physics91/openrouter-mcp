import pytest

from src.openrouter_mcp.handlers.benchmark import (
    BenchmarkError,
    _extract_benchmark_response_data,
)


class RecordingDict(dict):
    def __init__(self, label, values, calls):
        super().__init__(values)
        self.label = label
        self.calls = calls

    def get(self, key, default=None):
        self.calls.append((self.label, "get", key))
        return super().get(key, default)

    def __getitem__(self, key):
        self.calls.append((self.label, "getitem", key))
        return super().__getitem__(key)


def test_extract_benchmark_response_data_preserves_access_order_and_values():
    calls = []
    usage = RecordingDict(
        "usage",
        {"total_tokens": 9, "prompt_tokens": 4, "completion_tokens": 5},
        calls,
    )
    message = RecordingDict("message", {"content": "answer"}, calls)
    choice = RecordingDict("choice", {"message": message}, calls)
    response = RecordingDict("response", {"choices": [choice], "usage": usage}, calls)

    extracted = _extract_benchmark_response_data(response, "vendor/model")

    assert extracted == ("answer", 9, 4, 5)
    assert calls == [
        ("response", "get", "choices"),
        ("response", "getitem", "choices"),
        ("response", "getitem", "choices"),
        ("choice", "get", "message"),
        ("choice", "getitem", "message"),
        ("message", "get", "content"),
        ("choice", "getitem", "message"),
        ("message", "getitem", "content"),
        ("response", "get", "usage"),
        ("usage", "get", "total_tokens"),
        ("usage", "get", "prompt_tokens"),
        ("usage", "get", "completion_tokens"),
    ]


@pytest.mark.parametrize("response", [{}, {"choices": None}, {"choices": []}])
def test_extract_benchmark_response_data_rejects_missing_choices(response):
    with pytest.raises(BenchmarkError) as exc_info:
        _extract_benchmark_response_data(response, "vendor/model")

    assert str(exc_info.value) == "No choices in response from vendor/model"
    assert exc_info.value.model_id == "vendor/model"
    assert exc_info.value.error_code == "NO_CHOICES"


@pytest.mark.parametrize(
    "choice",
    [
        {},
        {"message": None},
        {"message": {}},
        {"message": {"content": ""}},
    ],
)
def test_extract_benchmark_response_data_rejects_missing_content(choice):
    with pytest.raises(BenchmarkError) as exc_info:
        _extract_benchmark_response_data({"choices": [choice]}, "vendor/model")

    assert str(exc_info.value) == "No content in response from vendor/model"
    assert exc_info.value.model_id == "vendor/model"
    assert exc_info.value.error_code == "NO_CONTENT"


def test_extract_benchmark_response_data_preserves_malformed_choice_error():
    with pytest.raises(AttributeError):
        _extract_benchmark_response_data({"choices": [None]}, "vendor/model")


def test_extract_benchmark_response_data_preserves_none_usage_error():
    response = {
        "choices": [{"message": {"content": "answer"}}],
        "usage": None,
    }

    with pytest.raises(AttributeError):
        _extract_benchmark_response_data(response, "vendor/model")
