from unittest.mock import MagicMock

import pytest

from src.openrouter_mcp.free.router import FreeModelRouter


def make_free_model(model_id, context_length=32768, provider="unknown"):
    """Shared test helper for creating free model dicts."""
    return {
        "id": model_id,
        "name": model_id,
        "context_length": context_length,
        "cost_tier": "free",
        "provider": provider,
        "capabilities": {},
    }


@pytest.fixture
def mock_model_cache():
    cache = MagicMock()
    cache.filter_models.return_value = []
    return cache


@pytest.fixture
def free_models():
    return [
        make_free_model("google/gemma:free", 131072, "google"),
        make_free_model("deepseek/chat:free", 131072, "deepseek"),
        make_free_model("qwen/model:free", 32768, "qwen"),
    ]


@pytest.fixture
def mock_cache(free_models):
    cache = MagicMock()
    cache.filter_models.return_value = free_models
    return cache


@pytest.fixture
def router(mock_model_cache):
    return FreeModelRouter(mock_model_cache)


@pytest.fixture(autouse=True)
def _reset_handler_singletons():
    """Reset handler module-level singletons between tests to prevent state leakage."""
    yield
    from src.openrouter_mcp.handlers import free_chat as handler_module

    handler_module._router = None
    handler_module._router_lock = None
    # _metrics and _classifier are added in Task 8. Setting to None here is safe
    # (Python allows creating module attrs via assignment) and ensures cleanup once they exist.
    handler_module._metrics = None
    handler_module._classifier = None
