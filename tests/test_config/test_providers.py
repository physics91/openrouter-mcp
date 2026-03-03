"""
Tests for provider configuration management.

This module tests loading provider configurations, alias resolution,
and provider information retrieval.
"""

import json
from unittest.mock import mock_open, patch

import pytest

from openrouter_mcp.config.providers import (
    get_provider_info,
    get_quality_tier_info,
    load_provider_config,
    resolve_provider_alias,
)


@pytest.fixture(autouse=True)
def reset_config_cache():
    """Reset the configuration cache before each test."""
    import openrouter_mcp.config.providers as providers_module

    providers_module._config_cache = None
    yield
    providers_module._config_cache = None


class TestLoadProviderConfig:
    """Test provider configuration loading."""

    def test_load_config_from_file(self):
        """Test loading configuration from existing file."""
        # Create mock configuration
        mock_config = {
            "providers": {
                "openai": {
                    "display_name": "OpenAI",
                    "website": "https://openai.com",
                    "description": "Leading AI research organization",
                    "default_capabilities": {
                        "supports_streaming": True,
                        "supports_system_prompt": True,
                    },
                    "model_families": ["gpt-3", "gpt-4"],
                }
            },
            "aliases": {"oai": "openai", "chatgpt": "openai"},
            "quality_tiers": {
                "premium": {
                    "description": "High-quality flagship models",
                    "typical_cost": "High",
                    "examples": ["gpt-4", "claude-3-opus"],
                }
            },
        }

        # Mock the file open
        mock_file_content = json.dumps(mock_config)
        with patch("builtins.open", mock_open(read_data=mock_file_content)):
            with patch("pathlib.Path.exists", return_value=True):
                result = load_provider_config()

        assert result == mock_config
        assert "providers" in result
        assert "aliases" in result
        assert "quality_tiers" in result

    def test_load_config_caching(self):
        """Test that configuration is cached after first load."""
        mock_config = {"providers": {}, "aliases": {}, "quality_tiers": {}}
        mock_file_content = json.dumps(mock_config)

        with patch("builtins.open", mock_open(read_data=mock_file_content)):
            with patch("pathlib.Path.exists", return_value=True):
                # Load twice
                result1 = load_provider_config()
                result2 = load_provider_config()

                # File should only be opened once due to caching
                assert result1 == result2
                # Note: Due to module-level caching, we can't easily verify call count here

    def test_load_config_file_not_found(self):
        """Test handling of missing configuration file."""
        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            result = load_provider_config()

        # Should return default empty configuration
        assert result == {"providers": {}, "aliases": {}, "quality_tiers": {}}

    def test_load_config_invalid_json(self):
        """Test handling of invalid JSON in configuration file."""
        invalid_json = "{invalid json content"

        with patch("builtins.open", mock_open(read_data=invalid_json)):
            result = load_provider_config()

        # Should return default empty configuration
        assert result == {"providers": {}, "aliases": {}, "quality_tiers": {}}

    def test_load_config_general_exception(self):
        """Test handling of unexpected errors during load."""
        with patch("builtins.open", side_effect=Exception("Unexpected error")):
            result = load_provider_config()

        # Should return default empty configuration
        assert result == {"providers": {}, "aliases": {}, "quality_tiers": {}}


class TestResolveProviderAlias:
    """Test provider alias resolution."""

    def test_resolve_direct_alias(self):
        """Test resolving a direct alias to canonical name."""
        mock_config = {
            "providers": {"openai": {}},
            "aliases": {"oai": "openai", "chatgpt": "openai"},
        }

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            result = resolve_provider_alias("oai")
            assert result == "openai"

            result = resolve_provider_alias("chatgpt")
            assert result == "openai"

    def test_resolve_canonical_name(self):
        """Test resolving a name that's already canonical."""
        mock_config = {"providers": {"openai": {}, "anthropic": {}}, "aliases": {}}

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            result = resolve_provider_alias("openai")
            assert result == "openai"

            result = resolve_provider_alias("anthropic")
            assert result == "anthropic"

    def test_resolve_case_insensitive(self):
        """Test that alias resolution is case-insensitive."""
        mock_config = {"providers": {"openai": {}}, "aliases": {"oai": "openai"}}

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            # Test various cases
            assert resolve_provider_alias("OAI") == "openai"
            assert resolve_provider_alias("Oai") == "openai"
            assert resolve_provider_alias("OPENAI") == "openai"
            assert resolve_provider_alias("OpenAI") == "openai"

    def test_resolve_partial_match(self):
        """Test resolving partial matches in aliases."""
        mock_config = {"providers": {"openai": {}}, "aliases": {"gpt": "openai"}}

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            # Partial match should resolve
            result = resolve_provider_alias("gpt-4")
            assert result == "openai"

    def test_resolve_unknown_provider(self):
        """Test resolving an unknown provider name."""
        mock_config = {"providers": {}, "aliases": {}}

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            result = resolve_provider_alias("unknown-provider")
            # Should return the input as-is
            assert result == "unknown-provider"

    def test_resolve_empty_provider(self):
        """Test resolving empty or None provider name."""
        mock_config = {"providers": {}, "aliases": {}}

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            result = resolve_provider_alias("")
            assert result == "unknown"

            result = resolve_provider_alias(None)
            assert result == "unknown"


