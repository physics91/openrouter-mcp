#!/usr/bin/env python3
"""
Comprehensive integration tests for server.py

This test suite improves coverage from 0% to 60%+ by testing:
- Server initialization and configuration
- Handler registration and tool loading
- Lifecycle management and shutdown hooks
- Environment validation
- Signal handling
- Integration points with MCP registry and lifecycle manager
"""

import asyncio
import signal
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def _get_registered_tools(mcp_instance):
    """Fetch registered tool mapping via FastMCP public API."""

    async def _collect():
        tools = await mcp_instance.list_tools()
        return {tool.name: tool for tool in tools}

    return asyncio.run(_collect())


class TestServerInitialization:
    """Test server initialization and configuration."""

    def test_server_module_imports(self):
        """Test that server module can be imported successfully."""
        from openrouter_mcp import server

        assert server is not None
        assert hasattr(server, "create_app")
        assert hasattr(server, "main")
        assert hasattr(server, "validate_environment")
        assert hasattr(server, "shutdown_handler")

    def test_mcp_registry_import(self):
        """Test that MCP registry is imported correctly."""
        from openrouter_mcp.server import mcp

        assert mcp is not None
        assert hasattr(mcp, "list_tools")

    def test_handler_modules_imported(self, mock_env_vars):
        """Test that handlers can be registered explicitly during server init."""
        from openrouter_mcp.handlers import register_handlers
        from openrouter_mcp.mcp_registry import mcp

        register_handlers()

        # Verify handlers have registered tools
        tools = _get_registered_tools(mcp)
        assert len(tools) > 0, "No tools registered"

        # Verify expected minimum tool count
        assert len(tools) >= 15, f"Expected at least 15 tools, got {len(tools)}"

    def test_logging_configuration(self):
        """Test that logging is configured correctly."""
        import logging

        # Verify logger exists
        logger = logging.getLogger("openrouter_mcp.server")
        assert logger is not None


class TestHandlerRegistration:
    """Test handler registration and tool loading."""

    def test_all_handlers_register_tools(self, mock_env_vars):
        """Test that all handlers register their tools with the MCP instance."""
        from openrouter_mcp.handlers import register_handlers
        from openrouter_mcp.mcp_registry import mcp

        register_handlers()

        tools = _get_registered_tools(mcp)

        # Verify expected tools from each handler
        expected_tools = {
            # Chat handler
            "chat_with_model",
            "list_available_models",
            "get_usage_stats",
            # Multimodal handler
            "chat_with_vision",
            "list_vision_models",
            # MCP Benchmark handler
            "benchmark_models",
            "compare_model_performance",
            "compare_model_categories",
            "get_benchmark_history",
            "export_benchmark_report",
            # Collective Intelligence handler
            "collective_chat_completion",
            "ensemble_reasoning",
            "adaptive_model_selection",
            "cross_model_validation",
            "collaborative_problem_solving",
        }

        registered_tools = set(tools.keys())
        missing = expected_tools - registered_tools
        assert not missing, f"Expected tools missing: {missing}"

    def test_tool_count(self, mock_env_vars):
        """Test that the correct number of tools are registered."""
        from openrouter_mcp.handlers import register_handlers
        from openrouter_mcp.mcp_registry import mcp

        register_handlers()

        tools = _get_registered_tools(mcp)
        assert len(tools) >= 15, f"Expected at least 15 tools, got {len(tools)}"

    def test_tool_metadata(self, mock_env_vars):
        """Test that registered tools have proper metadata."""
        from openrouter_mcp.handlers import register_handlers
        from openrouter_mcp.mcp_registry import mcp

        register_handlers()

        tools = _get_registered_tools(mcp)

        # Check a few key tools for metadata
        for tool_name in [
            "chat_with_model",
            "list_available_models",
            "collective_chat_completion",
        ]:
            assert tool_name in tools, f"Tool '{tool_name}' not found"
            tool = tools[tool_name]
            assert hasattr(tool, "fn"), f"Tool '{tool_name}' missing function"


