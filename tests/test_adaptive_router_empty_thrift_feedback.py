"""Regression tests for empty adaptive-router thrift feedback."""

from unittest.mock import Mock

import pytest

from openrouter_mcp.collective_intelligence import adaptive_router
from openrouter_mcp.collective_intelligence.adaptive_router import AdaptiveRouter
from openrouter_mcp.utils.metadata import ModelProvider


@pytest.mark.unit
def test_empty_thrift_metrics_skip_provider_detection() -> None:
    """An exact empty metrics dict cannot contain provider feedback."""
    router = AdaptiveRouter(Mock())
    provider_extractor = Mock(return_value=ModelProvider.UNKNOWN)
    original_extractor = adaptive_router.extract_provider_from_id
    adaptive_router.extract_provider_from_id = provider_extractor
    try:
        feedback = router._build_thrift_feedback_for_model(
            "provider/model",
            {},
            window_start=None,
            window_end=None,
            lookback_days=-1,
        )
    finally:
        adaptive_router.extract_provider_from_id = original_extractor

    assert feedback == {
        "source": "none",
        "penalty": 0.0,
        "lookback_days": 0,
        "window_start": None,
        "window_end": None,
        "bucket_summary": None,
    }
    provider_extractor.assert_not_called()


@pytest.mark.unit
def test_empty_thrift_mapping_subclass_retains_provider_detection() -> None:
    """Custom mapping subclasses must retain the original lookup path."""

    class Metrics(dict):
        pass

    router = AdaptiveRouter(Mock())
    provider_extractor = Mock(return_value=ModelProvider.UNKNOWN)
    original_extractor = adaptive_router.extract_provider_from_id
    adaptive_router.extract_provider_from_id = provider_extractor
    try:
        router._build_thrift_feedback_for_model(
            "provider/model",
            Metrics(),
            window_start=None,
            window_end=None,
            lookback_days=0,
        )
    finally:
        adaptive_router.extract_provider_from_id = original_extractor

    provider_extractor.assert_called_once_with("provider/model")
