# Contributing to OpenRouter MCP Server

Thank you for your interest in contributing to OpenRouter MCP Server! This guide will help you get started with development and ensure your contributions align with the project's standards.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)
- [Getting Help](#getting-help)

## Development Setup

### Prerequisites

- **Python 3.9+** with pip
- **Node.js 16+** with npm
- **Git** for version control
- **OpenRouter API Key** for testing

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/your-username/openrouter-mcp.git
cd openrouter-mcp

# Add upstream remote
git remote add upstream https://github.com/original-repo/openrouter-mcp.git
```

### 2. Development Environment

#### Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt
pip install -e .
```

#### Node.js Environment

```bash
# Install Node.js dependencies
npm install

# Link for global testing
npm link
```

### 3. Environment Configuration

Create a `.env` file for development:

```env
# Development configuration
OPENROUTER_API_KEY=your-test-api-key
OPENROUTER_APP_NAME=openrouter-mcp-dev
OPENROUTER_HTTP_REFERER=https://localhost

# Development server
HOST=localhost
PORT=8000
LOG_LEVEL=debug
```

### 4. Verify Setup

```bash
# Run tests
npm run test

# Start development server
npm run start
```

## Project Structure

```
openrouter-mcp/
├── bin/                           # CLI scripts
│   ├── openrouter-mcp.js         # Main CLI entry point
│   └── check-python.js           # Python environment checker
├── src/openrouter_mcp/           # Python MCP server
│   ├── __init__.py
│   ├── client/                   # OpenRouter API client
│   │   ├── __init__.py
│   │   ├── openrouter.py        # Main client implementation
│   │   └── exceptions.py        # Custom exceptions
│   ├── handlers/                 # MCP tool handlers
│   │   ├── __init__.py
│   │   └── chat.py              # Chat completion handlers
│   └── server.py                # FastMCP server entry point
├── tests/                        # Test suite
│   ├── test_client/             # Client tests
│   │   ├── test_openrouter.py
│   │   └── fixtures/
│   ├── test_handlers/           # Handler tests
│   └── conftest.py              # pytest configuration
├── docs/                        # Documentation
│   ├── API.md                   # API reference
│   └── CLAUDE_DESKTOP_GUIDE.md  # Integration guide
├── requirements.txt             # Python dependencies
├── requirements-dev.txt         # Development dependencies
├── package.json                 # Node.js package configuration
├── pytest.ini                  # pytest configuration
├── .gitignore
├── .npmignore
├── README.md
└── CONTRIBUTING.md              # This file
```

### Key Components

#### Python Components

- **`src/openrouter_mcp/client/openrouter.py`**: Core OpenRouter API client
- **`src/openrouter_mcp/handlers/chat.py`**: MCP tool implementations
- **`src/openrouter_mcp/server.py`**: FastMCP server setup

#### Node.js Components

- **`bin/openrouter-mcp.js`**: CLI interface and process management
- **`bin/check-python.js`**: Environment validation
- **`package.json`**: NPM package configuration

#### Testing

- **`tests/test_client/`**: API client tests
- **`tests/test_handlers/`**: MCP handler tests
- **`tests/conftest.py`**: Shared test fixtures

## Development Workflow

### 1. Test-Driven Development (TDD)

This project follows TDD methodology:

1. **RED**: Write failing tests first
2. **GREEN**: Implement minimal code to pass tests
3. **REFACTOR**: Improve code while keeping tests green

Example workflow:

```bash
# 1. Write a failing test
# Edit tests/test_client/test_openrouter.py

# 2. Run tests to see it fail
npm run test

# 3. Implement minimal code to pass
# Edit src/openrouter_mcp/client/openrouter.py

# 4. Run tests until they pass
npm run test

# 5. Refactor and improve
# Keep running tests to ensure nothing breaks
```

### 2. Feature Development

For new features:

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Write tests first
# Implement feature
# Update documentation
# Test thoroughly

# Commit with conventional commits
git commit -m "feat: add support for custom headers"
```

### 3. Bug Fixes

For bug fixes:

```bash
# Create bugfix branch
git checkout -b fix/issue-description

# Write test that reproduces the bug
# Fix the bug
# Ensure test passes
# Update documentation if needed

# Commit fix
git commit -m "fix: resolve rate limiting issue"
```

## Testing

### Running Tests

```bash
# Run all tests
npm run test

# Run with coverage
npm run test:coverage

# Run specific test file
python -m pytest tests/test_client/test_openrouter.py -v

# Run specific test
python -m pytest tests/test_client/test_openrouter.py::TestOpenRouterClient::test_chat_completion -v
```

### Writing Tests

#### Test Structure

```python
import pytest
from unittest.mock import AsyncMock, patch
from openrouter_mcp.client.openrouter import OpenRouterClient

class TestNewFeature:
    """Test new feature functionality."""
    
    @pytest.mark.asyncio
    async def test_feature_success(self, mock_client):
        """Test successful feature execution."""
        # Arrange
        expected_result = {"success": True}
        
        # Act
        result = await mock_client.new_feature()
        
        # Assert
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_feature_error_handling(self, mock_client):
        """Test feature error handling."""
        # Arrange
        mock_client.session.post.side_effect = Exception("Test error")
        
        # Act & Assert
        with pytest.raises(OpenRouterError):
            await mock_client.new_feature()
```

#### Test Fixtures

Create reusable test fixtures in `conftest.py`:

```python
@pytest.fixture
async def mock_client():
    """Mock OpenRouter client for testing."""
    client = OpenRouterClient(api_key="test-key")
    with patch.object(client, 'session') as mock_session:
        mock_session.post = AsyncMock()
        yield client
```

### Integration Tests

For testing the full MCP integration:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_chat_completion_integration():
    """Test full MCP chat completion flow."""
    # This test requires a real API key
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("No API key available for integration test")
    
    # Test with real API
    request = ChatCompletionRequest(
        model="openai/gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    
    result = await chat_with_model(request)
    assert "choices" in result
```

## Code Style

### Python Code Style

We use:
- **Black** for code formatting
- **Ruff** for linting
- **Type hints** for all function signatures
- **Docstrings** for all public functions

#### Formatting and Linting

```bash
# Format code
npm run format

# Lint code
npm run lint

# Fix linting issues automatically
python -m ruff check src/ tests/ --fix
```

#### Style Guidelines

```python
# Good: Type hints and docstring
async def chat_completion(
    self,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Generate chat completion using OpenRouter API.
    
    Args:
        model: Model identifier (e.g., "openai/gpt-4")
        messages: List of conversation messages
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens to generate
        
    Returns:
        Dictionary containing the completion response
        
    Raises:
        OpenRouterError: If the API request fails
    """
    # Implementation here
```

### JavaScript Code Style

For Node.js CLI code:
- **Prettier** for formatting
- **ESLint** for linting
- **JSDoc** for documentation

```javascript
/**
 * Start the OpenRouter MCP server
 * @param {Object} options - Server configuration options
 * @param {string} options.host - Host to bind to
 * @param {number} options.port - Port to listen on
 * @returns {Promise<void>}
 */
async function startServer(options) {
  // Implementation here
}
```

### Commit Messages

Use [Conventional Commits](https://conventionalcommits.org/):

```bash
# Feature
git commit -m "feat: add streaming support for chat completions"

# Bug fix
git commit -m "fix: resolve timeout issue in client connection"

# Documentation
git commit -m "docs: update API reference with new parameters"

# Tests
git commit -m "test: add unit tests for error handling"

# Refactor
git commit -m "refactor: simplify client authentication logic"

# Breaking change
git commit -m "feat!: change API response format for consistency"
```

## Pull Request Process

### 1. Before Submitting

- [ ] Tests pass: `npm run test`
- [ ] Code is formatted: `npm run format`
- [ ] Code is linted: `npm run lint`
- [ ] Documentation is updated
- [ ] CHANGELOG entry added (if applicable)

### 2. Pull Request Template

Create a PR with this template:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## How Has This Been Tested?
- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
```

### 3. Review Process

1. **Automated checks** must pass (tests, linting, formatting)
2. **Manual review** by maintainers
3. **Address feedback** and update as needed
4. **Final approval** and merge

## Release Process

### Version Management

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Workflow

1. **Update version** in `package.json`
2. **Update CHANGELOG.md** with release notes
3. **Create release PR** with version bump
4. **Tag release** after merge
5. **Publish to NPM** (maintainers only)

```bash
# Example release process
git checkout main
git pull upstream main

# Update version
npm version minor  # or major/patch

# Update changelog
# Edit CHANGELOG.md

# Commit and push
git add .
git commit -m "chore: release v1.2.0"
git push upstream main

# Create tag
git tag v1.2.0
git push upstream v1.2.0
```

## Development Tips

### Debugging

#### Python Debugging

```python
import logging
import pdb

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Set breakpoint
pdb.set_trace()

# Or use breakpoint() in Python 3.7+
breakpoint()
```

#### Node.js Debugging

```bash
# Run with debugging
node --inspect-brk bin/openrouter-mcp.js start

# Or use built-in debugging
npm run start -- --debug
```

### Testing with Real API

For testing with real OpenRouter API:

```bash
# Set real API key
export OPENROUTER_API_KEY="your-real-key"

# Run integration tests
python -m pytest tests/ -m integration -v

# Test CLI manually
npm run start
```

### Performance Profiling

```python
import cProfile
import pstats

# Profile function
def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Your code here
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('tottime')
    stats.print_stats()
```

## Architecture Guidelines

### Adding New MCP Tools

1. **Define Pydantic models** for request/response
2. **Write comprehensive tests** first
3. **Implement tool handler** in `handlers/`
4. **Add error handling** and logging
5. **Update documentation**

Example new tool:

```python
# In handlers/new_tool.py
from pydantic import BaseModel, Field
from fastmcp import FastMCP

class NewToolRequest(BaseModel):
    """Request for new tool."""
    parameter: str = Field(..., description="Tool parameter")

@mcp.tool()
async def new_tool(request: NewToolRequest) -> Dict[str, Any]:
    """
    Description of what the tool does.
    
    Args:
        request: Tool request parameters
        
    Returns:
        Tool response data
        
    Raises:
        OpenRouterError: If the operation fails
    """
    # Implementation
    pass
```

### Error Handling Patterns

```python
from openrouter_mcp.client.exceptions import (
    OpenRouterError,
    AuthenticationError,
    RateLimitError
)

try:
    result = await client.api_call()
except AuthenticationError:
    logger.error("Authentication failed")
    raise
except RateLimitError as e:
    logger.warning(f"Rate limited, retry after {e.retry_after}s")
    raise
except OpenRouterError as e:
    logger.error(f"API error: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise OpenRouterError(f"Unexpected error: {e}")
```

## Getting Help

### Documentation

- [API Documentation](docs/API.md)
- [Claude Desktop Guide](docs/CLAUDE_DESKTOP_GUIDE.md)
- [Main README](README.md)

### Community

- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Ask questions and share ideas
- **Pull Requests**: Contribute code and documentation

### Maintainer Contact

For security issues or urgent matters, contact maintainers directly through GitHub.

---

Thank you for contributing to OpenRouter MCP Server! Your contributions help make AI models more accessible to everyone.