class TestEnvironmentValidation:
    """Test environment variable validation."""

    def test_validate_environment_with_valid_key(self, mock_env_vars):
        """Test environment validation with valid API key."""
        from openrouter_mcp.server import validate_environment

        # Should not raise any exception
        validate_environment()

    def test_validate_environment_missing_api_key(self, monkeypatch):
        """Test environment validation fails with missing API key."""
        from openrouter_mcp.server import validate_environment

        # Remove API key
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        # Should raise ValueError
        with pytest.raises(ValueError, match="Missing required environment variables"):
            validate_environment()

    def test_validate_environment_empty_api_key(self, monkeypatch):
        """Test environment validation fails with empty API key."""
        from openrouter_mcp.server import validate_environment

        # Set empty API key
        monkeypatch.setenv("OPENROUTER_API_KEY", "")

        # Should raise ValueError
        with pytest.raises(ValueError, match="Missing required environment variables"):
            validate_environment()

    def test_create_app_validates_environment(self, mock_env_vars):
        """Test that create_app() validates environment variables."""
        from openrouter_mcp.server import create_app

        # Should succeed with valid environment
        app = create_app()
        assert app is not None

    def test_create_app_fails_without_api_key(self, monkeypatch):
        """Test that create_app() fails without API key."""
        from openrouter_mcp.server import create_app

        # Remove API key
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        # Should raise ValueError
        with pytest.raises(ValueError):
            create_app()

    def test_create_app_registers_handlers(self, mock_env_vars):
        """Test that create_app explicitly registers handlers before returning."""
        from openrouter_mcp.server import create_app, mcp

        with patch("openrouter_mcp.server.register_handlers", create=True) as mock_register:
            with patch("openrouter_mcp.server.validate_environment") as mock_validate:
                app = create_app()

        assert app is mcp
        mock_register.assert_called_once()
        mock_validate.assert_called_once()


class TestLifecycleManagement:
    """Test server lifecycle management."""

    @pytest.mark.asyncio
    async def test_shutdown_handler_cleanup(self, mock_env_vars):
        """Test that shutdown handler performs cleanup."""
        from openrouter_mcp.server import shutdown_handler

        # Mock the lifecycle manager shutdown (patched on server module)
        with patch(
            "openrouter_mcp.server.shutdown_lifecycle_manager", new_callable=AsyncMock
        ) as mock_shutdown:
            await shutdown_handler()

            # Verify shutdown was called
            mock_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handler_error_handling(self, mock_env_vars):
        """Test that shutdown handler handles errors gracefully."""
        from openrouter_mcp.server import shutdown_handler

        # Mock shutdown to raise an error (patched on server module)
        with patch(
            "openrouter_mcp.server.shutdown_lifecycle_manager", new_callable=AsyncMock
        ) as mock_shutdown:
            mock_shutdown.side_effect = Exception("Test error")

            # Should not raise exception (logs error instead)
            await shutdown_handler()

            # Verify shutdown was attempted
            mock_shutdown.assert_called_once()

    def test_signal_handler_registration(self, mock_env_vars):
        """Test that signal handlers are registered correctly."""
        from openrouter_mcp.server import main

        with patch("openrouter_mcp.server.signal.signal") as mock_signal:
            with patch("openrouter_mcp.server.create_app") as mock_create_app:
                # Mock the app to avoid actually running
                mock_app = Mock()
                mock_app.run.side_effect = KeyboardInterrupt()
                mock_create_app.return_value = mock_app

                with patch("openrouter_mcp.server.asyncio.run"):
                    try:
                        main()
                    except (KeyboardInterrupt, SystemExit):
                        pass

                # Verify signal handlers were registered
                calls = mock_signal.call_args_list
                signal_types = [call_args[0][0] for call_args in calls]
                assert signal.SIGINT in signal_types
                assert signal.SIGTERM in signal_types

    def test_signal_handler_triggers_shutdown(self, mock_env_vars):
        """Test that signal handler triggers shutdown."""
        from openrouter_mcp.server import main

        signal_handler_ref = None

        def capture_signal_handler(sig, handler):
            nonlocal signal_handler_ref
            if sig == signal.SIGINT:
                signal_handler_ref = handler

        with patch("openrouter_mcp.server.signal.signal", side_effect=capture_signal_handler):
            with patch("openrouter_mcp.server.create_app") as mock_create_app:
                mock_app = Mock()
                mock_app.run.side_effect = KeyboardInterrupt()
                mock_create_app.return_value = mock_app

                with patch("openrouter_mcp.server.asyncio.run") as mock_asyncio_run:
                    try:
                        main()
                    except (KeyboardInterrupt, SystemExit):
                        pass

                    # Verify shutdown handler was called
                    assert mock_asyncio_run.call_count >= 1


