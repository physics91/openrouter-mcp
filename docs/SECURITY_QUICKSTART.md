# Security Quick Start Guide

## ⚡ 2-Minute Security Setup

### For New Users

```bash
# 1. Install
npm install

# 2. Initialize (automatically uses v2.0)
openrouter-mcp init

# 3. Verify
npm run test:security
```

**You're done!** ✅ Your credentials are now protected with:
- 256-bit random encryption key
- OS Keystore protection (DPAPI/Keychain/libsecret)
- AES-256-GCM authenticated encryption

---

### For Existing Users (v1.0)

```bash
# 1. Check current version
openrouter-mcp security-audit

# 2. If you see "v1.0" - MIGRATE NOW
openrouter-mcp migrate-encryption

# 3. Verify migration
openrouter-mcp security-audit
```

**Migration complete!** ✅ Your credentials are now secure.

---

## 🔒 Security Status Check

### Quick Health Check
```bash
openrouter-mcp security-audit
```

### What to Look For

**✅ SECURE (v2.0)**:
```
✓ OS Keychain: Master key found (v2.0)
✓ Encrypted File: API key found (AES-256-GCM v2.0)
✓ Environment: Single-user
```

**⚠️ INSECURE (v1.0)**:
```
⚠ Encrypted File: v1.0 (deterministic key - migrate now)
! Recommendation: Migrate to v2.0 immediately
```

---

## 🛡️ Security Levels Explained

### v2.0 (SECURE) ✅
- **Key**: 256-bit cryptographically random
- **Storage**: OS Keystore (DPAPI/Keychain/libsecret)
- **Algorithm**: AES-256-GCM with authentication
- **Protection**: Forward secrecy, tamper detection
- **Status**: Production-ready, NIST-compliant

### v1.0 (INSECURE) ⚠️
- **Key**: Derived from hostname/username (predictable)
- **Storage**: File-based only
- **Algorithm**: AES-256-GCM (correct) with weak key (incorrect)
- **Protection**: Obfuscation, not encryption
- **Status**: Deprecated, migrate immediately

---

## 🎯 Common Security Tasks

### Rotate API Key (Every 90 Days)
```bash
openrouter-mcp rotate-key
```

### Backup Master Key
```bash
# Export (requires strong password)
openrouter-mcp export-key

# Save output securely offline
# Import on new machine if needed
openrouter-mcp import-key
```

### Security Audit
```bash
# Full audit report
openrouter-mcp security-audit

# Fix permission issues automatically
# (will prompt during audit if found)
```

### Delete All Credentials
```bash
openrouter-mcp delete-credentials
```

---

## 🚨 Security Red Flags

### Immediate Action Required

**🔴 v1.0 Encryption Detected**
```bash
# STOP: Do not continue using v1.0
# Action: Migrate immediately
openrouter-mcp migrate-encryption
```

**🔴 OS Keystore Not Available**
```bash
# Install keytar
npm install keytar

# Linux: Install libsecret
sudo apt-get install libsecret-1-dev  # Ubuntu/Debian
```

**🔴 Insecure File Permissions**
```bash
# Fix automatically
openrouter-mcp security-audit
# Select "Fix file permissions now?" when prompted
```

**🔴 Plaintext API Key in Config**
```bash
# Check Claude configs
cat ~/.config/Claude/claude_desktop_config.json | grep OPENROUTER_API_KEY

# If found: This is required for Claude integrations
# But ensure file permissions are 600
chmod 600 ~/.config/Claude/claude_desktop_config.json
```

---

## 📊 Security Checklist

### Daily
- [ ] Lock screen when away from computer
- [ ] Keep OS updated

### Weekly
- [ ] Run security audit: `openrouter-mcp security-audit`

### Monthly
- [ ] Review audit logs: `~/.openrouter-mcp/security-audit.log`
- [ ] Check for suspicious API usage on OpenRouter dashboard

### Every 90 Days
- [ ] Rotate API key: `openrouter-mcp rotate-key`
- [ ] Backup master key: `openrouter-mcp export-key`
- [ ] Review access logs

### After Events
- [ ] After security incident: Rotate key immediately
- [ ] After machine compromise: Delete credentials, re-initialize
- [ ] After sharing machine: Verify permissions, run audit

---

## 🔧 Troubleshooting Security Issues

### "Decryption failed"
```bash
# Check version
cat ~/.openrouter-mcp/.credentials.enc | jq '.version'

# If v1.0 and on different machine
openrouter-mcp delete-credentials
openrouter-mcp init
```

### "OS Keystore not available"
```bash
# Install keytar
npm install keytar

# Linux: Install system dependency
sudo apt-get install libsecret-1-dev
```

### "Permission denied"
```bash
# Fix permissions
chmod 700 ~/.openrouter-mcp
chmod 600 ~/.openrouter-mcp/.credentials.enc

# Or use built-in fix
openrouter-mcp security-audit
```

### "Master key not found"
```bash
# Re-initialize (will prompt for API key)
openrouter-mcp delete-credentials
openrouter-mcp init
```

---

## 📚 Additional Resources

### Documentation
- **Technical Details**: [docs/ENCRYPTION_V2.md](./ENCRYPTION_V2.md)
- **Migration Guide**: [docs/MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)
- **Full Security Guide**: [docs/SECURITY.md](./SECURITY.md)

### Testing
```bash
# Run security tests
npm run test:security

# Expected: 23/23 tests pass
```

### Support
- **Security Issues**: security@openrouter-mcp.com (private)
- **General Help**: GitHub Issues (public)
- **Documentation**: `docs/` directory

---

## ⚡ TL;DR Security Commands

```bash
# New users: Setup (2 minutes)
npm install && openrouter-mcp init

# Existing users: Migrate v1.0 → v2.0 (2 minutes)
openrouter-mcp migrate-encryption

# Security check (30 seconds)
openrouter-mcp security-audit

# Rotate API key (1 minute)
openrouter-mcp rotate-key

# Run security tests (1 minute)
npm run test:security
```

---

## 🎯 Security Priorities

### Priority 1: CRITICAL (Do Immediately)
1. Migrate from v1.0 to v2.0 if using encrypted storage
2. Install keytar for OS Keystore support
3. Run security audit and fix any critical issues

### Priority 2: HIGH (Do Within 7 Days)
1. Set up API key rotation reminder (90 days)
2. Backup master key securely offline
3. Review and fix file permissions
4. Verify all security tests pass

### Priority 3: MEDIUM (Do Within 30 Days)
1. Enable full disk encryption (OS-level)
2. Set up security monitoring/alerting
3. Document incident response procedures
4. Review access logs and API usage

### Priority 4: LOW (Do As Needed)
1. Implement key rotation automation
2. Set up centralized secrets management (enterprise)
3. Conduct security training for team
4. Regular security audits (quarterly)

---

**Last Updated**: 2025-01-18
**Version**: 1.0
**Status**: Production Ready ✅
