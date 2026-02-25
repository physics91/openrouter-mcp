import pytest
from unittest.mock import MagicMock
from src.openrouter_mcp.free.router import FreeModelRouter


@pytest.fixture
def mock_model_cache():
    cache = MagicMock()
    cache.filter_models.return_value = []
    return cache


@pytest.fixture
def router(mock_model_cache):
    return FreeModelRouter(mock_model_cache)