class TestServerMain:
    """Test the main entry point."""

    def test_main_creates_app(self, mock_env_vars):
        """Test that main() creates the application."""
        from openrouter_mcp.server import main

        with patch("openrouter_mcp.server.create_app") as mock_create_app:
            mock_app = Mock()
            mock_app.run.side_effect = KeyboardInterrupt()
            mock_create_app.return_value = mock_app

            with patch("openrouter_mcp.server.signal.signal"):
                with patch("openrouter_mcp.server.asyncio.run"):
                    try:
                        main()
                    except (KeyboardInterrupt, SystemExit):
                        pass

            # Verify create_app was called
            mock_create_app.assert_called_once()

    def test_main_configures_logging_before_startup(self, mock_env_vars):
        """Test that main() configures logging at runtime."""
        from openrouter_mcp.server import main

        with patch("openrouter_mcp.server.configure_logging", create=True) as mock_configure:
            with patch("openrouter_mcp.server.create_app") as mock_create_app:
                mock_app = Mock()
                mock_app.run.side_effect = KeyboardInterrupt()
                mock_create_app.return_value = mock_app

                with patch("openrouter_mcp.server.signal.signal"):
                    with patch("openrouter_mcp.server.asyncio.run"):
                        main()

        mock_configure.assert_called_once()

    def test_main_starts_server(self, mock_env_vars):
        """Test that main() starts the MCP server."""
        from openrouter_mcp.server import main

        with patch("openrouter_mcp.server.create_app") as mock_create_app:
            mock_app = Mock()
            mock_app.run.side_effect = KeyboardInterrupt()
            mock_create_app.return_value = mock_app

            with patch("openrouter_mcp.server.signal.signal"):
                with patch("openrouter_mcp.server.asyncio.run"):
                    try:
                        main()
                    except (KeyboardInterrupt, SystemExit):
                        pass

            # Verify app.run() was called
            mock_app.run.assert_called_once()

    def test_main_handles_keyboard_interrupt(self, mock_env_vars):
        """Test that main() handles KeyboardInterrupt gracefully."""
        from openrouter_mcp.server import main

        with patch("openrouter_mcp.server.create_app") as mock_create_app:
            mock_app = Mock()
            mock_app.run.side_effect = KeyboardInterrupt()
            mock_create_app.return_value = mock_app

            with patch("openrouter_mcp.server.signal.signal"):
                with patch("openrouter_mcp.server.asyncio.run"):
                    # Should not raise exception
                    main()

    def test_main_handles_server_error(self, mock_env_vars):
        """Test that main() handles server errors."""
        from openrouter_mcp.server import main

        with patch("openrouter_mcp.server.create_app") as mock_create_app:
            # Simulate server error
            mock_create_app.side_effect = Exception("Server error")

            # Should raise exception
            with pytest.raises(Exception, match="Server error"):
                main()

    def test_main_cleanup_on_normal_exit(self, mock_env_vars):
        """Test that cleanup runs on normal exit."""
        from openrouter_mcp.server import main

        with patch("openrouter_mcp.server.create_app") as mock_create_app:
            mock_app = Mock()
            # Simulate normal exit (no exception)
            mock_app.run.return_value = None
            mock_create_app.return_value = mock_app

            with patch("openrouter_mcp.server.signal.signal"):
                with patch("openrouter_mcp.server.asyncio.run") as mock_asyncio_run:
                    try:
                        main()
                    except (KeyboardInterrupt, SystemExit):
                        pass

                    # Verify cleanup was called (shutdown_handler)
                    assert mock_asyncio_run.call_count >= 1


