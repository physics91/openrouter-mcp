"""
Test fixtures module for OpenRouter MCP Server.

This module provides centralized, DRY-compliant test fixtures and factories
for consistent test setup across all test modules.

Usage:
    from tests.fixtures import MockClientFactory, ResponseFactory
    from tests.fixtures.ci_fixtures import (
        create_sample_models,
        create_sample_task,
        MockModelProviderFactory,
    )
"""

from .mock_clients import MockClientFactory
from .mock_responses import ResponseFactory, create_mock_response
from .state_management import lifecycle_manager_scope, reset_singleton_state

__all__ = [
    "MockClientFactory",
    "ResponseFactory",
    "create_mock_response",
    "lifecycle_manager_scope",
    "reset_singleton_state",
]
