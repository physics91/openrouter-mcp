# OpenRouter MCP Server

🚀 A powerful Model Context Protocol (MCP) server that provides seamless access to multiple AI models through OpenRouter's unified API.

[![NPM Version](https://img.shields.io/npm/v/openrouter-mcp.svg)](https://www.npmjs.com/package/openrouter-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)

## ✨ Features

- 🤖 **Multi-Model Access**: Chat with GPT-4o, Claude 3.5, Llama 3.3, Gemini 2.5, and 200+ other AI models
- 🖼️ **Vision/Multimodal Support**: Analyze images and visual content with vision-capable models
  - Support for base64-encoded images and image URLs
  - Automatic image resizing and optimization for API limits
  - Compatible with GPT-4o, Claude 3.5, Gemini 2.5, Llama Vision, and more
- 🚀 **Latest Models (Jan 2025)**: Always up-to-date with the newest models
  - OpenAI o1, GPT-4o, GPT-4 Turbo
  - Claude 3.5 Sonnet, Claude 3 Opus
  - Gemini 2.5 Pro/Flash (1M+ context)
  - DeepSeek V3, Grok 2, and more
- ⚡ **Intelligent Caching**: Smart model list caching for improved performance
  - In-memory and persistent file caching
  - Configurable TTL with automatic refresh
  - Enhanced model metadata and categorization
- 🔄 **Streaming Support**: Real-time response streaming for better user experience
- 📊 **Usage Tracking**: Monitor API usage, costs, and token consumption
- 🛡️ **Error Handling**: Robust error handling with detailed logging
- 🔧 **Easy Setup**: One-command installation with `npx`
- 🖥️ **Claude Desktop Integration**: Seamless integration with Claude Desktop app
- 📚 **Full MCP Compliance**: Implements Model Context Protocol standards

## 🚀 Quick Start

### Option 1: Using npx (Recommended)

```bash
# Initialize configuration
npx openrouter-mcp init

# Start the server
npx openrouter-mcp start
```

### Option 2: Global Installation

```bash
# Install globally
npm install -g openrouter-mcp

# Initialize and start
openrouter-mcp init
openrouter-mcp start
```

## 📋 Prerequisites

- **Node.js 16+**: Required for CLI interface
- **Python 3.9+**: Required for the MCP server backend
- **OpenRouter API Key**: Get one free at [openrouter.ai](https://openrouter.ai)

## 🛠️ Installation & Configuration

### 1. Get Your OpenRouter API Key

1. Visit [OpenRouter](https://openrouter.ai)
2. Sign up for a free account
3. Navigate to the API Keys section
4. Create a new API key

### 2. Initialize the Server

```bash
npx openrouter-mcp init
```

This will:
- Prompt you for your OpenRouter API key
- Create a `.env` configuration file
- Optionally set up Claude Desktop integration

### 3. Start the Server

```bash
npx openrouter-mcp start
```

The server will start on `localhost:8000` by default.

## 🎯 Usage

### Available Commands

```bash
# Show help
npx openrouter-mcp --help

# Initialize configuration
npx openrouter-mcp init

# Start the server
npx openrouter-mcp start [options]

# Check server status
npx openrouter-mcp status

# Configure Claude Desktop integration
npx openrouter-mcp install-claude

# Configure Claude Code CLI integration
npx openrouter-mcp install-claude-code
```

### Start Server Options

```bash
# Custom port and host
npx openrouter-mcp start --port 9000 --host 0.0.0.0

# Enable verbose logging
npx openrouter-mcp start --verbose

# Enable debug mode
npx openrouter-mcp start --debug
```

## 🤖 Claude Desktop Integration

### Automatic Setup

```bash
npx openrouter-mcp install-claude
```

This automatically configures Claude Desktop to use OpenRouter models.

### Manual Setup

Add to your Claude Desktop config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`
**Linux**: `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "your-openrouter-api-key"
      }
    }
  }
}
```

Then restart Claude Desktop.

## 💻 Claude Code CLI Integration

### Automatic Setup

```bash
npx openrouter-mcp install-claude-code
```

This automatically configures Claude Code CLI to use OpenRouter models.

### Manual Setup

Add to your Claude Code CLI config file at `~/.claude/claude_code_config.json`:

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "your-openrouter-api-key"
      }
    }
  }
}
```

### Usage with Claude Code CLI

Once configured, you can use OpenRouter models directly in your terminal:

```bash
# Chat with different AI models
claude-code "Use GPT-4 to explain this complex algorithm"
claude-code "Have Claude Opus review my Python code"
claude-code "Ask Llama 2 to suggest optimizations"

# Model discovery and comparison
claude-code "List all available AI models and their pricing"
claude-code "Compare GPT-4 and Claude Sonnet for code generation"

# Usage tracking
claude-code "Show my OpenRouter API usage for today"
claude-code "Which AI models am I using most frequently?"
```

For detailed setup instructions, see [Claude Code CLI Integration Guide](docs/CLAUDE_CODE_GUIDE.md).

## 🛠️ Available MCP Tools

Once integrated with Claude Desktop or Claude Code CLI, you'll have access to these tools:

### 1. `chat_with_model`
Chat with any available AI model.

**Parameters:**
- `model`: Model ID (e.g., "openai/gpt-4o", "anthropic/claude-3.5-sonnet")
- `messages`: Conversation history
- `temperature`: Creativity level (0.0-2.0)
- `max_tokens`: Maximum response length
- `stream`: Enable streaming responses

**Example:**
```json
{
  "model": "openai/gpt-4o",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain quantum computing"}
  ],
  "temperature": 0.7
}
```

### 2. `list_available_models`
Get information about all available models.

**Parameters:**
- `filter_by`: Optional filter by model name

**Returns:**
- Model IDs, names, descriptions
- Pricing information
- Context window sizes
- Capabilities

### 3. `get_usage_stats`
Track your API usage and costs.

**Parameters:**
- `start_date`: Start date (YYYY-MM-DD)
- `end_date`: End date (YYYY-MM-DD)

**Returns:**
- Total costs and token usage
- Request counts
- Model-specific breakdowns

### 4. `chat_with_vision` 🖼️
Chat with vision-capable models by sending images.

**Parameters:**
- `model`: Vision-capable model ID (e.g., "openai/gpt-4o", "anthropic/claude-3-opus", "google/gemini-pro-vision")
- `messages`: Conversation history (supports both text and image content)
- `images`: List of images (file paths, URLs, or base64 strings)
- `temperature`: Creativity level (0.0-2.0)
- `max_tokens`: Maximum response length

**Image Format Support:**
- **File paths**: `/path/to/image.jpg`, `./image.png`
- **URLs**: `https://example.com/image.jpg`
- **Base64**: Direct base64 strings (with or without data URI prefix)

**Example - Multiple Images:**
```json
{
  "model": "openai/gpt-4o",
  "messages": [
    {"role": "user", "content": "Compare these images and describe the differences"}
  ],
  "images": [
    {"data": "/home/user/image1.jpg", "type": "path"},
    {"data": "https://example.com/image2.png", "type": "url"},
    {"data": "data:image/jpeg;base64,/9j/4AAQ...", "type": "base64"}
  ]
}
```

**Features:**
- Automatic image format detection and conversion
- Image resizing for API size limits (20MB max)
- Support for JPEG, PNG, GIF, and WebP formats
- Batch processing of multiple images

### 5. `list_vision_models` 🖼️
Get all vision-capable models.

**Parameters:** None

**Returns:**
- List of models that support image analysis
- Model capabilities and pricing information
- Context window sizes for multimodal content

**Example Vision Models:**
- `openai/gpt-4o`: OpenAI's latest multimodal model
- `openai/gpt-4o-mini`: Fast and cost-effective vision model
- `anthropic/claude-3-opus`: Most capable Claude vision model
- `anthropic/claude-3-sonnet`: Balanced Claude vision model
- `google/gemini-pro-vision`: Google's multimodal AI
- `meta-llama/llama-3.2-90b-vision-instruct`: Meta's vision-capable Llama model

## 🔧 Configuration

### Environment Variables

Create a `.env` file in your project directory:

```env
# OpenRouter API Configuration
OPENROUTER_API_KEY=placeholder-here
OPENROUTER_APP_NAME=openrouter-mcp
OPENROUTER_HTTP_REFERER=https://localhost

# Server Configuration
HOST=localhost
PORT=8000
LOG_LEVEL=info
```

### Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key | Required |
| `OPENROUTER_APP_NAME` | App identifier for tracking | "openrouter-mcp" |
| `OPENROUTER_HTTP_REFERER` | HTTP referer header | "https://localhost" |
| `HOST` | Server bind address | "localhost" |
| `PORT` | Server port | "8000" |
| `LOG_LEVEL` | Logging level | "info" |

## 📊 Popular Models

Here are some popular models available through OpenRouter:

