# OpenRouter MCP - Quick Start Guide

> Get started in 5 minutes with the most secure and performant OpenRouter MCP server

## 🚀 3-Step Quick Start

### Step 1: Install & Initialize

```bash
# Install globally
npm install -g @physics91/openrouter-mcp

# Or use npx directly (no installation needed)
npx @physics91/openrouter-mcp init
```

When prompted:
- Enter your OpenRouter API key (get one at [openrouter.ai](https://openrouter.ai))
- Optionally configure Claude Desktop integration
- API key is securely stored in OS Keychain 🔐

### Step 2: Start the Server

```bash
npx openrouter-mcp start
```

You should see:
```
✓ API key loaded from os-keychain (sk-o...***MASKED***)
✓ Server running on http://localhost:8000
✓ MCP tools registered: 15
```

### Step 3: Connect from Claude Desktop

```bash
# Auto-configure Claude Desktop
npx openrouter-mcp install-claude

# Then restart Claude Desktop
```

**Done!** You can now use OpenRouter models in Claude Desktop.

---

## 💡 Try These Commands

### In Claude Desktop

```
"List all available AI models from OpenRouter"
"Use GPT-4 to explain quantum computing"
"Compare responses from Claude and GPT-4" (uses Collective Intelligence!)
"Analyze this image with GPT-4 Vision" (attach an image)
```

### In Claude Code CLI

**Setup** (3 minutes):

```bash
# 1. Create config file
mkdir -p ~/.claude

# 2. Add configuration (copy-paste this)
cat > ~/.claude/claude_code_config.json << 'EOF'
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-your-key-here"
      }
    }
  }
}
EOF

# 3. Edit and replace 'sk-or-v1-your-key-here' with your actual key
nano ~/.claude/claude_code_config.json

# 4. Set permissions
chmod 600 ~/.claude/claude_code_config.json
```

**Use**:
```bash
claude "Use GPT-4 to analyze this Python code"
claude "Use Claude Opus to write documentation"
claude "List all available models"
```

---

## 🎯 Key Features at a Glance

### 🔐 Security (NEW!)

- **Secure Credentials**: API keys stored in OS Keychain (macOS), Credential Manager (Windows), or encrypted files
- **Log Sanitization**: API keys masked, prompts hashed, PII protected
- **No Path Traversal**: Multimodal inputs secured (base64/URL only)

```bash
# Check security status
npx openrouter-mcp status

# Rotate API key (recommended every 90 days)
npx openrouter-mcp rotate-key

# Security audit
npx openrouter-mcp security-audit
```

### ⚡ Performance (NEW!)

- **95% faster** subsequent requests (singleton client)
- **Zero cache corruption** (file locking)
- **Smart caching** (2-hour default TTL, configurable)

```bash
# Custom cache settings
export CACHE_TTL_HOURS=6
export CACHE_MAX_ITEMS=5000
npx openrouter-mcp start
```

### 🧠 Collective Intelligence (NEW!)

Get consensus from multiple AI models:

```
"Use consensus from 3 models to answer: What is the future of AI?"
"Validate this answer using cross-model verification"
"Solve this complex problem collaboratively with multiple AI models"
```

**5 Tools Available**:
1. `collective_chat_completion` - Multi-model consensus
2. `ensemble_reasoning` - Break down complex problems
3. `adaptive_model_selection` - Auto-select best model
4. `cross_model_validation` - Verify answers across models
5. `collaborative_problem_solving` - Iterative multi-model refinement

### 🖼️ Multimodal (Secured!)

Vision-capable models (GPT-4 Vision, Claude 3, Gemini):

```
"Analyze this chart" (with image)
"Describe this architecture diagram"
"Extract text from this screenshot"
```

**Security Note**: File path inputs removed for security. Use base64 or URLs only.

---

## 📊 Available Models

```bash
# List all models
claude "List all AI models"

# Filter by capability
claude "Show me vision-capable models"

# Check pricing
claude "Compare costs of GPT-4 vs Claude Opus"
```

Popular models:
- `openai/gpt-4-turbo`
- `openai/gpt-4-vision-preview`
- `anthropic/claude-3-opus`
- `anthropic/claude-3-sonnet`
- `google/gemini-pro`
- `google/gemini-pro-vision`
- `meta-llama/llama-3-70b`

---

## ⚙️ Configuration

### Environment Variables

Create `.env` file:

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-...

# Optional
OPENROUTER_APP_NAME=MyApp
OPENROUTER_HTTP_REFERER=https://myapp.com
HOST=localhost
PORT=8000
LOG_LEVEL=INFO

# Cache settings
CACHE_TTL_HOURS=2
CACHE_MAX_ITEMS=1000

# Logging (⚠️ verbose only for development!)
# OPENROUTER_VERBOSE_LOGGING=false
```

### Claude Desktop Config

Auto-configure:
```bash
npx openrouter-mcp install-claude
```

Or manually edit config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

Add:
```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"]
    }
  }
}
```

---

## 🔄 Migration from Old Setup

### If you have existing `.env` file:

**Good news**: It still works! But we recommend migrating to secure storage:

```bash
# 1. Migrate encryption (if using encrypted storage)
npx openrouter-mcp migrate-encryption

