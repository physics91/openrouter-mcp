# Security Policy

## Overview

This document outlines the security practices and recommendations for using the OpenRouter MCP Server. Security is a foundational concern, and we've implemented multiple layers of protection to safeguard your API keys, data, and privacy.

## Security Features

### 1. API Key Protection

#### ✅ SECURE: Environment Variables (Recommended)
**All API keys MUST be stored as environment variables, never in configuration files.**

**Windows:**
```cmd
set OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

**Linux/macOS:**
```bash
export OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

**Permanent (Linux/macOS):**
```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export OPENROUTER_API_KEY=sk-or-v1-your-api-key-here' >> ~/.bashrc
source ~/.bashrc
```

#### ❌ INSECURE: Configuration Files (Forbidden)
The system **actively prevents** API keys from being stored in configuration files:

- Line 92 in `mcp_manager.py`: API key field removed from preset configuration
- Line 422 in `mcp_manager.py`: Warning issued if API key is provided as argument
- Validation checks will **reject** configurations containing API keys
- Security errors are raised if API keys are detected in config files

### 2. Data Privacy in Benchmarking

#### Default: Privacy-Preserving Mode
By default, **all benchmark operations redact sensitive content** from logs and saved results:

```python
# ✅ SECURE: Default behavior (privacy mode enabled)
await benchmark_models(
    models=["openai/gpt-4", "anthropic/claude-3.5-sonnet"],
    prompt="What is the capital of France?"
    # save_results=True will save REDACTED content only
)
```

**Saved results will show:**
```json
{
  "config": {
    "prompt": "<REDACTED: 32 chars>",
    "privacy_mode": true
  },
  "results": {
    "openai/gpt-4": {
      "response": "<REDACTED: 245 chars>"
    }
  }
}
```

#### Opt-In: Verbose Logging (Use With Caution)
To include actual content in logs (for debugging only):

```python
# ⚠️ WARNING: This includes prompt/response content in logs
await benchmark_models(
    models=["openai/gpt-4"],
    prompt="Sensitive data here",
    include_prompts_in_logs=True  # Explicit consent required
)
```

**Warning message will be logged:**
```
PRIVACY WARNING: Logging prompt content is enabled.
Prompts may contain sensitive or personal information.
```

### 3. Secure Logging Practices

#### Automatic Data Sanitization
The `SensitiveDataSanitizer` class (in `openrouter.py`) automatically protects:

**API Keys in Headers:**
```python
# Before sanitization (NEVER logged):
{"Authorization": "Bearer sk-or-v1-abc123def456..."}

# After sanitization (what gets logged):
{"Authorization": "Bearer sk-o...***MASKED***"}
```

**Request/Response Content:**
```python
# Verbose logging disabled (default):
# Only metadata logged: message count, content length, role

# Verbose logging enabled:
# Content truncated to 100 characters maximum
```

**Error Messages:**
```python
# Response bodies in errors are truncated to 100 characters
# Full sensitive data is NEVER included in exception messages
```

### 4. Secrets Management Best Practices

#### Option A: Environment Variables (Basic)
Suitable for development and single-user setups:

```bash
export OPENROUTER_API_KEY=sk-or-v1-your-key
```

**Pros:**
- Simple to set up
- No additional dependencies
- Supported by all platforms

**Cons:**
- Not encrypted at rest
- Visible in process environment
- Manual management required

#### Option B: OS Keychain Integration (Advanced)
For production or enhanced security, integrate with OS-native secret storage:

**Python keyring library (optional dependency):**
```python
# Install: pip install keyring
import keyring

# Store API key securely
keyring.set_password("openrouter-mcp", "api_key", "sk-or-v1-your-key")

# Retrieve API key
api_key = keyring.get_password("openrouter-mcp", "api_key")
```

**Supported backends:**
- Windows: Windows Credential Manager
- macOS: Keychain
- Linux: Secret Service (GNOME Keyring, KWallet)

#### Option C: Cloud Secret Managers (Enterprise)
For team/production environments:

- **AWS Secrets Manager**
- **Azure Key Vault**
- **Google Cloud Secret Manager**
- **HashiCorp Vault**

## Threat Model

### Threats Mitigated

1. **Secret Exposure via Configuration Files**
   - **Threat:** API keys stored in plaintext config files committed to version control
   - **Mitigation:** Environment variable enforcement + validation checks + rejection of configs with keys

2. **Information Disclosure via Logs**
   - **Threat:** User prompts/responses containing PII logged by default
   - **Mitigation:** Privacy-preserving mode by default + opt-in verbose logging with warnings

3. **Secret Leakage via Error Messages**
   - **Threat:** API responses containing sensitive data exposed in exception messages
   - **Mitigation:** Response body redaction + truncation to 100 characters in errors

