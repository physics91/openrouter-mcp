# System Architecture Overview

This document describes the technical architecture of the OpenRouter MCP Server, designed with TDD principles and modular components.

## Table of Contents
- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)
- [Design Patterns](#design-patterns)
- [Security Considerations](#security-considerations)

## System Overview

The OpenRouter MCP Server is a hybrid Node.js/Python application that implements the Model Context Protocol (MCP) to provide unified access to 200+ AI models through OpenRouter's API.

```
┌─────────────────────────────────────────────────┐
│                  Client Layer                    │
│  (Claude Desktop / Claude Code CLI / Custom)     │
└─────────────────┬───────────────────────────────┘
                  │ MCP Protocol
┌─────────────────▼───────────────────────────────┐
│              MCP Server Layer                    │
│            (FastMCP Framework)                   │
├──────────────────────────────────────────────────┤
│                Tool Handlers                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │   Chat   │ │Multimodal│ │Benchmark │        │
│  └──────────┘ └──────────┘ └──────────┘        │
├──────────────────────────────────────────────────┤
│              Service Layer                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │  Client  │ │  Cache   │ │ Metadata │        │
│  └──────────┘ └──────────┘ └──────────┘        │
├──────────────────────────────────────────────────┤
│            OpenRouter API Layer                  │
│         (External API Integration)               │
└──────────────────────────────────────────────────┘
```

## Component Architecture

### 1. CLI Interface (Node.js)
**Location**: `bin/`
- **openrouter-mcp.js**: Main CLI entry point
- **check-python.js**: Python environment validator

**Responsibilities**:
- User interaction and configuration
- Python server process management
- Claude Desktop/Code integration setup

### 2. MCP Server Core (Python)
**Location**: `src/openrouter_mcp/`
- **server.py**: FastMCP server initialization and tool registration

**Key Features**:
- Asynchronous request handling
- Tool registration and dispatch
- Error handling and logging

### 3. Tool Handlers
**Location**: `src/openrouter_mcp/handlers/`

#### Chat Handler (`chat.py`)
- Text-based chat completions
- Streaming response support
- Token usage tracking

#### Multimodal Handler (`multimodal.py`)
- Image processing with Pillow
- Base64 encoding/decoding
- Vision model selection

#### Benchmark Handler (`benchmark.py`)
- Parallel model execution
- Performance metric collection
- Report generation (MD/CSV/JSON)

### 4. Client Layer
**Location**: `src/openrouter_mcp/client/`
- **openrouter.py**: OpenRouter API client implementation

**Features**:
- HTTP/HTTPS request handling
- Rate limiting and retry logic
- Response parsing and validation

### 5. Models & Cache
**Location**: `src/openrouter_mcp/models/`
- **cache.py**: Dual-layer caching system

**Cache Architecture**:
```python
Memory Cache (LRU)
    ├── Model List
    ├── Model Metadata
    └── Recent Responses

File Cache (JSON)
    ├── openrouter_model_cache.json
    └── Timestamped entries
```

### 6. Configuration
**Location**: `src/openrouter_mcp/config/`
- **providers.json**: Provider metadata and categories
- **providers.py**: Configuration loader

## Data Flow

### Request Flow
```
1. Client Request → MCP Server
2. MCP Server → Tool Handler Selection
3. Tool Handler → Parameter Validation
4. Cache Check → Hit/Miss Decision
5. If Miss → OpenRouter API Call
6. Response Processing → Cache Update
7. Format Response → Client
```

### Benchmark Flow
```
1. Receive Benchmark Request
2. Parse Model List & Parameters
3. Initialize Benchmark Session
4. Parallel Execution:
   ├── Model 1 → Multiple Runs
   ├── Model 2 → Multiple Runs
   └── Model N → Multiple Runs
5. Collect Metrics
6. Generate Rankings
7. Create Reports (MD/CSV/JSON)
8. Return Results
```

## Technology Stack

### Core Technologies
- **Python 3.9+**: Server implementation
- **Node.js 16+**: CLI and package management
- **FastMCP**: MCP framework
- **httpx**: Async HTTP client
- **Pillow**: Image processing

### Development Stack
- **pytest**: Test framework (TDD)
- **ESLint**: JavaScript linting
- **Black**: Python code formatting
- **mypy**: Type checking

### Dependencies
```
Production:
├── fastmcp>=0.1.0
├── httpx>=0.24.0
├── Pillow>=10.0.0
├── python-dotenv>=1.0.0
└── pydantic>=2.0.0

Development:
├── pytest>=7.0.0
├── pytest-asyncio>=0.21.0
├── pytest-cov>=4.0.0
└── black>=23.0.0
```

## Design Patterns

### 1. Strategy Pattern
Used for different handler implementations:
```python
class BaseHandler(ABC):
    @abstractmethod
    async def handle(self, params): pass

class ChatHandler(BaseHandler):
    async def handle(self, params): ...

class MultimodalHandler(BaseHandler):
    async def handle(self, params): ...
```

### 2. Singleton Pattern
Cache manager implementation:
```python
class CacheManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

### 3. Factory Pattern
Model metadata creation:
```python
class ModelMetadataFactory:
    @staticmethod
    def create(model_id: str) -> ModelMetadata:
        # Enhanced metadata generation
        return ModelMetadata(...)
```

### 4. Observer Pattern
Benchmark progress tracking:
```python
class BenchmarkObserver:
    def update(self, event: BenchmarkEvent):
        # Handle progress updates
```

## Security Considerations

### API Key Management
- Environment variable storage
- No hardcoded credentials
- Secure transmission over HTTPS

### Input Validation
- Parameter type checking with Pydantic
- Size limits for image uploads
- Prompt injection prevention

### Rate Limiting
- Request throttling
- Exponential backoff
- Circuit breaker pattern

### Error Handling
- Sanitized error messages
- No sensitive data in logs
- Graceful degradation

## Performance Optimizations

### Caching Strategy
- Memory cache for frequent requests
- File cache for model metadata
- TTL-based invalidation
- LRU eviction policy

### Async Processing
- Non-blocking I/O operations
- Concurrent request handling
- Stream processing for large responses

### Resource Management
- Connection pooling
- Memory usage monitoring
- Automatic cleanup

## Testing Architecture

### Test Structure
```
tests/
├── unit/           # Isolated component tests
├── integration/    # Component interaction tests
├── e2e/           # End-to-end scenarios
└── fixtures/      # Test data and mocks
```

### TDD Workflow
1. Write failing test
2. Implement minimal code
3. Refactor with confidence
4. Maintain >80% coverage

## Deployment Architecture

### Local Development
```bash
python -m venv venv
pip install -r requirements-dev.txt
npm install
npm run dev
```

### Production Deployment
```bash
npm install -g openrouter-mcp
openrouter-mcp init
openrouter-mcp start --production
```

## Future Considerations

### Scalability
- Horizontal scaling with load balancing
- Distributed caching with Redis
- Queue-based job processing

### Monitoring
- Performance metrics collection
- Error tracking integration
- Usage analytics

### Extensions
- Plugin system for custom handlers
- WebSocket support for real-time updates
- GraphQL API layer

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0