### OpenAI Models
- `openai/gpt-4o`: Most capable multimodal GPT-4 model (text + vision)
- `openai/gpt-4o-mini`: Fast and cost-effective with vision support
- `openai/gpt-4`: Most capable text-only GPT-4 model
- `openai/gpt-3.5-turbo`: Fast and cost-effective text model

### Anthropic Models
- `anthropic/claude-3-opus`: Most capable Claude model (text + vision)
- `anthropic/claude-3-sonnet`: Balanced capability and speed (text + vision)
- `anthropic/claude-3-haiku`: Fast and efficient (text + vision)

### Open Source Models
- `meta-llama/llama-3.2-90b-vision-instruct`: Meta's flagship vision model
- `meta-llama/llama-3.2-11b-vision-instruct`: Smaller vision-capable Llama
- `meta-llama/llama-2-70b-chat`: Meta's text-only flagship model
- `mistralai/mixtral-8x7b-instruct`: Efficient mixture of experts
- `microsoft/wizardlm-2-8x22b`: High-quality instruction following

### Specialized Models
- `google/gemini-pro-vision`: Google's multimodal AI (text + vision)
- `google/gemini-pro`: Google's text-only model
- `cohere/command-r-plus`: Great for RAG applications
- `perplexity/llama-3-sonar-large-32k-online`: Web-connected model

Use `list_available_models` to see all available models and their pricing.

## 🐛 Troubleshooting

### Common Issues

**1. Python not found**
```bash
# Check Python installation
python --version

# If not installed, download from python.org
# Make sure Python is in your PATH
```

**2. Missing Python dependencies**
```bash
# Install manually if needed
pip install -r requirements.txt

# For multimodal/vision features
pip install Pillow>=10.0.0
```

**3. API key not configured**
```bash
# Re-run initialization
npx openrouter-mcp init
```

**4. Port already in use**
```bash
# Use a different port
npx openrouter-mcp start --port 9000
```

**5. Claude Desktop not detecting server**
- Restart Claude Desktop after configuration
- Check config file path and format
- Verify API key is correct

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
npx openrouter-mcp start --debug
```

### Status Check

Check server configuration and status:

```bash
npx openrouter-mcp status
```

## 🧪 Development

### Running Tests

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
npm run test

# Run tests with coverage
npm run test:coverage

# Lint code
npm run lint

# Format code
npm run format
```

### Project Structure

```
openrouter-mcp/
├── bin/                    # CLI scripts
│   ├── openrouter-mcp.js  # Main CLI entry point
│   └── check-python.js    # Python environment checker
├── src/openrouter_mcp/    # Python MCP server
│   ├── client/            # OpenRouter API client
│   │   └── openrouter.py  # Main API client with vision support
│   ├── handlers/          # MCP tool handlers
│   │   ├── chat.py        # Text-only chat handlers
│   │   └── multimodal.py  # Vision/multimodal handlers
│   └── server.py          # Main server entry point
├── tests/                 # Test suite
│   ├── test_chat.py       # Chat functionality tests
│   └── test_multimodal.py # Multimodal functionality tests
├── examples/              # Usage examples
│   └── multimodal_example.py # Multimodal usage examples
├── docs/                  # Documentation
├── requirements.txt       # Python dependencies (includes Pillow)
└── package.json          # Node.js package config
```

## 📚 Documentation

- [API Documentation](docs/API.md) - Detailed API reference
- [Multimodal/Vision Guide](docs/MULTIMODAL_GUIDE.md) - Complete vision capabilities guide
- [Claude Desktop Integration](docs/CLAUDE_DESKTOP_GUIDE.md) - Complete Desktop setup guide
- [Claude Code CLI Integration](docs/CLAUDE_CODE_GUIDE.md) - Terminal workflow integration
- [Contributing Guide](CONTRIBUTING.md) - Development guidelines
- [OpenRouter API Docs](https://openrouter.ai/docs) - Official OpenRouter documentation
- [MCP Specification](https://modelcontextprotocol.io) - Model Context Protocol standard

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- [OpenRouter](https://openrouter.ai) - Get your API key
- [Claude Desktop](https://claude.ai/desktop) - Download Claude Desktop app
- [Model Context Protocol](https://modelcontextprotocol.io) - Learn about MCP
- [FastMCP](https://github.com/jlowin/fastmcp) - The MCP framework we use

## 🙏 Acknowledgments

- [OpenRouter](https://openrouter.ai) for providing access to multiple AI models
- [FastMCP](https://github.com/jlowin/fastmcp) for the excellent MCP framework
- [Anthropic](https://anthropic.com) for the Model Context Protocol specification

---

**Made with ❤️ for the AI community**

Need help? Open an issue or check our documentation!