4. **Unauthorized Access via Stolen Credentials**
   - **Mitigation:** Principle of least privilege + secure storage recommendations

### Residual Risks

1. **Environment Variable Exposure**
   - **Risk:** Environment variables visible to processes with same user privileges
   - **Recommendation:** Use OS keychain or cloud secret managers for production

2. **Memory Dumps**
   - **Risk:** API keys visible in process memory dumps
   - **Recommendation:** Implement memory zeroing for sensitive data (future enhancement)

3. **Opt-In Verbose Logging**
   - **Risk:** Users may enable verbose logging and leak sensitive data
   - **Mitigation:** Clear warnings + documentation + explicit consent required

## Security Checklist

### For Developers

- [ ] **NEVER** commit `.env` files or config files containing API keys
- [ ] **ALWAYS** use environment variables for secrets
- [ ] Add `.env` and `*config*.json` to `.gitignore`
- [ ] Use privacy mode (default) for benchmarking in production
- [ ] Enable verbose logging only for local debugging
- [ ] Review logs before sharing (even sanitized logs may contain metadata)

### For System Administrators

- [ ] Use OS keychain or cloud secret managers for production
- [ ] Implement secret rotation policies (rotate API keys every 90 days)
- [ ] Monitor API usage for anomalies (use `track_usage()` tool)
- [ ] Restrict file permissions on config directories (`chmod 700 ~/.claude`)
- [ ] Use dedicated service accounts with minimal permissions
- [ ] Enable audit logging at the system level

### For Security Auditors

- [ ] Verify API keys are NOT in config files: `grep -r "sk-or-" ~/.claude/`
- [ ] Check environment variable usage: `env | grep OPENROUTER`
- [ ] Review benchmark results for redaction: `cat benchmarks/*.json`
- [ ] Inspect logs for sanitization: `tail -f logs/*.log`
- [ ] Test error handling: Trigger errors and verify response redaction

## Vulnerability Disclosure

### Reporting Security Issues

**DO NOT** create public GitHub issues for security vulnerabilities.

**Email:** security@[your-domain-here] (replace with actual security contact)

**Include:**
- Detailed description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Suggested fixes (optional)

**Response Timeline:**
- Acknowledgment: Within 48 hours
- Initial assessment: Within 7 days
- Fix target: Within 30 days for high-severity issues

### Security Updates

Security patches will be released as:
- **Patch versions** for backwards-compatible security fixes (e.g., 1.4.1)
- **Minor versions** for security enhancements requiring changes (e.g., 1.5.0)

Subscribe to security advisories: [GitHub Security Advisories](https://github.com/your-org/openrouter-mcp/security/advisories)

## Compliance & Standards

This project implements security controls aligned with:

- **OWASP Top 10 (2021)**: Protection against A01 (Broken Access Control), A02 (Cryptographic Failures), A09 (Security Logging Failures)
- **CWE-798**: Hard-coded credentials prevention
- **CWE-532**: Information exposure through log files prevention
- **NIST SP 800-53**: AC-3 (Access Enforcement), IA-5 (Authenticator Management), AU-2 (Audit Events)

## Defense in Depth Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Secure Secret Storage (Environment/Keychain)       │
│  - API keys never in config files                          │
│  - Validation rejects configs with embedded secrets        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Input Sanitization                                 │
│  - Request headers sanitized before logging                │
│  - Payload content redacted (metadata only by default)     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Privacy-Preserving Logging                        │
│  - Prompts/responses redacted by default                   │
│  - Opt-in verbose mode with explicit warnings              │
│  - Hash-based content verification (no plaintext)          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Error Handling                                     │
│  - Response bodies truncated in exceptions                 │
│  - No sensitive data in error messages                     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Principle of Least Privilege                      │
│  - Minimal permissions for service accounts                │
│  - File permissions: 700 for config directories            │
└─────────────────────────────────────────────────────────────┘
```

## Secure by Default Philosophy

This project follows **"Secure by Default"** principles:

1. **Default Configuration is Most Secure**: Privacy mode enabled, verbose logging disabled
2. **Fail Securely**: Validation errors prevent insecure configurations from being saved
3. **Explicit Consent**: Dangerous operations (verbose logging) require explicit opt-in
4. **Clear Warnings**: Security implications are communicated before risky actions
5. **Defense in Depth**: Multiple layers of security controls

## Additional Resources

- [OpenRouter API Security](https://openrouter.ai/docs/security)
- [OWASP Cheat Sheet: Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [OWASP Cheat Sheet: Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [CWE-798: Hard-coded Credentials](https://cwe.mitre.org/data/definitions/798.html)
- [CWE-532: Information Exposure Through Log Files](https://cwe.mitre.org/data/definitions/532.html)

---

**Last Updated:** 2025-12-29
**Version:** 1.4.0
**Security Contact:** [To be configured]