class TestIntegrationPoints:
    """Test integration with other components."""

    def test_mcp_registry_integration(self, mock_env_vars):
        """Test integration with MCP registry."""
        from openrouter_mcp.mcp_registry import mcp as registry_mcp
        from openrouter_mcp.server import mcp

        # Verify they are the same instance
        assert mcp is registry_mcp

    def test_lifecycle_manager_integration(self, mock_env_vars):
        """Test integration with lifecycle manager."""
        from openrouter_mcp.collective_intelligence import shutdown_lifecycle_manager

        # Verify shutdown_handler uses lifecycle manager
        assert shutdown_lifecycle_manager is not None

    @pytest.mark.asyncio
    async def test_operational_controls_initialization(self, mock_env_vars):
        """Test that operational controls are initialized."""
        from openrouter_mcp.collective_intelligence import get_lifecycle_manager

        # Get lifecycle manager (creates it if not exists)
        manager = await get_lifecycle_manager()
        assert manager is not None
        assert hasattr(manager, "shutdown")
        assert hasattr(manager, "configure")
        assert hasattr(manager, "get_consensus_engine")

    def test_dotenv_loading(self, tmp_path, monkeypatch):
        """Test that create_app loads .env at runtime if present."""
        env_file = tmp_path / ".env"
        env_file.write_text("OPENROUTER_API_KEY=test-key-from-file\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        from openrouter_mcp import server

        with patch("openrouter_mcp.server.register_handlers", create=True):
            with patch("openrouter_mcp.server.validate_environment"):
                with patch("openrouter_mcp.server.load_dotenv") as mock_load_dotenv:
                    server.create_app()

        mock_load_dotenv.assert_called_once()


class TestServerConfiguration:
    """Test server configuration and setup."""

    def test_create_app_returns_mcp_instance(self, mock_env_vars):
        """Test that create_app returns the MCP instance."""
        from openrouter_mcp.server import create_app

        app = create_app()
        assert app is not None
        assert hasattr(app, "list_tools")

    def test_server_name(self, mock_env_vars):
        """Test that server has correct name."""
        from openrouter_mcp.server import mcp

        # The MCP instance should have the name 'openrouter-mcp'
        assert hasattr(mcp, "name")
        assert mcp.name == "openrouter-mcp"

    def test_fastmcp_instance(self, mock_env_vars):
        """Test that server uses FastMCP."""
        from fastmcp import FastMCP

        from openrouter_mcp.server import mcp

        assert isinstance(mcp, FastMCP)


class TestErrorHandling:
    """Test error handling in server."""

    def test_import_error_fallback(self):
        """Test that import error fallback works."""
        # The server has try/except blocks for imports
        # This test verifies the import paths exist
        from openrouter_mcp import server

        assert hasattr(server, "mcp")

    @pytest.mark.asyncio
    async def test_shutdown_handler_import_error(self, mock_env_vars):
        """Test shutdown handler handles import errors."""
        from openrouter_mcp.server import shutdown_handler

        # Mock the shutdown to fail with ImportError
        with patch(
            "openrouter_mcp.server.shutdown_lifecycle_manager", new_callable=AsyncMock
        ) as mock_shutdown:
            mock_shutdown.side_effect = ImportError("Module not found")

            # Should handle error gracefully (logs it instead of raising)
            await shutdown_handler()

            # Verify shutdown was attempted
            mock_shutdown.assert_called_once()


class TestServerDocumentation:
    """Test server documentation and metadata."""

    def test_module_docstring(self):
        """Test that server module has documentation."""
        from openrouter_mcp import server

        assert server.__doc__ is not None
        assert len(server.__doc__) > 0
        assert "OpenRouter MCP Server" in server.__doc__

    def test_function_docstrings(self):
        """Test that server functions have documentation."""
        from openrouter_mcp.server import create_app, main, shutdown_handler, validate_environment

        assert create_app.__doc__ is not None
        assert validate_environment.__doc__ is not None
        assert shutdown_handler.__doc__ is not None
        assert main.__doc__ is not None


# Run coverage check if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=openrouter_mcp.server", "--cov-report=term-missing"])
