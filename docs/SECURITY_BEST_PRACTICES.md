# Security Best Practices for OpenRouter MCP

## Quick Start Security Guide

### For Individual Developers

**Recommended Setup (5 minutes):**

1. **Install with OS Keychain Support**
   ```bash
   npm install -g @physics91/openrouter-mcp keytar
   ```

2. **Initialize with Secure Storage**
   ```bash
   openrouter-mcp init
   # Choose "OS Keychain" when prompted
   ```

3. **Verify Security Configuration**
   ```bash
   openrouter-mcp security-audit
   ```

### For Enterprise/Team Environments

**Do NOT use plaintext storage.** Implement one of these solutions:

1. **Enterprise Secrets Management**
   - HashiCorp Vault
   - AWS Secrets Manager
   - Azure Key Vault
   - Google Cloud Secret Manager

2. **Contact Security Team**
   - Request approved credential storage method
   - Follow organizational security policies
   - Enable audit logging

---

## Security Features

### 1. OS Keychain Storage (Recommended)

**What it is:**
- Uses your operating system's native credential storage
- macOS: Keychain Access
- Windows: Credential Manager
- Linux: Secret Service API (gnome-keyring or KWallet)

**Security Benefits:**
- ✓ Encrypted at rest
- ✓ Protected by OS security mechanisms
- ✓ May require user authentication to access
- ✓ Not visible in plain text files
- ✓ Integrated with system security policies

**Installation:**
```bash
npm install keytar
```

**Setup:**
```bash
openrouter-mcp init
# Select "OS Keychain/Credential Manager" when prompted
```

**Verification:**
```bash
# macOS
security find-generic-password -s openrouter-mcp

# Windows
cmdkey /list | findstr openrouter-mcp

# Linux (GNOME)
secret-tool search service openrouter-mcp
```

### 2. Encrypted File Storage (Recommended for CI/CD)

**What it is:**
- AES-256-GCM encrypted file storage
- Machine-specific encryption key
- No external dependencies required
- Works in headless/containerized environments

**Security Benefits:**
- ✓ Encrypted at rest with AES-256-GCM
- ✓ Machine-specific key derivation
- ✓ Tamper-proof (authenticated encryption)
- ✓ File permissions enforced (600)
- ✓ No external dependencies
- ✓ Works in CI/CD pipelines
- ⚠ Less secure than OS Keychain (key derivable by root/admin)

**When to use:**
- CI/CD environments
- Docker containers
- Systems without keychain support
- Automated deployments
- Headless servers

**Setup:**
```bash
openrouter-mcp init
# Select "Encrypted File Storage" when prompted
```

**Manual Usage:**
```javascript
const { storeInEncryptedFile, getFromEncryptedFile } = require('./bin/secure-credentials');

// Store
storeInEncryptedFile('your-api-key');

// Retrieve
const apiKey = getFromEncryptedFile();
```

**Technical Details:**
- **Algorithm**: AES-256-GCM (AEAD)
- **Key Derivation**: SHA-256(hostname + username + platform + architecture)
- **IV**: Random 16 bytes per encryption
- **File Location**: `~/.openrouter-mcp/.credentials.enc`
- **Permissions**: Automatically set to 600 (owner only)

**Limitations:**
- Encryption key is machine-specific (not portable)
- Attacker with code execution on same machine can potentially decrypt
- Best suited for isolated environments (containers, VMs)

### 3. Environment Variables (.env file)

**When to use:**
- Development/testing only
- Low-security environments
- Single-user systems
- Temporary testing

**⚠ NOT recommended for:**
- Production environments
- Shared systems
- Long-term storage

**Security Measures:**

1. **File Permissions**
   ```bash
   # Unix/Linux/macOS
   chmod 600 .env

   # Windows (PowerShell)
   icacls .env /inheritance:r /grant:r "$env:USERNAME:(F)"
   ```

2. **Version Control Protection**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore

   # Verify not committed
   git ls-files .env  # Should return nothing
   ```

3. **Pre-commit Hook** (E:\ai-dev\openrouter-mcp\.git\hooks\pre-commit)
   ```bash
   #!/bin/sh
   # Prevent accidental credential commits

   if git diff --cached --name-only | xargs grep -l "OPENROUTER_API_KEY\|sk-or-"; then
       echo "ERROR: Potential API key found in staged files!"
       exit 1
   fi
   ```

### 3. Configuration Files (Claude Integrations)

**Security Considerations:**
- Required for Claude Desktop/Code integration
- API key stored in plaintext
- Protected by file permissions

**Setup with Consent:**
```bash
openrouter-mcp init
# Explicit consent required for each config file
```

**Manual Permission Setup:**
```bash
# macOS (Claude Desktop)
chmod 600 ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Windows (Claude Desktop)
icacls "%APPDATA%\Claude\claude_desktop_config.json" /inheritance:r /grant:r "%USERNAME%:(F)"

# Claude Code user scope
chmod 600 ~/.claude.json

