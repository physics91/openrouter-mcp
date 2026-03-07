# Security Architecture and Threat Model

## Executive Summary

This document outlines the security architecture, threat model, and best practices for the OpenRouter MCP server. As a system that handles API keys and provides access to multiple AI models, security is paramount.

## Table of Contents

- [Threat Model](#threat-model)
- [Security Architecture](#security-architecture)
- [API Key Management](#api-key-management)
- [Logging Security](#logging-security)
- [Secure Configuration](#secure-configuration)
- [Best Practices](#best-practices)
- [Incident Response](#incident-response)
- [Security Checklist](#security-checklist)

---

## Threat Model

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     User Environment                         │
│                                                              │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │ Claude       │◄────────┤ OpenRouter   │                 │
│  │ Desktop/Code │  MCP    │ MCP Server   │                 │
│  └──────────────┘         └──────┬───────┘                 │
│                                   │                          │
│                                   │ API Key                  │
│                                   │                          │
│                         ┌─────────▼────────┐                │
│                         │ Configuration    │                │
│                         │ Storage:         │                │
│                         │ • OS Keychain    │ ★ Recommended  │
│                         │ • Encrypted File │ ★ CI/CD        │
│                         │ • .env           │ ⚠ Dev Only     │
│                         │ • JSON configs   │ ⚠ Legacy       │
│                         └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
                                   │
                                   │ HTTPS
                                   │
                         ┌─────────▼────────┐
                         │   OpenRouter     │
                         │   API Gateway    │
                         └──────────────────┘
```

### Threats (STRIDE Model)

#### 1. Spoofing Identity

**Threat 1.1**: Attacker impersonates legitimate user by stealing session/API tokens
- **Likelihood**: Medium
- **Impact**: High (unauthorized access to AI models, cost implications)
- **Mitigation**:
  - Use OS-level keychain storage when available
  - Implement file permission restrictions (600 on Unix)
  - Regular API key rotation
  - Monitor API usage for anomalies

**Threat 1.2**: Malicious process masquerading as MCP server
- **Likelihood**: Low
- **Impact**: High (credential theft)
- **Mitigation**:
  - Verify package signatures during installation
  - Use trusted package managers (npm official registry)
  - Implement process integrity checks

#### 2. Tampering with Data

**Threat 2.1**: Man-in-the-Middle attack on API communications
- **Likelihood**: Low
- **Impact**: Critical (API key theft, data manipulation)
- **Mitigation**:
  - Enforce TLS 1.2+ for all HTTPS communications
  - Certificate pinning (OpenRouter API)
  - No fallback to HTTP

**Threat 2.2**: Modification of configuration files
- **Likelihood**: Medium
- **Impact**: High (credential exposure, service disruption)
- **Mitigation**:
  - File permission restrictions (600/700)
  - Configuration file integrity checks
  - User consent before writing credentials
  - Backup original configurations

#### 3. Repudiation

**Threat 3.1**: User denies API usage/costs
- **Likelihood**: Low
- **Impact**: Medium (billing disputes)
- **Mitigation**:
  - Comprehensive audit logging (optional)
  - Request/response tracking with timestamps
  - User authentication correlation

#### 4. Information Disclosure

**Threat 4.1**: API key exposure through plaintext storage
- **Likelihood**: Medium (with encrypted storage options)
- **Impact**: Critical (unauthorized API access, financial loss)
- **Mitigation**:
  - **PRIMARY**: OS keychain integration (encrypted at rest)
  - **SECONDARY**: AES-256-GCM encrypted file storage
  - **TERTIARY**: File permission restrictions (600)
  - Exclude .env from version control
  - Clear warnings about plaintext storage
  - User consent before writing credentials
  - Automatic shared environment detection

**Threat 4.2**: API key exposure in logs/error messages
- **Likelihood**: Low (MITIGATED - v2.0.0+)
- **Impact**: High
- **Mitigation**:
  - ✅ **IMPLEMENTED**: Comprehensive sanitization system (SensitiveDataSanitizer)
  - ✅ **IMPLEMENTED**: API keys masked in all log output (shows first 4 chars only)
  - ✅ **IMPLEMENTED**: User prompts hashed by default (SHA-256)
  - ✅ **IMPLEMENTED**: AI responses sanitized (metadata only in default mode)
  - ✅ **IMPLEMENTED**: Explicit opt-in required for verbose logging
  - ✅ **IMPLEMENTED**: Warning message when verbose mode enabled
  - See `SECURITY_BEST_PRACTICES.md` for operational logging guidance
- **Historical Risk**: Before v2.0.0, full payloads were logged at debug level (FIXED)

**Threat 4.3**: API key exposure in process environment
- **Likelihood**: Medium
- **Impact**: High (process inspection tools can read environment)
- **Mitigation**:
  - Minimize environment variable usage
  - Clear sensitive variables after use
  - Use secure memory when possible

**Threat 4.4**: Configuration files committed to version control
- **Likelihood**: High
- **Impact**: Critical (public exposure of credentials)
- **Mitigation**:
  - Default .gitignore patterns
  - Pre-commit hooks to detect secrets
  - Clear documentation warnings
  - Repository scanning tools

**Threat 4.5**: Shoulder surfing during API key entry
- **Likelihood**: Medium (shared workspaces)
- **Impact**: High
- **Mitigation**:
  - Masked input during key entry
  - Clear screen instructions
  - Prompt to verify secure environment

#### 5. Denial of Service (DoS)

**Threat 5.1**: API key abuse leading to rate limiting
- **Likelihood**: Medium
- **Impact**: Medium (service disruption)
- **Mitigation**:
  - Rate limiting on client side
  - API key rotation capabilities
  - Multiple key support
  - Usage monitoring/alerts

**Threat 5.2**: Resource exhaustion attacks
- **Likelihood**: Low
- **Impact**: Medium
- **Mitigation**:
  - Request timeout limits
  - Concurrent request limits
  - Memory usage monitoring

#### 6. Elevation of Privilege

**Threat 6.1**: Exploit to gain file system access beyond intended scope
- **Likelihood**: Low (FIXED - see CVE-2025-MULTIMODAL)
- **Impact**: High
- **Mitigation**:
  - ✅ **IMPLEMENTED**: Removed arbitrary file path access from multimodal handler
  - ✅ **IMPLEMENTED**: Strict input validation - only accepts bytes or URLs
  - Principle of least privilege
  - Sandboxed execution when possible
  - Input validation and sanitization
  - Regular security updates
- **Historical Vulnerability**: Path traversal in multimodal image handler (FIXED 2025-11-18)
  - See `reports/SECURITY_FIXES.md` for fix summary and follow-up notes

**Threat 6.2**: Configuration injection attacks
- **Likelihood**: Medium
- **Impact**: High (arbitrary code execution)
- **Mitigation**:
  - Validate all configuration inputs
  - JSON schema validation
  - Sanitize file paths
  - Prevent path traversal
  - ✅ **IMPLEMENTED**: No file path acceptance from external inputs

---

## Security Architecture

### Defense in Depth Layers

1. **Transport Layer**
   - TLS 1.2+ enforcement
   - Certificate validation
   - No HTTP fallback

2. **Application Layer**
   - Input validation
   - Output sanitization
   - Error handling without information leakage

3. **Storage Layer**
   - OS keychain integration (primary)
   - File permission restrictions
   - Encryption at rest (when keychain is used)

4. **Access Control Layer**
   - User consent before credential storage
   - Minimal privilege principle
   - Explicit permission grants

### Secure by Default Principles

1. **No Automatic Credential Storage**
   - User must explicitly consent to each storage location
   - Clear explanation of security implications
   - Opt-in for less secure options

2. **Prefer OS Keychain**
   - Default recommendation for credential storage
   - Encrypted at rest
   - Protected by OS security mechanisms

3. **Minimal Configuration**
   - Only necessary files created
   - User chooses which integrations to configure
   - No silent credential writes

4. **Visibility and Control**
   - Clear messaging about what's being stored where
   - Easy credential rotation/deletion
   - Audit trail of configuration changes

---

## API Key Management

### Storage Options (Priority Order)

#### 1. OS Keychain (Recommended - Most Secure)

**Platforms**:
- macOS: Keychain Access
- Windows: Credential Manager
- Linux: Secret Service API (libsecret/gnome-keyring)

**Advantages**:
- Encrypted at rest
- OS-level access controls
- Integration with system security policies
- Can require user authentication to access
- Not visible in plain text files

**Implementation**:
```javascript
// Using keytar library
const keytar = require('keytar');

// Store API key
await keytar.setPassword('openrouter-mcp', 'api-key', userApiKey);

// Retrieve API key
const apiKey = await keytar.getPassword('openrouter-mcp', 'api-key');

// Delete API key
await keytar.deletePassword('openrouter-mcp', 'api-key');
```

**Limitations**:
- Requires native dependencies (keytar)
- May not work in headless/SSH environments
- User still has access (not encrypted from user perspective)

#### 2. Encrypted File Storage (Recommended for CI/CD)

**Security Level**: MEDIUM-HIGH

**Encryption Details**:
- Algorithm: AES-256-GCM (Authenticated Encryption)
- Key Derivation: SHA-256(hostname + username + platform + architecture)
- IV: Random 16 bytes per encryption
- Authentication: GCM auth tag prevents tampering
- Location: `~/.openrouter-mcp/.credentials.enc`

**Advantages**:
- Encrypted at rest
- Machine-specific encryption
- No external dependencies
- Works in headless environments
- File permissions enforced (600)
- Tamper-proof (authenticated encryption)

**Security Measures**:
- AES-256-GCM encryption
- Machine-specific key derivation
- File permissions: 600
- Audit logging

**Risks**:
- Key derived from machine data (accessible if attacker has code execution)
- Not portable across machines without re-encryption
- Less secure than OS Keychain

**Use Cases**:
- CI/CD environments
- Docker containers
- Systems without keychain support
- Automated deployments

**Implementation**:
```javascript
// Store encrypted
const secureCredentials = require('./bin/secure-credentials');
secureCredentials.storeInEncryptedFile('your-api-key');

// Retrieve
const apiKey = secureCredentials.getFromEncryptedFile();
```

#### 3. Environment Variables (.env file)

**Security Level**: MEDIUM (plaintext with permissions)

**Advantages**:
- Simple to implement
- Widely understood
- Works in all environments
- Easy to integrate with deployment tools

**Security Measures**:
- File permissions: 600 (owner read/write only)
- .gitignore to prevent commits
- Clear documentation about risks
- User consent required

**Risks**:
- Plaintext storage
- Visible in file system
- Can be accidentally committed
- Accessible to any process running as the user

#### 4. Configuration Files (JSON)

**Use Case**: Claude Desktop/Code integration

**Security Measures**:
- File permissions: 600
- User consent before writing
- Clear warnings about plaintext storage
- Location in user home directory

**Risks**:
- Similar to .env files
- May be backed up to cloud services
- Accessible to other applications

### API Key Rotation

Best practice: Rotate API keys regularly (recommended: every 90 days)

**Rotation Process**:
1. Generate new API key on OpenRouter
2. Update stored credentials using `openrouter-mcp rotate-key`
3. Test new key functionality
4. Revoke old key on OpenRouter
5. Clear old key from all storage locations

---

## Logging Security

### Overview

The OpenRouter MCP client implements comprehensive logging security to prevent sensitive data exposure. All API keys, user prompts, and AI responses are sanitized before logging.

### Sanitization Features

**Default Mode (Secure)**:
- API keys: Masked (shows only first 4 characters)
- User prompts: SHA-256 hashed
- AI responses: Metadata only (token counts, model info)
- Multimodal content: Type and size information only

**Verbose Mode (Debug)**:
- API keys: Still masked (never logged in full)
- User prompts: Truncated to 50 characters
- AI responses: Truncated to 100 characters
- Requires explicit opt-in with `enable_verbose_logging=true`
- Displays warning on activation

### Configuration

```python
# Secure default (production)
client = OpenRouterClient(
    api_key="your-key",
    enable_verbose_logging=False  # Default
)

# Debug mode (development only)
client = OpenRouterClient(
    api_key="your-key",
    enable_verbose_logging=True  # Explicit opt-in required
)
```

### Best Practices

1. **Never enable verbose logging in production**
2. **Use INFO or WARNING log levels for production**
3. **Encrypt log files at rest**
4. **Implement log retention policies**
5. **Restrict log file access (chmod 600)**

### Compliance Considerations

- **GDPR**: Default mode hashes all user data (not identifiable)
- **HIPAA**: Never enable verbose logging for healthcare data
- **PCI DSS**: No payment data should ever be sent to AI models

**Operational Guidance**: See `SECURITY_BEST_PRACTICES.md` for logging hygiene, credential handling, and deployment recommendations.

---

## Secure Configuration

### File Permissions

#### Unix/Linux/macOS

```bash
# Configuration files
chmod 600 ~/.env
chmod 600 ~/.claude/claude_code_config.json
chmod 700 ~/.claude/

# On macOS (Claude Desktop)
chmod 600 ~/Library/Application\ Support/Claude/claude_desktop_config.json
chmod 700 ~/Library/Application\ Support/Claude/
```

#### Windows

```powershell
# Remove inherited permissions and grant only current user
$path = "$env:USERPROFILE\.claude\claude_code_config.json"
$acl = Get-Acl $path
$acl.SetAccessRuleProtection($true, $false)
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $env:USERNAME, "FullControl", "Allow"
)
$acl.SetAccessRule($rule)
Set-Acl $path $acl
```

### .gitignore Protection

Always include in your project `.gitignore`:

```gitignore
# Environment variables
.env
.env.local
.env.*.local

# API keys and secrets
*.key
*.pem
secrets/

# Configuration with credentials
*config.json
!*config.example.json
```

### Pre-commit Hooks

Prevent accidental credential commits:

```bash
#!/bin/sh
# .git/hooks/pre-commit

# Check for potential secrets
if git diff --cached --name-only | xargs grep -l "OPENROUTER_API_KEY\|sk-or-"; then
    echo "ERROR: Potential API key found in staged files!"
    echo "Please remove credentials before committing."
    exit 1
fi
```

---

## Best Practices

### For Individual Developers

1. **Use OS Keychain**
   - Always prefer keychain storage when available
   - Keep OS security updates current

2. **Protect .env Files**
   - Never commit to version control
   - Set proper file permissions (600)
   - Keep in project root or secure location

3. **Regular Key Rotation**
   - Rotate API keys every 90 days
   - Immediately rotate if compromise suspected
   - Keep old key active briefly for zero-downtime rotation

4. **Monitor API Usage**
   - Regularly check OpenRouter dashboard
   - Set up billing alerts
   - Investigate unexpected usage patterns

5. **Secure Your Workstation**
   - Use full disk encryption
   - Lock screen when away
   - Use strong authentication (password + 2FA)

### For Enterprise/Shared Environments

1. **Never Use Plaintext Storage**
   - Mandatory keychain or secrets management system
   - No .env files on shared systems
   - Centralized credential rotation

2. **Implement Secrets Management**
   - Use HashiCorp Vault, AWS Secrets Manager, or similar
   - Centralized audit logging
   - Role-based access control
   - Automatic rotation policies

3. **Network Segmentation**
   - Isolate AI workloads
   - Restrict outbound API access
   - Monitor network traffic

4. **Audit and Compliance**
   - Log all API key access
   - Regular security audits
   - Compliance with data protection regulations
   - Incident response procedures

5. **Access Control**
   - Principle of least privilege
   - Individual API keys per user/service
   - Regular access reviews
   - Immediate revocation on termination

### For CI/CD Environments

1. **Use Secrets Management**
   - GitHub Secrets, GitLab CI/CD variables
   - Never hardcode in workflows
   - Use short-lived tokens when possible

2. **Minimize Exposure**
   - Only inject secrets in necessary steps
   - Clear from environment after use
   - Avoid logging secret values

3. **Audit Trail**
   - Log all secret access
   - Monitor for unauthorized access
   - Alert on anomalies

---

## Incident Response

### Suspected API Key Compromise

**Immediate Actions** (within 1 hour):

1. **Revoke Compromised Key**
   - Log into OpenRouter dashboard
   - Revoke the suspected key immediately
   - Do NOT wait to verify compromise

2. **Generate New Key**
   - Create replacement API key
   - Update all legitimate systems
   - Test functionality

3. **Assess Exposure**
   - Check OpenRouter usage logs
   - Identify unauthorized requests
   - Calculate potential financial impact

**Short-term Actions** (within 24 hours):

4. **Investigate Root Cause**
   - How was the key compromised?
   - Which systems were affected?
   - What data was accessed?

5. **Contain Damage**
   - Revoke all potentially affected keys
   - Update all credential storage
   - Patch vulnerability if found

6. **Notify Stakeholders**
   - Inform management if enterprise
   - Document incident timeline
   - Prepare incident report

**Long-term Actions** (within 1 week):

7. **Prevent Recurrence**
   - Implement additional security controls
   - Update security documentation
   - Train team on lessons learned

8. **Monitor for Reoccurrence**
   - Enhanced monitoring for 30 days
   - Review security logs regularly
   - Update incident response procedures

### Incident Response Contact

For security incidents involving this project:
- Report issues: [GitHub Security Advisories]
- Email: [security@yourproject.com]
- Severity levels: Critical, High, Medium, Low

---

## Security Checklist

### Initial Setup

- [ ] Install from trusted source (official npm registry)
- [ ] Verify package integrity (npm audit)
- [ ] Use OS keychain for API key storage (if available)
- [ ] Set proper file permissions on all config files
- [ ] Add .env and config files to .gitignore
- [ ] Review security warnings during init
- [ ] Understand where credentials are stored
- [ ] Test API key rotation process

### Ongoing Maintenance

- [ ] Rotate API keys every 90 days
- [ ] Review API usage monthly
- [ ] Update dependencies regularly (npm audit fix)
- [ ] Monitor for security advisories
- [ ] Audit file permissions quarterly
- [ ] Review access logs for anomalies
- [ ] Test incident response procedures
- [ ] Keep OS and security tools updated

### Before Deployment

- [ ] Audit all configuration files
- [ ] Verify no credentials in version control
- [ ] Confirm proper file permissions
- [ ] Test in production-like environment
- [ ] Document credential locations
- [ ] Prepare incident response procedures
- [ ] Set up monitoring and alerting
- [ ] Review security architecture

### Enterprise Specific

- [ ] Implement centralized secrets management
- [ ] Enable audit logging
- [ ] Configure RBAC for API keys
- [ ] Set up automated key rotation
- [ ] Integrate with SIEM system
- [ ] Conduct penetration testing
- [ ] Perform security awareness training
- [ ] Establish incident response team

---

## Security Updates

This document is version controlled. Check for updates regularly:
- **Last Updated**: 2025-11-17
- **Version**: 1.4.0
- **Next Review**: 2025-02-17

---

## References

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [OpenRouter Security Best Practices](https://openrouter.ai/docs/security)
- [STRIDE Threat Model](https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats)

---

## Contact

For security concerns or questions:
- GitHub Issues (non-sensitive): [Link to issues]
- Security Email: [security@yourproject.com]
- Documentation: [Link to docs]

**Note**: For responsible disclosure of security vulnerabilities, please use private security advisories on GitHub or email directly. Do not open public issues for security vulnerabilities.