# 2. Verify
npx openrouter-mcp security-audit

# 3. Start normally
npx openrouter-mcp start

# Now your key is in OS Keychain ✓
```

### If you have multimodal code with file paths:

**Update required** (security fix):

**Before** (❌ vulnerable):
```python
from openrouter_mcp.handlers.multimodal import ImageInput

img = ImageInput(data="/path/image.jpg", type="path")  # Won't work
```

**After** (✅ secure):
```python
from openrouter_mcp.handlers.multimodal import (
    ImageInput,
    encode_image_to_base64
)

with open("/path/image.jpg", "rb") as f:
    img_bytes = f.read()

img = ImageInput(
    data=encode_image_to_base64(img_bytes),
    type="base64"
)
```

---

## 🛠️ Troubleshooting

### Server won't start

```bash
# Check Python
python --version  # Need 3.9+

# Check logs
npx openrouter-mcp start --debug

# Reset everything
npx openrouter-mcp init
```

### Claude Desktop can't find server

```bash
# Reinstall
npx openrouter-mcp install-claude

# Restart Claude Desktop completely (Quit → Relaunch)

# Check config file exists and is valid JSON
```

### API key errors

```bash
# Check status
npx openrouter-mcp status

# Re-initialize
npx openrouter-mcp init
```

### Cache corruption (if using old version)

```bash
# Delete cache
rm openrouter_model_cache.json

# Restart
npx openrouter-mcp start

# Note: New version has file locking, corruption won't happen
```

---

## 📚 Next Steps

### Learn More

- **Full Guide**: `docs/USAGE_GUIDE_KR.md` (Korean)
- **Security Details**: `docs/SECURITY.md`
- **Collective Intelligence**: `docs/COLLECTIVE_INTELLIGENCE_INTEGRATION.md`
- **Performance**: `docs/PERFORMANCE_IMPROVEMENTS.md`
- **API Reference**: `docs/API.md`

### Advanced Usage

```python
# Use Collective Intelligence programmatically
from openrouter_mcp.handlers.collective_intelligence import (
    collective_chat_completion
)

result = await collective_chat_completion({
    "prompt": "Explain quantum computing",
    "strategy": "weighted_average",
    "min_models": 3,
    "confidence_threshold": 0.8
})

print(result["consensus_response"])
print(result["quality_metrics"])
```

### Best Practices

**Security**:
- ✅ Use OS Keychain (not `.env`)
- ✅ Rotate keys every 90 days
- ✅ Never enable verbose logging in production
- ✅ Review security audit logs regularly

**Performance**:
- ✅ Shared client (automatic, no config needed)
- ✅ Adjust cache TTL based on your needs
- ✅ Use adaptive model selection for cost optimization

**Collective Intelligence**:
- ✅ Use `min_models=5` for critical decisions
- ✅ Set `confidence_threshold=0.8+` for accuracy
- ✅ Always validate with `cross_model_validation`

---

## 🎯 Common Use Cases

### 1. Model Comparison

```
"Compare how GPT-4, Claude, and Gemini explain quantum physics"
```

### 2. Cost-Effective AI

```
"Use adaptive model selection to answer this at lowest cost"
```

### 3. High-Accuracy Tasks

```
"Use 5-model consensus with 0.9 confidence to verify this calculation"
```

### 4. Vision Analysis

```
"Use GPT-4 Vision to analyze this medical chart" (attach image)
```

### 5. Code Generation

```
"Use ensemble reasoning to write a complex Python algorithm"
```

---

## ✅ Success Checklist

After setup, verify:

- [ ] Server starts without errors
- [ ] API key shows as "loaded from os-keychain"
- [ ] Claude Desktop shows OpenRouter tools
- [ ] Can list models successfully
- [ ] Can send basic chat message
- [ ] Security audit shows no issues

```bash
# Run full verification
npx openrouter-mcp status
npx openrouter-mcp security-audit
```

---

## 🎉 You're Ready!

The improved OpenRouter MCP now provides:

- **🔐 Enterprise Security**: Keychain storage, encrypted files, log sanitization
- **⚡ Peak Performance**: 95% faster, zero corruption, smart caching
- **🧠 Collective Intelligence**: 5 multi-model tools for better answers
- **🖼️ Secure Multimodal**: Path traversal vulnerability eliminated
- **📊 Semantic Similarity**: Multi-algorithm consensus grouping

All improvements are tested with **341 passing tests** and ready for production!

---

**Last Updated**: 2025-11-18
**Version**: 1.3.0 (Documentation Fix & Command Correction)

**Need Help?**
- 📖 Full Documentation: `docs/`
- 🐛 Issues: https://github.com/physics91/openrouter-mcp/issues
- 🔒 Security: `SECURITY.md`