# Claude Code project scope
chmod 600 .mcp.json
```

---

## API Key Management

### Obtaining an API Key

1. Visit https://openrouter.ai/
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. **Copy immediately** (shown only once)

**Security Tips:**
- Use descriptive names: "openrouter-mcp-dev-laptop"
- Set usage limits if available
- Note creation date for rotation tracking

### API Key Rotation

**Recommended Frequency:** Every 90 days

**Rotation Process:**

1. **Generate New Key**
   - Create new key on OpenRouter dashboard
   - Keep old key active temporarily

2. **Update All Locations**
   ```bash
   openrouter-mcp rotate-key
   # Enter new key when prompted
   ```

3. **Test New Key**
   ```bash
   openrouter-mcp start
   # Verify functionality
   ```

4. **Revoke Old Key**
   - Once confirmed working, revoke old key on OpenRouter
   - Clear from any backup locations

**Emergency Rotation** (suspected compromise):
- Revoke immediately (don't wait for testing)
- Generate and deploy new key ASAP
- Review access logs
- Document incident

### API Key Deletion

**Remove from all locations:**
```bash
openrouter-mcp delete-credentials
```

**Manual Cleanup:**
```bash
# Remove from keychain
# macOS
security delete-generic-password -s openrouter-mcp

# Windows
cmdkey /delete:openrouter-mcp

# Linux
secret-tool clear service openrouter-mcp

# Remove from files
rm .env
# Manually remove from Claude configs
```

---

## Security Audit

### Regular Security Checks

**Run Monthly:**
```bash
openrouter-mcp security-audit
```

**Review Output:**
- Critical Issues: Fix immediately
- Warnings: Address within 1 week
- Good Practices: Maintain

**Common Issues:**

1. **Insecure File Permissions**
   ```bash
   # Fix
   chmod 600 .env
   chmod 600 ~/.claude/claude_*_config.json
   ```

2. **.env Not in .gitignore**
   ```bash
   # Fix
   echo ".env" >> .gitignore
   git rm --cached .env  # If accidentally committed
   ```

3. **OS Keychain Not Available**
   ```bash
   # Fix
   npm install keytar
   openrouter-mcp rotate-key  # Migrate to keychain
   ```

### Monitoring API Usage

**OpenRouter Dashboard:**
1. Log in to https://openrouter.ai/
2. Navigate to Usage/Billing
3. Review request logs
4. Check for anomalies:
   - Unusual request volume
   - Unknown user agents
   - Unexpected times/locations

**Set Up Alerts:**
- Billing threshold alerts
- Usage spike notifications
- Email alerts for API errors

---

## Compliance and Enterprise

### Enterprise Security Requirements

**Mandatory Controls:**

1. **Centralized Secrets Management**
   - Use HashiCorp Vault, AWS Secrets Manager, etc.
   - No local plaintext storage
   - Automated rotation policies
   - Audit logging enabled

2. **Access Control**
   - Individual API keys per user/service
   - Role-based access control (RBAC)
   - Regular access reviews
   - Immediate revocation on termination

3. **Network Security**
   - Restrict outbound connections
   - Use approved proxies/gateways
   - Monitor network traffic
   - TLS 1.2+ enforcement

4. **Audit and Compliance**
   - Comprehensive logging
   - Log retention policies
   - Regular security audits
   - Compliance certifications (SOC 2, ISO 27001)

### Integration with Enterprise Tools

**HashiCorp Vault:**
```bash
# Store API key
vault kv put secret/openrouter-mcp api_key="sk-or-..."

# Retrieve in scripts
export OPENROUTER_API_KEY=$(vault kv get -field=api_key secret/openrouter-mcp)
```

**AWS Secrets Manager:**
```bash
# Store API key
aws secretsmanager create-secret \
  --name openrouter-mcp-api-key \
  --secret-string "sk-or-..."

# Retrieve
aws secretsmanager get-secret-value \
  --secret-id openrouter-mcp-api-key \
  --query SecretString --output text
```

---

## Platform-Specific Guidance

### macOS

**Strengths:**
- Excellent keychain integration
- Strong file permissions
- Full disk encryption (FileVault)

**Best Practices:**
1. Enable FileVault
2. Use Keychain for credentials
3. Lock screen when away (hot corner)
4. Keep macOS updated

**Verification:**
```bash
# Check keychain
security find-generic-password -s openrouter-mcp -w

# Check file permissions
ls -la .env
# Should show: -rw------- (600)
```

### Windows

**Strengths:**
- Credential Manager integration
- BitLocker encryption
- Group Policy controls

**Best Practices:**
1. Enable BitLocker
2. Use Credential Manager
3. Set screen lock timeout
4. Keep Windows updated

**Verification:**
```powershell
# Check Credential Manager
cmdkey /list | Select-String "openrouter-mcp"

