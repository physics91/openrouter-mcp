import pytest


class TestFreeChatRegistration:
    @pytest.mark.unit
    def test_free_chat_importable(self):
        from src.openrouter_mcp.handlers.free_chat import free_chat, FreeChatRequest
        assert free_chat is not None
        assert FreeChatRequest is not None

    @pytest.mark.unit
    def test_handlers_init_exports_free_chat(self):
        from src.openrouter_mcp.handlers import free_chat
        assert free_chat is not None

    @pytest.mark.unit
    def test_free_chat_request_model_validates(self):
        from src.openrouter_mcp.handlers.free_chat import FreeChatRequest
        req = FreeChatRequest(message="test")
        assert req.message == "test"
