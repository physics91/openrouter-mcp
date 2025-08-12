# Testing Guide

Comprehensive testing documentation for the OpenRouter MCP Server, built with Test-Driven Development (TDD) principles.

## Table of Contents
- [Testing Philosophy](#testing-philosophy)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Test Coverage](#test-coverage)
- [Continuous Integration](#continuous-integration)
- [Troubleshooting Tests](#troubleshooting-tests)

## Testing Philosophy

This project follows strict TDD principles:
1. **Red**: Write a failing test first
2. **Green**: Write minimal code to pass the test
3. **Refactor**: Improve code while keeping tests green

### Test Pyramid
```
         /\
        /E2E\        (5%)  - End-to-end scenarios
       /------\
      /Integration\  (20%) - Component interactions
     /------------\
    /   Unit Tests  \ (75%) - Individual functions/methods
   /----------------\
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures and configuration
├── test_client/            # Client layer tests
│   ├── __init__.py
│   └── test_openrouter.py  # OpenRouter client tests
├── test_handlers/          # Handler tests
│   ├── __init__.py
│   ├── test_chat_handler.py
│   └── test_multimodal.py
├── test_mcp_benchmark.py   # Benchmarking tests
├── test_metadata.py        # Metadata system tests
├── test_models_cache.py    # Cache system tests
└── fixtures/              # Test data
    ├── images/            # Test images
    └── responses/         # Mock API responses
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_client/test_openrouter.py

# Run specific test function
pytest tests/test_handlers/test_chat_handler.py::test_chat_completion

# Run tests matching pattern
pytest -k "benchmark"
```

### Test Coverage

```bash
# Run tests with coverage report
pytest --cov=src/openrouter_mcp --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=src/openrouter_mcp --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
```

### Continuous Testing

```bash
# Watch mode - re-run tests on file changes
pytest-watch

# Run tests in parallel
pytest -n auto

# Run only failed tests from last run
pytest --lf

# Run failed tests first, then others
pytest --ff
```

## Writing Tests

### Test File Naming
- Test files must start with `test_`
- Test functions must start with `test_`
- Test classes must start with `Test`

### Basic Test Structure

```python
import pytest
from src.openrouter_mcp.client import OpenRouterClient

class TestOpenRouterClient:
    """Test suite for OpenRouter client."""
    
    @pytest.fixture
    def client(self):
        """Create a test client instance."""
        return OpenRouterClient(api_key="test-key")
    
    def test_client_initialization(self, client):
        """Test client initializes with correct configuration."""
        assert client.api_key == "test-key"
        assert client.base_url == "https://openrouter.ai/api/v1"
    
    @pytest.mark.asyncio
    async def test_chat_completion(self, client, mock_response):
        """Test chat completion request."""
        # Arrange
        messages = [{"role": "user", "content": "Hello"}]
        
        # Act
        response = await client.chat_completion(
            model="openai/gpt-4",
            messages=messages
        )
        
        # Assert
        assert response["choices"][0]["message"]["content"]
        assert response["model"] == "openai/gpt-4"
```

### Testing Async Code

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_async_function():
    """Test asynchronous function."""
    result = await some_async_function()
    assert result == expected_value

# Using pytest-asyncio fixtures
@pytest.fixture
async def async_client():
    """Async fixture for client."""
    client = AsyncClient()
    await client.connect()
    yield client
    await client.disconnect()
```

### Mocking and Fixtures

```python
# conftest.py
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for API calls."""
    mock = AsyncMock()
    mock.post.return_value.json.return_value = {
        "choices": [{"message": {"content": "Test response"}}]
    }
    return mock

@pytest.fixture
def sample_image_base64():
    """Provide sample base64 encoded image."""
    return "data:image/png;base64,iVBORw0KGgoAAAANS..."

# Using fixtures in tests
def test_with_mock(mock_httpx_client):
    """Test using mocked HTTP client."""
    # Your test code here
```

### Parametrized Tests

```python
@pytest.mark.parametrize("model,expected_provider", [
    ("openai/gpt-4", "openai"),
    ("anthropic/claude-3", "anthropic"),
    ("google/gemini-pro", "google"),
])
def test_provider_detection(model, expected_provider):
    """Test provider detection for different models."""
    provider = detect_provider(model)
    assert provider == expected_provider
```

### Testing Error Cases

```python
def test_invalid_api_key():
    """Test handling of invalid API key."""
    with pytest.raises(AuthenticationError) as exc_info:
        client = OpenRouterClient(api_key="invalid")
        client.validate_key()
    
    assert "Invalid API key" in str(exc_info.value)

def test_rate_limit_handling():
    """Test rate limit error handling."""
    client = OpenRouterClient()
    
    with pytest.raises(RateLimitError) as exc_info:
        # Simulate rate limit scenario
        for _ in range(100):
            client.make_request()
    
    assert exc_info.value.retry_after > 0
```

### Benchmark Testing

```python
@pytest.mark.benchmark
async def test_benchmark_performance():
    """Test benchmarking system performance."""
    models = ["openai/gpt-4", "anthropic/claude-3"]
    prompt = "Test prompt"
    
    results = await benchmark_models(
        models=models,
        prompt=prompt,
        runs=3
    )
    
    assert len(results["results"]) == len(models)
    assert all(r["metrics"]["total_time"] > 0 for r in results["results"])
    assert results["rankings"]["by_speed"]
```

### Integration Tests

```python
@pytest.mark.integration
class TestMCPIntegration:
    """Integration tests for MCP server."""
    
    @pytest.fixture
    async def mcp_server(self):
        """Start MCP server for testing."""
        server = await start_test_server()
        yield server
        await server.shutdown()
    
    async def test_full_chat_flow(self, mcp_server):
        """Test complete chat flow through MCP."""
        # Connect to server
        client = MCPClient(server_url=mcp_server.url)
        
        # Send chat request
        response = await client.call_tool(
            "chat_with_model",
            model="openai/gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )
        
        # Verify response
        assert response["choices"]
        assert response["usage"]["total_tokens"] > 0
```

## Test Coverage

### Coverage Goals
- **Overall**: Minimum 80% coverage
- **Critical paths**: 95% coverage
- **New code**: 100% coverage required

### Coverage Configuration

```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto

[coverage:run]
source = src/openrouter_mcp
omit = 
    */tests/*
    */conftest.py
    */__init__.py

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
```

### Checking Coverage

```bash
# Generate coverage report
coverage run -m pytest
coverage report

# Check specific module coverage
coverage report --include="src/openrouter_mcp/handlers/*"

# Find untested lines
coverage report --show-missing
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest --cov=src/openrouter_mcp --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

## Troubleshooting Tests

### Common Issues

#### 1. Async Test Failures
```python
# Problem: Test not marked as async
def test_async_function():  # Wrong
    await some_async_function()

# Solution: Mark test as async
@pytest.mark.asyncio
async def test_async_function():  # Correct
    await some_async_function()
```

#### 2. Fixture Scope Issues
```python
# Problem: Session fixture used in function test
@pytest.fixture(scope="session")
def expensive_resource():
    return create_resource()

# Solution: Use appropriate scope
@pytest.fixture(scope="function")
def test_resource():
    return create_resource()
```

#### 3. Mock Not Working
```python
# Problem: Mocking wrong path
@patch('client.OpenRouterClient')  # Wrong path

# Solution: Mock where it's used
@patch('src.openrouter_mcp.handlers.chat.OpenRouterClient')
```

### Debug Tips

```bash
# Run tests with detailed output
pytest -vvs

# Show print statements
pytest -s

# Debug with pdb
pytest --pdb

# Show local variables on failure
pytest -l

# Stop on first failure
pytest -x

# Run last failed test with pdb
pytest --lf --pdb
```

## Best Practices

### 1. Test Independence
Each test should be independent and not rely on other tests.

### 2. Clear Test Names
Test names should clearly describe what they test.

### 3. Arrange-Act-Assert
Follow the AAA pattern for test structure.

### 4. Use Fixtures
Leverage fixtures for setup and teardown.

### 5. Test One Thing
Each test should verify one specific behavior.

### 6. Fast Tests
Keep unit tests fast (< 100ms per test).

### 7. Deterministic Tests
Tests should produce the same result every time.

### 8. Meaningful Assertions
Use specific assertions with clear failure messages.

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0