# Check file permissions
icacls .env
# Should show only current user with Full Control
```

### Linux

**Strengths:**
- Secret Service API
- File permission granularity
- LUKS encryption

**Best Practices:**
1. Install gnome-keyring or KWallet
2. Enable full disk encryption (LUKS)
3. Use strong file permissions
4. Keep system updated

**Verification:**
```bash
# Check secret service
secret-tool search service openrouter-mcp

# Check file permissions
ls -la .env
# Should show: -rw------- (600)

# Check SELinux/AppArmor
sestatus  # or aa-status
```

---

## CI/CD Security

### GitHub Actions

**Secure Setup:**

```yaml
# .github/workflows/test.yml
name: Test OpenRouter MCP

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up environment
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          # Key is only available in this step
          echo "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" >> $GITHUB_ENV

      - name: Run tests
        run: npm test

      # Key is automatically cleared after workflow
```

**Security Rules:**
- Never echo/print secrets
- Use GitHub Secrets (Settings > Secrets)
- Limit secret access to necessary steps
- Rotate secrets regularly
- Enable secret scanning

### GitLab CI/CD

```yaml
# .gitlab-ci.yml
test:
  script:
    - npm test
  variables:
    OPENROUTER_API_KEY: $OPENROUTER_API_KEY
  only:
    - main
  secrets:
    OPENROUTER_API_KEY:
      vault: production/openrouter/api_key
```

**Security Rules:**
- Use CI/CD variables (Settings > CI/CD > Variables)
- Mark variables as "Protected" and "Masked"
- Limit to specific branches/tags
- Use Vault integration when possible

---

## Incident Response

### Suspected Compromise

**Immediate Actions** (within 1 hour):

1. **Revoke API Key**
   ```bash
   # On OpenRouter dashboard
   # Revoke the suspected key immediately
   ```

2. **Assess Exposure**
   ```bash
   # Check OpenRouter usage logs
   # Identify unauthorized requests
   # Calculate potential costs
   ```

3. **Generate New Key**
   ```bash
   openrouter-mcp rotate-key
   # Use new key immediately
   ```

**Investigation** (within 24 hours):

4. **Root Cause Analysis**
   - How was key compromised?
   - What systems affected?
   - What data accessed?

5. **Security Audit**
   ```bash
   openrouter-mcp security-audit
   # Address all issues found
   ```

6. **Document Incident**
   - Timeline of events
   - Impact assessment
   - Remediation steps
   - Lessons learned

**Prevention** (within 1 week):

7. **Implement Controls**
   - Additional security measures
   - Monitoring improvements
   - Team training

8. **Enhanced Monitoring**
   - 30-day enhanced surveillance
   - Daily log reviews
   - Alert tuning

### Reporting Security Issues

**Responsible Disclosure:**

For security vulnerabilities in OpenRouter MCP:
- Email: [security@yourproject.com]
- GitHub Security Advisories (preferred)
- Do NOT create public issues

**Include:**
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested remediation

---

## Security Checklist

### Initial Setup
- [ ] Install keytar for OS Keychain support
- [ ] Run `openrouter-mcp init` with keychain option
- [ ] Add .env to .gitignore
- [ ] Set secure file permissions (600)
- [ ] Run security audit
- [ ] Document key location
- [ ] Set rotation reminder (90 days)

### Monthly Maintenance
- [ ] Run security audit
- [ ] Review API usage logs
- [ ] Check for updates (`npm outdated`)
- [ ] Verify file permissions
- [ ] Review .gitignore effectiveness
- [ ] Test key rotation process

### Quarterly Tasks
- [ ] Rotate API key
- [ ] Review security documentation
- [ ] Update incident response procedures
- [ ] Conduct security training
- [ ] Audit access controls
- [ ] Review compliance status

### Annual Tasks
- [ ] Comprehensive security review
- [ ] Penetration testing (enterprise)
- [ ] Update security policies
- [ ] Review and renew certifications
- [ ] Disaster recovery testing

---

## Additional Resources

### Documentation
- [Main Security Documentation](./SECURITY.md)
- [Threat Model](./SECURITY.md#threat-model)
- [Installation Guide](./INSTALLATION.md)
- [Troubleshooting](./TROUBLESHOOTING.md)

### External Resources
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [OpenRouter Security Documentation](https://openrouter.ai/docs/security)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

### Tools
- [git-secrets](https://github.com/awslabs/git-secrets) - Prevent committing secrets
- [gitleaks](https://github.com/gitleaks/gitleaks) - Scan for secrets in repos
- [truffleHog](https://github.com/trufflesecurity/trufflehog) - Find credentials in git history

---

## Support

**Security Questions:**
- Email: [security@yourproject.com]
- GitHub Discussions (non-sensitive)

**Security Incidents:**
- GitHub Security Advisories (preferred)
- Private email for disclosure

**General Support:**
- GitHub Issues
- Documentation: [docs/](.)

---

**Last Updated:** 2025-11-17
**Version:** 1.4.0
**Next Review:** 2025-02-17
