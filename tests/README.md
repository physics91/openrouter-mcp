# OpenRouter MCP Server - Test Suite

Comprehensive test suite for the OpenRouter MCP Server following the Test Pyramid strategy.

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run quick smoke test (< 1 second)
pytest tests/test_tool_registration_simple.py -v

# Run all safe tests (no API calls)
pytest --ignore=tests/test_real_world_integration.py -v

# Run with coverage
pytest --cov=src/openrouter_mcp --cov-report=html --ignore=tests/test_real_world_integration.py
```

## Test Files

### Critical Regression Tests ⭐

**`test_tool_registration_simple.py`** - Fastest, most reliable tests
- Verifies all tools are registered
- Direct tool manager access (no async)
- **CRITICAL**: Catches "0 tools" bug
- Execution time: < 1 second
- **Run this first!**

```bash
pytest tests/test_tool_registration_simple.py -v
```

### Integration Tests

**`test_mcp_integration.py`** - Server integration without API calls
- FastMCP tool registration verification
- Server startup and configuration
- Environment validation
- Tool metadata checks
- Shared registry pattern tests

**`test_collective_intelligence_mocked.py`** - CI features with mocked APIs
- All collective intelligence tools tested
- No real API calls (fully mocked)
- Comprehensive coverage of:
  - Collective chat completion
  - Ensemble reasoning
  - Adaptive model selection
  - Cross-model validation
  - Collaborative problem solving

**`test_mcp_server_fixed.py`** - Improved server tests with assertions
- Replaces old print-only tests
- Server initialization tests
- Environment variable handling
- Tool description validation

### End-to-End Tests

**`test_real_world_integration.py`** - Real API integration tests
- ⚠️ Requires `OPENROUTER_API_KEY`
- ⚠️ Makes real API calls (costs money)
- ⚠️ Skipped in CI by default
- Use for manual/nightly testing only

```bash
# Only run with valid API key
export OPENROUTER_API_KEY=sk-or-...
pytest tests/test_real_world_integration.py -v -s
```

### Unit Tests

**`test_collective_intelligence/`** - Unit tests for CI components
- `test_consensus_engine.py` - Consensus algorithms
- `test_adaptive_router.py` - Model routing logic
- `test_cross_validator.py` - Validation logic
- `test_collaborative_solver.py` - Problem solving
- `test_ensemble_reasoning.py` - Reasoning engine

**`test_handlers/`** - Handler-specific tests
- `test_chat_handler.py` - Chat functionality

**`test_client/`** - OpenRouter client tests
- `test_openrouter.py` - Client implementation

## Running Tests

### By Test Suite

```bash
# Quick smoke test (critical regression tests)
pytest tests/test_tool_registration_simple.py -v

# Integration tests (no API calls)
pytest tests/test_mcp_integration.py tests/test_collective_intelligence_mocked.py -v

# All safe tests
pytest --ignore=tests/test_real_world_integration.py -v

# Real API tests (manual only)
OPENROUTER_API_KEY=sk-... pytest tests/test_real_world_integration.py -v
```

### By Marker

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Real API tests only (needs API key)
pytest -m real_api
```

### With Coverage

```bash
# Coverage report
pytest --cov=src/openrouter_mcp --cov-report=html --ignore=tests/test_real_world_integration.py

# View coverage report
open htmlcov/index.html  # On macOS/Linux
start htmlcov/index.html # On Windows
```

### Using Test Runner

```bash
# Quick smoke test
python run_tests.py quick

# All integration tests
python run_tests.py integration

# All safe tests
python run_tests.py all

# With coverage
python run_tests.py coverage

# Real API tests (with confirmation)
python run_tests.py real
```

## Test Pyramid

```
              /\
             /  \
            / E2E \ ← test_real_world_integration.py (few, slow, expensive)
           /______\
          /        \
         / Integration \ ← test_mcp_integration.py, test_*_mocked.py (medium, mocked)
        /__________\
       /            \
      /  Unit Tests  \ ← test_collective_intelligence/, test_handlers/ (many, fast)
     /________________\
```

## Critical Regression Tests

These tests MUST always pass:

1. **Tool Registration Test**
   ```bash
   pytest tests/test_tool_registration_simple.py::TestToolRegistrationSimple::test_no_zero_tools_regression -v
   ```
   - Ensures tools are always registered
   - Catches import issues
   - Execution: < 1 second

2. **Server Startup Test**
   ```bash
   pytest tests/test_mcp_server_fixed.py::TestMCPServerBasicFunctionality::test_no_zero_tools_regression -v
   ```
   - Validates server initialization
   - Checks all handlers
   - Execution: < 2 seconds

## Test Configuration

### `pytest.ini`
- Test discovery settings
- Pytest markers
- Coverage configuration
- Warning filters

### `conftest.py`
- Shared fixtures
- Mock data factories
- Test utilities

## CI/CD

Tests are designed to run in CI without API keys:

```yaml
# GitHub Actions
- name: Run tests
  run: |
    pytest --ignore=tests/test_real_world_integration.py -v
```

All tests in CI:
- ✅ No API calls
- ✅ No external dependencies
- ✅ Fast execution (< 30 seconds)
- ✅ No costs

## Test Coverage Goals

| Component | Goal | Current | Status |
|-----------|------|---------|--------|
| MCP Server | 60% | 0% | ❌ Critical Gap |
| Chat Handlers | 90% | 94% | ✅ Excellent |
| Benchmark System | 50% | 22% | ❌ Needs Work |
| Collective Intelligence | 80% | 85-98% | ✅ Excellent |
| OpenRouter Client | 80% | 64% | ⚠️ Good |
| **Overall Project** | **60%** | **66%** | ✅ **Passing** |

## Mocking Examples

### Mock OpenRouter Client
```python
@patch('openrouter_mcp.handlers.chat.OpenRouterClient')
async def test_example(mock_client_class):
    mock_client = AsyncMock()
    mock_client_class.from_env.return_value = mock_client
    mock_client.chat_completion.return_value = {"choices": [...]}
    # Test code here
```

### Mock Model Cache
```python
@patch('openrouter_mcp.handlers.mcp_benchmark.ModelCache')
async def test_example(mock_cache_class):
    mock_cache = AsyncMock()
    mock_cache.get_models.return_value = [...]
    # Test code here
```

## Writing New Tests

### For New Features

1. **Add Unit Test** - Fast, isolated test
2. **Add Integration Test** - With mocked dependencies
3. **Optionally Add E2E Test** - For critical user flows

### Test Template

```python
import pytest
from unittest.mock import patch, AsyncMock

class TestNewFeature:
    """Test new feature."""

    @pytest.mark.unit
    def test_basic_functionality(self):
        """Test basic functionality."""
        # Arrange
        ...
        # Act
        ...
        # Assert
        ...

    @pytest.mark.integration
    @patch('module.ExternalDependency')
    async def test_integration(self, mock_dep):
        """Test integration with mocked dependencies."""
        # Mock setup
        mock_dep.return_value = AsyncMock()
        # Test code
        ...

    @pytest.mark.real_api
    async def test_e2e(self):
        """Test end-to-end (requires API key)."""
        pytest.skip("Requires OPENROUTER_API_KEY")
        # Real API test
        ...
```

## Troubleshooting

### Tests Failing

1. **Check imports**: Ensure `src/` is in Python path
2. **Check environment**: Set `OPENROUTER_API_KEY` if needed
3. **Check dependencies**: Run `pip install -e ".[dev]"`
4. **Check Python version**: Requires Python 3.11+

### Common Issues

**Import Error**: Add `src/` to PYTHONPATH
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

**Async Warnings**: Ensure `pytest-asyncio` is installed
```bash
pip install pytest-asyncio
```

**Coverage Issues**: Ensure running from project root
```bash
cd /path/to/openrouter-mcp
pytest --cov=src/openrouter_mcp
```

## Resources

- [Testing Strategy Documentation](../docs/TESTING_STRATEGY.md)
- [Test Coverage Summary](../docs/TEST_COVERAGE_SUMMARY.md)
- [pytest Documentation](https://docs.pytest.org/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)

## Support

For questions or issues:
1. Check documentation in `docs/`
2. Review existing tests for examples
3. Run tests with `-vv` for verbose output
4. Use `--pdb` to drop into debugger on failure

```bash
pytest tests/test_name.py -vv --pdb
```