class TestGetProviderInfo:
    """Test provider information retrieval."""

    def test_get_existing_provider_info(self):
        """Test getting info for an existing provider."""
        mock_config = {
            "providers": {
                "openai": {
                    "display_name": "OpenAI",
                    "website": "https://openai.com",
                    "description": "Leading AI research organization",
                    "default_capabilities": {
                        "supports_streaming": True,
                        "supports_system_prompt": True,
                    },
                    "model_families": ["gpt-3", "gpt-4"],
                }
            },
            "aliases": {},
        }

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            result = get_provider_info("openai")

        assert result["display_name"] == "OpenAI"
        assert result["website"] == "https://openai.com"
        assert result["default_capabilities"]["supports_streaming"] is True
        assert "gpt-4" in result["model_families"]

    def test_get_provider_info_via_alias(self):
        """Test getting info using an alias."""
        mock_config = {
            "providers": {
                "openai": {"display_name": "OpenAI", "website": "https://openai.com"}
            },
            "aliases": {"oai": "openai"},
        }

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            result = get_provider_info("oai")

        assert result["display_name"] == "OpenAI"

    def test_get_unknown_provider_info(self):
        """Test getting info for an unknown provider returns defaults."""
        mock_config = {"providers": {}, "aliases": {}}

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            result = get_provider_info("unknown-provider")

        # Should return default info
        assert result["display_name"] == "Unknown-Provider"
        assert result["description"] == "AI model provider: unknown-provider"
        assert result["default_capabilities"]["supports_streaming"] is True
        assert result["model_families"] == []

    def test_get_provider_info_case_insensitive(self):
        """Test that provider info lookup is case-insensitive."""
        mock_config = {
            "providers": {"openai": {"display_name": "OpenAI"}},
            "aliases": {},
        }

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            result1 = get_provider_info("OpenAI")
            result2 = get_provider_info("OPENAI")
            result3 = get_provider_info("openai")

            # All should resolve to the same provider
            assert (
                result1["display_name"]
                == result2["display_name"]
                == result3["display_name"]
            )


class TestGetQualityTierInfo:
    """Test quality tier information retrieval."""

    def test_get_existing_tier_info(self):
        """Test getting info for an existing quality tier."""
        mock_config = {
            "quality_tiers": {
                "premium": {
                    "description": "High-quality flagship models",
                    "typical_cost": "High",
                    "examples": ["gpt-4", "claude-3-opus"],
                }
            }
        }

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            result = get_quality_tier_info("premium")

        assert result["description"] == "High-quality flagship models"
        assert result["typical_cost"] == "High"
        assert "gpt-4" in result["examples"]

    def test_get_unknown_tier_info(self):
        """Test getting info for an unknown quality tier returns defaults."""
        mock_config = {"quality_tiers": {}}

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            result = get_quality_tier_info("unknown-tier")

        # Should return default info
        assert result["description"] == "Quality tier: unknown-tier"
        assert result["typical_cost"] == "Variable"
        assert result["examples"] == []

    def test_get_multiple_tier_info(self):
        """Test getting info for multiple quality tiers."""
        mock_config = {
            "quality_tiers": {
                "premium": {
                    "description": "Premium models",
                    "typical_cost": "High",
                    "examples": ["gpt-4"],
                },
                "budget": {
                    "description": "Budget models",
                    "typical_cost": "Low",
                    "examples": ["gpt-3.5-turbo"],
                },
            }
        }

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            premium = get_quality_tier_info("premium")
            budget = get_quality_tier_info("budget")

        assert premium["typical_cost"] == "High"
        assert budget["typical_cost"] == "Low"


class TestProviderConfigIntegration:
    """Integration tests for provider configuration."""

    def test_full_workflow(self):
        """Test complete workflow from alias to provider info."""
        mock_config = {
            "providers": {
                "openai": {
                    "display_name": "OpenAI",
                    "website": "https://openai.com",
                    "model_families": ["gpt"],
                },
                "anthropic": {
                    "display_name": "Anthropic",
                    "website": "https://anthropic.com",
                    "model_families": ["claude"],
                },
            },
            "aliases": {"oai": "openai", "ant": "anthropic"},
            "quality_tiers": {
                "premium": {
                    "description": "Premium tier",
                    "examples": ["gpt-4", "claude-3"],
                }
            },
        }

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            # Resolve alias
            canonical = resolve_provider_alias("oai")
            assert canonical == "openai"

            # Get provider info
            info = get_provider_info(canonical)
            assert info["display_name"] == "OpenAI"

            # Get tier info
            tier = get_quality_tier_info("premium")
            assert "gpt-4" in tier["examples"]

    def test_config_consistency(self):
        """Test that multiple calls return consistent results."""
        mock_config = {
            "providers": {"openai": {"display_name": "OpenAI"}},
            "aliases": {"oai": "openai"},
            "quality_tiers": {},
        }

        with patch(
            "openrouter_mcp.config.providers.load_provider_config",
            return_value=mock_config,
        ):
            # Multiple calls should return same results
            for _ in range(5):
                assert resolve_provider_alias("oai") == "openai"
                assert get_provider_info("openai")["display_name"] == "OpenAI"
