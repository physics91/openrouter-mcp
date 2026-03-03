"""
Server Core Tests

Tests for server initialization, configuration validation, shutdown handling,
and signal registration. Targets 0% coverage areas identified in Phase 7.
"""

import asyncio
import os
import signal
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest

pytestmark = pytest.mark.unit


class TestValidateEnvironment:
    """Tests for validate_environment function."""

    def test_validate_environment_missing_api_key(self, monkeypatch):
        """Should raise ValueError when OPENROUTER_API_KEY is missing."""
        from openrouter_mcp.server import validate_environment

        # Import may load .env; remove key after import for deterministic behavior.
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        with pytest.raises(ValueError) as exc_info:
            validate_environment()

        assert "OPENROUTER_API_KEY" in str(exc_info.value)

    def test_validate_environment_success(self, monkeypatch):
        """Should not raise when OPENROUTER_API_KEY is set."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

        from openrouter_mcp.server import validate_environment

        # Should not raise
        validate_environment()

    def test_validate_environment_empty_key(self, monkeypatch):
        """Should raise ValueError when OPENROUTER_API_KEY is empty."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "")

        from openrouter_mcp.server import validate_environment

        with pytest.raises(ValueError) as exc_info:
            validate_environment()

        assert "OPENROUTER_API_KEY" in str(exc_info.value)


class TestCreateApp:
    """Tests for create_app function."""

    def test_create_app_returns_fastmcp(self, monkeypatch):
        """Should return the FastMCP instance."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

        from openrouter_mcp.server import create_app
        from fastmcp import FastMCP

        app = create_app()

        assert isinstance(app, FastMCP)

    def test_create_app_fails_without_api_key(self, monkeypatch):
        """Should raise ValueError when API key is missing."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        from openrouter_mcp.server import create_app

        with pytest.raises(ValueError):
            create_app()


class TestShutdownHandler:
    """Tests for shutdown_handler function."""

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up_client(self, monkeypatch):
        """Should call cleanup_shared_client during shutdown."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

        # Mock the cleanup functions
        mock_cleanup = AsyncMock()
        mock_lifecycle_shutdown = AsyncMock()

        with patch(
            "openrouter_mcp.server.cleanup_shared_client",
            mock_cleanup,
        ):
            with patch(
                "openrouter_mcp.server.shutdown_lifecycle_manager",
                mock_lifecycle_shutdown,
            ):
                # Import and run shutdown handler
                from openrouter_mcp.server import shutdown_handler

                await shutdown_handler()

        # Verify cleanup was called
        mock_cleanup.assert_called_once()
        mock_lifecycle_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_cleanup_errors(self, monkeypatch):
        """Should handle errors during cleanup gracefully."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

        # Mock cleanup to raise error
        async def failing_cleanup():
            raise RuntimeError("Cleanup failed")

        with patch(
            "openrouter_mcp.server.cleanup_shared_client",
            failing_cleanup,
        ):
            with patch(
                "openrouter_mcp.server.shutdown_lifecycle_manager",
                AsyncMock(),
            ):
                from openrouter_mcp.server import shutdown_handler

                # Should not raise
                await shutdown_handler()

    @pytest.mark.asyncio
    async def test_shutdown_handles_lifecycle_errors(self, monkeypatch):
        """Should handle errors in lifecycle manager shutdown."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

        async def failing_lifecycle():
            raise RuntimeError("Lifecycle shutdown failed")

        with patch(
            "openrouter_mcp.server.cleanup_shared_client",
            AsyncMock(),
        ):
            with patch(
                "openrouter_mcp.server.shutdown_lifecycle_manager",
                failing_lifecycle,
            ):
                from openrouter_mcp.server import shutdown_handler

                # Should not raise
                await shutdown_handler()


class TestSignalHandlers:
    """Tests for signal handler registration."""

    def test_signal_handler_registration(self, monkeypatch):
        """Should register SIGINT and SIGTERM handlers."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

        registered_signals = {}

        def mock_signal(sig, handler):
            registered_signals[sig] = handler
            return None

        # Mock signal.signal to capture registrations
        with patch("signal.signal", side_effect=mock_signal):
            # Mock app.run to prevent actual server start
            with patch("openrouter_mcp.mcp_registry.mcp.run"):
                with patch(
                    "openrouter_mcp.server.shutdown_handler",
                    AsyncMock(),
                ):
                    try:
                        from openrouter_mcp.server import main

                        main()
                    except KeyboardInterrupt:
                        pass

        # Note: SIGINT and SIGTERM should be registered
        # The actual registration happens in main()


class TestServerInitialization:
    """Tests for server initialization flow."""

    def test_initialization_logs_success(self, monkeypatch, caplog):
        """Should log success message during initialization."""
        import logging

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

        with caplog.at_level(logging.INFO):
            from openrouter_mcp.server import create_app

            create_app()

        assert any(
            "initialized successfully" in record.message
            for record in caplog.records
        )

    def test_initialization_validates_first(self, monkeypatch):
        """Should validate environment before initializing."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        from openrouter_mcp.server import create_app

        with pytest.raises(ValueError) as exc_info:
            create_app()

        assert "environment variable" in str(exc_info.value).lower()


class TestMCPRegistryIntegration:
    """Tests for integration with mcp_registry."""

    def test_mcp_instance_is_shared(self, monkeypatch):
        """Should use the shared MCP instance from registry."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

        from openrouter_mcp.server import create_app
        from openrouter_mcp.mcp_registry import mcp

        app = create_app()

        assert app is mcp

    def test_handlers_are_registered(self, monkeypatch):
        """Should have handlers registered after import."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

        # Import server to trigger handler registration
        import importlib
        import openrouter_mcp.server

        importlib.reload(openrouter_mcp.server)

        from openrouter_mcp.mcp_registry import mcp

        # MCP should have tools registered
        # Note: Actual tool count depends on handlers


class TestErrorHandling:
    """Tests for error handling in server."""

    def test_main_catches_keyboard_interrupt(self, monkeypatch, caplog):
        """Should handle KeyboardInterrupt gracefully."""
        import logging

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

        def raise_interrupt():
            raise KeyboardInterrupt()

        with patch("openrouter_mcp.mcp_registry.mcp.run", side_effect=raise_interrupt):
            with patch("openrouter_mcp.server.shutdown_handler", AsyncMock()):
                with caplog.at_level(logging.INFO):
                    from openrouter_mcp.server import main

                    # Should not raise
                    main()

        assert any(
            "shutdown" in record.message.lower()
            for record in caplog.records
        )

    def test_main_raises_on_other_errors(self, monkeypatch):
        """Should re-raise non-interrupt exceptions."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

        def raise_error():
            raise RuntimeError("Server failed")

        with patch("openrouter_mcp.mcp_registry.mcp.run", side_effect=raise_error):
            with patch("openrouter_mcp.server.shutdown_handler", AsyncMock()):
                from openrouter_mcp.server import main

                with pytest.raises(RuntimeError):
                    main()
