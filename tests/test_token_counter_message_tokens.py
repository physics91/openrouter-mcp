from typing import List

from src.openrouter_mcp.utils.token_counter import TokenCounter


class RecordingEncoding:
    def __init__(self) -> None:
        self.calls: List[str] = []

    def encode(self, text: str) -> List[str]:
        self.calls.append(text)
        return list(text)


def test_count_message_tokens_preserves_encoding_order_and_overhead(monkeypatch):
    counter = TokenCounter()
    encoding = RecordingEncoding()
    requested_models = []
    monkeypatch.setattr(
        counter,
        "_get_encoding_for_model",
        lambda model_id: requested_models.append(model_id) or encoding,
    )
    messages = [
        {"role": "user", "content": "hello", "name": 7},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "caption"},
                {"type": "image_url", "image_url": {"url": "image-data"}},
                "unsupported",
            ],
            "name": "alice",
        },
    ]

    token_count = counter.count_message_tokens(messages, model_id="vendor/model")

    assert token_count == 36
    assert requested_models == ["vendor/model"]
    assert encoding.calls == ["user", "hello", "user", "caption", "alice"]


def test_count_message_tokens_preserves_content_only_fallback(monkeypatch):
    counter = TokenCounter()
    requested_models = []

    def fail_encoding_lookup(model_id):
        requested_models.append(model_id)
        raise RuntimeError("encoding unavailable")

    monkeypatch.setattr(counter, "_get_encoding_for_model", fail_encoding_lookup)
    messages = [
        {"role": "user", "content": "abcdefgh", "metadata": "x" * 100},
        {
            "content": [
                {"type": "text", "text": "12345678"},
                {"type": "image_url", "image_url": {"url": "image-data"}},
            ],
            "name": "ignored",
        },
    ]

    token_count = counter.count_message_tokens(messages, model_id="vendor/model")

    assert token_count == 4
    assert requested_models == ["vendor/model"]


def test_count_message_tokens_empty_input_skips_encoding_lookup(monkeypatch):
    counter = TokenCounter()

    def fail_if_called(model_id):
        raise AssertionError(f"unexpected encoding lookup for {model_id}")

    monkeypatch.setattr(counter, "_get_encoding_for_model", fail_if_called)

    assert counter.count_message_tokens([], model_id="vendor/model") == 0
