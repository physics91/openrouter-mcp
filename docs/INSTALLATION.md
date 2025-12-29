# Installation Guide

Comprehensive installation instructions for the OpenRouter MCP Server across different platforms and configurations.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Install](#quick-install)
- [Platform-Specific Installation](#platform-specific-installation)
- [Configuration](#configuration)
- [Verification](#verification)
- [Upgrading](#upgrading)
- [Uninstallation](#uninstallation)

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Node.js** | 16.0.0 | 18.0.0+ |
| **Python** | 3.9.0 | 3.11.0+ |
| **RAM** | 2GB | 4GB+ |
| **Storage** | 500MB | 1GB+ |
| **OS** | Windows 10, macOS 10.15, Ubuntu 20.04 | Latest versions |

### Required Software

#### 1. Node.js Installation

**Windows:**
```powershell
# Download from nodejs.org
# Or use Chocolatey
choco install nodejs

# Verify installation
node --version
npm --version
```

**macOS:**
```bash
# Using Homebrew
brew install node

# Or download from nodejs.org
# Verify installation
node --version
npm --version
```

**Linux (Ubuntu/Debian):**
```bash
# Using NodeSource repository
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify installation
node --version
npm --version
```

#### 2. Python Installation

**Windows:**
```powershell
# Download from python.org (check "Add to PATH")
# Or use Chocolatey
choco install python

# Verify installation
python --version
pip --version
```

**macOS:**
```bash
# Using Homebrew
brew install python@3.11

# Verify installation
python3 --version
pip3 --version
```

**Linux (Ubuntu/Debian):**
```bash
# Install Python and pip
sudo apt update
sudo apt install python3.11 python3-pip

# Verify installation
python3 --version
pip3 --version
```

## Quick Install

### One-Line Installation

```bash
# Using npx (no installation needed)
npx openrouter-mcp init && npx openrouter-mcp start

# Or install globally
npm install -g openrouter-mcp
openrouter-mcp init
openrouter-mcp start
```

## Platform-Specific Installation

### Windows Installation

#### Step 1: Install Prerequisites
```powershell
# Open PowerShell as Administrator

# Install Chocolatey (if not installed)
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install Node.js and Python
choco install nodejs python

# Restart PowerShell
```

#### Step 2: Install OpenRouter MCP
```powershell
# Install globally
npm install -g openrouter-mcp

# Or use npx (recommended)
npx openrouter-mcp init
```

#### Step 3: Configure Environment
```powershell
# Create configuration
openrouter-mcp init

# Enter your API key when prompted
# Configure Claude Desktop integration (optional)
```

### macOS Installation

#### Step 1: Install Prerequisites
```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Node.js and Python
brew install node python@3.11

# Add Python to PATH (if needed)
echo 'export PATH="/usr/local/opt/python@3.11/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

#### Step 2: Install OpenRouter MCP
```bash
# Install globally
npm install -g openrouter-mcp

# Or use npx (recommended)
npx openrouter-mcp init
```

#### Step 3: Configure Environment
```bash
# Initialize configuration
openrouter-mcp init

# Follow prompts for API key and integration setup
```

### Linux Installation

#### Step 1: Install Prerequisites
```bash
# Update package manager
sudo apt update && sudo apt upgrade -y

# Install curl and build essentials
sudo apt install curl build-essential -y

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y

# Install Python
sudo apt install python3.11 python3-pip python3-venv -y

# Create Python alias (optional)
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1
```

#### Step 2: Install OpenRouter MCP
```bash
# Install globally (may need sudo)
sudo npm install -g openrouter-mcp

# Or use npx (recommended)
npx openrouter-mcp init
```

#### Step 3: Configure Environment
```bash
# Initialize configuration
openrouter-mcp init

# Set up environment variables
export OPENROUTER_API_KEY="your-key-here"
```

### Docker Installation

```dockerfile
# Dockerfile
FROM node:18-python3.11

WORKDIR /app

# Install OpenRouter MCP
RUN npm install -g openrouter-mcp

# Copy configuration
COPY .env .env

# Expose port
EXPOSE 8000

# Start server
CMD ["openrouter-mcp", "start"]
```

Build and run:
```bash
docker build -t openrouter-mcp .
docker run -p 8000:8000 --env-file .env openrouter-mcp
```

## Configuration

### Basic Configuration

#### 1. Initialize Configuration
```bash
npx openrouter-mcp init
```

This will prompt you for:
- OpenRouter API key
- Server port (default: 8000)
- Claude Desktop integration
- Claude Code CLI integration

#### 2. Manual Configuration

Create `.env` file in your project directory:

```env
# Required
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Optional Server Configuration
HOST=localhost
PORT=8000
LOG_LEVEL=info

# Optional API Configuration
OPENROUTER_APP_NAME=my-app
OPENROUTER_HTTP_REFERER=https://myapp.com
```

Cache tuning (TTL, memory size, cache file path) is configured programmatically
via `ModelCache` and `OpenRouterClient` rather than environment variables.

### Claude Desktop Integration

#### Automatic Setup
```bash
npx openrouter-mcp install-claude
```

#### Manual Setup

**macOS:**
```bash
# Edit configuration file
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows:**
```powershell
# Edit configuration file
notepad %APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```bash
# Edit configuration file
nano ~/.config/claude/claude_desktop_config.json
```

Add configuration:
```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Claude Code CLI Integration

#### Automatic Setup
```bash
npx openrouter-mcp install-claude-code
```

#### Manual Setup
```bash
# Edit configuration file
nano ~/.claude/claude_code_config.json
```

Add configuration:
```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

## Verification

### 1. Check Installation
```bash
# Check CLI installation
npx openrouter-mcp --version

# Check Python dependencies
python -c "import fastmcp; print('FastMCP installed')"

# Check server status
npx openrouter-mcp status
```

### 2. Test Server
```bash
# Start server in verbose mode
npx openrouter-mcp start --verbose

# In another terminal, test API
curl http://localhost:8000/health
```

### 3. Test API Connection
```bash
# Test OpenRouter API
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
     https://openrouter.ai/api/v1/models | head -20
```

### 4. Run Diagnostic
```bash
# Full system diagnostic
npx openrouter-mcp diagnose

# This checks:
# - Node.js version
# - Python version and packages
# - API key validity
# - Network connectivity
# - File permissions
```

## Upgrading

### Upgrade to Latest Version

#### Global Installation
```bash
# Update global package
npm update -g openrouter-mcp

# Verify version
openrouter-mcp --version
```

#### npx Users
```bash
# Clear npm cache
npm cache clean --force

# Use latest version
npx openrouter-mcp@latest start
```

### Migrate Configuration

When upgrading major versions:

```bash
# Backup current configuration
cp .env .env.backup
cp .cache/openrouter_model_cache.json cache.backup.json

# Run migration
npx openrouter-mcp migrate

# Verify configuration
npx openrouter-mcp status
```

## Uninstallation

### Complete Removal

#### 1. Uninstall Package
```bash
# Global installation
npm uninstall -g openrouter-mcp

# Local installation
npm uninstall openrouter-mcp
```

#### 2. Remove Configuration Files
```bash
# Remove environment file
rm .env

# Remove cache
rm .cache/openrouter_model_cache.json

# Remove logs
rm -rf logs/
```

#### 3. Remove Claude Integration

**Claude Desktop:**
- Edit `claude_desktop_config.json`
- Remove the `openrouter` entry from `mcpServers`

**Claude Code:**
- Edit `claude_code_config.json`
- Remove the `openrouter` entry from `mcpServers`

#### 4. Clean Python Dependencies (Optional)
```bash
# If using virtual environment
deactivate
rm -rf venv/

# Or uninstall packages
pip uninstall fastmcp httpx pillow
```

## Troubleshooting Installation

### Common Issues

#### Node.js Version Too Old
```bash
# Update Node.js
nvm install 18
nvm use 18
```

#### Python Not Found
```bash
# Add Python to PATH
# Windows: Re-run Python installer and check "Add to PATH"
# macOS/Linux: Add to shell profile
echo 'export PATH="/usr/local/bin/python3:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### Permission Denied
```bash
# Use sudo on Unix systems
sudo npm install -g openrouter-mcp

# Or use npx to avoid global install
npx openrouter-mcp start
```

#### SSL Certificate Issues
```bash
# Temporary fix (not recommended for production)
export NODE_TLS_REJECT_UNAUTHORIZED=0

# Better solution: Update certificates
npm config set strict-ssl false
```

### Getting Help

If you encounter issues:
1. Check [Troubleshooting Guide](TROUBLESHOOTING.md)
2. Run diagnostic: `npx openrouter-mcp diagnose`
3. Check [GitHub Issues](https://github.com/your-repo/issues)
4. Join community Discord

## Next Steps

After installation:
- [API Reference](API.md) - Learn about available MCP tools
- [Benchmarking Guide](BENCHMARK_GUIDE.md) - Compare model performance
- [FAQ](FAQ.md) - Common questions and answers
- [Claude Desktop Guide](CLAUDE_DESKTOP_GUIDE.md) - Desktop integration
- [Claude Code Guide](CLAUDE_CODE_GUIDE.md) - Terminal workflow

For a complete documentation overview, see the [Documentation Index](INDEX.md).

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0
