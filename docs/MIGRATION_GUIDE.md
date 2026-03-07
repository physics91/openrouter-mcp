# Migration Guide: Encryption v1.0 → v2.0

## Executive Summary

**CRITICAL**: If you're using encrypted credential storage (v1.0), you must migrate to v2.0 immediately.

**Why migrate?**
- v1.0 uses **obfuscation**, not encryption (security theater)
- v1.0 keys are **deterministic and predictable** (anyone can derive them)
- v2.0 uses **cryptographically secure random keys** + OS Keystore

**Time required**: 2 minutes
**Downtime**: None (credentials remain accessible during migration)
**Risk level**: Low (original files are backed up)

---

## Pre-Migration Checklist

### 1. Check Your Current Version

```bash
# Check if you have v1.0 encrypted files
ls -la ~/.openrouter-mcp/.credentials.enc

# Run security audit to see your current setup
openrouter-mcp security-audit
```

**Indicators you need to migrate**:
- ⚠️ File exists at `~/.openrouter-mcp/.credentials.enc`
- ⚠️ Security audit shows "v1.0" encryption
- ⚠️ No master key in OS Keystore

### 2. Install Required Dependencies

```bash
# Install keytar for OS Keystore integration
npm install

# Or manually
npm install keytar
```

**OS-Specific Requirements**:
- **Windows**: No additional requirements (uses DPAPI)
- **macOS**: No additional requirements (uses Keychain)
- **Linux**: Requires libsecret-1-dev
  ```bash
  # Ubuntu/Debian
  sudo apt-get install libsecret-1-dev

  # Fedora/RHEL
  sudo yum install libsecret-devel

  # Arch
  sudo pacman -S libsecret
  ```

### 3. Backup Current Credentials (Optional but Recommended)

```bash
# Backup encrypted file
cp ~/.openrouter-mcp/.credentials.enc ~/.openrouter-mcp/.credentials.enc.manual-backup

# Backup audit log
cp ~/.openrouter-mcp/security-audit.log ~/.openrouter-mcp/security-audit.log.backup
```

---

## Migration Process

### Automatic Migration (Recommended)

```bash
# Run the migration command
openrouter-mcp migrate-encryption

# Or via npm
npm run migrate
```

**What happens during migration**:

```
┌─────────────────────────────────────────────────────────┐
│ Step 1: Detect v1.0 Encrypted File                      │
│  • Read ~/.openrouter-mcp/.credentials.enc              │
│  • Verify it's v1.0 format                              │
│  • Extract encrypted data                               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Step 2: Decrypt Using v1.0 Method                       │
│  • Derive machine-specific key                          │
│  • Decrypt with legacy algorithm                        │
│  • Extract plaintext API key                            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Step 3: Generate v2.0 Master Key                        │
│  • Generate 256-bit random key                          │
│  • Store in OS Keystore (DPAPI/Keychain/libsecret)     │
│  • Save metadata                                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Step 4: Re-encrypt with v2.0                            │
│  • Encrypt plaintext with new master key               │
│  • Generate random IV                                   │
│  • Create authentication tag                            │
│  • Save with version: "2.0"                             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Step 5: Backup and Verify                               │
│  • Backup old file to .v1.backup                        │
│  • Verify decryption works                              │
│  • Confirm data integrity                               │
└─────────────────────────────────────────────────────────┘
```

### Interactive Migration Output

```
═══════════════════════════════════════════════════════════
  Encryption Migration v1.0 → v2.0
═══════════════════════════════════════════════════════════

This will migrate your encrypted credentials from v1.0 to v2.0:
  • v1.0: Deterministic key derivation (INSECURE - machine-specific)
  • v2.0: Random 256-bit master key + OS Keystore (SECURE)

⚠️  Detected v1.0 encryption format
  File: /home/user/.openrouter-mcp/.credentials.enc

? Proceed with migration to v2.0? (Y/n)

🔄 Starting migration...

  [1/4] Decrypting v1.0 credentials...
  ✓ Decryption successful
  [2/4] Generating 256-bit master key...
  ✓ Master key generated
  [3/4] Storing master key in OS Keystore...
  ✓ Master key stored securely
  [4/4] Re-encrypting with v2.0...
  ✓ Backup created: /home/user/.openrouter-mcp/.credentials.enc.v1.backup
  ✓ Migration complete!

  Verifying migration...
  ✓ Verification successful

─────────────────────────────────────────────────────────────

✅ Migration Complete!

Summary:
  • Old version: v1.0 (deterministic key)
  • New version: v2.0 (random master key + OS Keystore)
  • Backup location: /home/user/.openrouter-mcp/.credentials.enc.v1.backup
  • Master key stored in: OS Keystore

Next steps:
  1. Test decryption: openrouter-mcp start
  2. Run security audit: openrouter-mcp security-audit
  3. Delete backup once verified: rm /home/user/.openrouter-mcp/.credentials.enc.v1.backup

═══════════════════════════════════════════════════════════
```

---

## Post-Migration Verification

### 1. Test Decryption

```bash
# Start the server to verify credentials work
openrouter-mcp start

# Should see:
# ✓ OpenRouter API Key: Configured
# ✓ Using v2.0 encryption
```

### 2. Run Security Audit

```bash
openrouter-mcp security-audit
```

**Expected output**:
```
Security Audit
═══════════════════════════════════════════════════════════

Credential Storage:

  ✓ OS Keychain: Master key found (v2.0)
  ✓ Encrypted File: API key found (AES-256-GCM v2.0)
    Masked key: sk-or-v1...abcd
    Encryption: AES-256-GCM with OS Keystore

Environment Analysis:

  ✓ Environment: Single-user

Summary:

  Good Practices (3):
    ✓ Using v2.0 encryption with OS Keystore
    ✓ Master key stored securely
    ✓ Authentication tags enabled
```

### 3. Run Security Tests

```bash
npm run test:security
```

**Expected**: All 23 tests should pass

---

## Troubleshooting

### Issue 1: "OS Keystore not available"

**Symptom**:
```
✗ OS Keystore not available
⚠️  v2.0 requires keytar for OS Keystore integration
```

**Solution**:
```bash
# Install keytar
npm install keytar

# Linux: Install libsecret
sudo apt-get install libsecret-1-dev  # Ubuntu/Debian
sudo yum install libsecret-devel      # Fedora/RHEL
```

### Issue 2: "Failed to decrypt v1.0 credentials"

**Symptom**:
```
✗ Failed to decrypt v1.0 credentials
  Error: Decryption failed: Unsupported state or unable to authenticate data
```

**Cause**: Credentials encrypted on different machine (hostname/username mismatch)

**Solution**:
```bash
# Option 1: Delete and re-initialize
openrouter-mcp delete-credentials
openrouter-mcp init

# Option 2: Use environment variable temporarily
export OPENROUTER_API_KEY="sk-or-v1-your-key"
openrouter-mcp init
```

### Issue 3: "Migration verification failed"

**Symptom**:
```
✗ Migration failed: Verification failed - decrypted data does not match
```

**Solution**:
```bash
# Restore from backup
cp ~/.openrouter-mcp/.credentials.enc.v1.backup ~/.openrouter-mcp/.credentials.enc

# Report issue with logs
openrouter-mcp security-audit > audit.log
# Share audit.log with support
```

### Issue 4: "Permission denied" (Linux)

**Symptom**:
```
Error: Permission denied: /home/user/.openrouter-mcp/.credentials.enc
```

**Solution**:
```bash
# Fix permissions
chmod 700 ~/.openrouter-mcp
chmod 600 ~/.openrouter-mcp/.credentials.enc

# Or use built-in fix
openrouter-mcp security-audit
# Then select "Fix file permissions now?"
```

### Issue 5: Windows DPAPI Access Denied

**Symptom**:
```
Error: Failed to store master key: Access denied
```

**Solution**:
```bash
# Run as administrator
# OR
# Use encrypted file storage instead (still secure, but without OS Keystore)
```

---

## Manual Migration (Advanced)

If automatic migration fails, you can migrate manually:

### Step 1: Export Current API Key

```bash
# Option A: From environment
echo $OPENROUTER_API_KEY

# Option B: Decrypt manually (Node.js)
node -e "
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');

const file = fs.readFileSync(os.homedir() + '/.openrouter-mcp/.credentials.enc', 'utf8');
const data = JSON.parse(file);

const machineId = os.hostname() + os.userInfo().username + os.platform() + os.arch();
const key = crypto.createHash('sha256').update(machineId).digest();

const decipher = crypto.createDecipheriv('aes-256-gcm', key, Buffer.from(data.iv, 'hex'));
decipher.setAuthTag(Buffer.from(data.authTag, 'hex'));

let decrypted = decipher.update(data.encrypted, 'hex', 'utf8');
decrypted += decipher.final('utf8');

console.log('API Key:', decrypted);
"
```

### Step 2: Delete Old Credentials

```bash
openrouter-mcp delete-credentials
```

### Step 3: Re-initialize with v2.0

```bash
# Will automatically use v2.0
openrouter-mcp init

# When prompted, enter your API key
```

---

## Rollback (If Needed)

If you need to rollback to v1.0 (not recommended):

```bash
# Restore backup
cp ~/.openrouter-mcp/.credentials.enc.v1.backup ~/.openrouter-mcp/.credentials.enc

# Delete master key from OS Keystore
node -e "
const keytar = require('keytar');
keytar.deletePassword('openrouter-mcp-v2', 'master-encryption-key');
"

# Verify v1.0 works
openrouter-mcp start
```

**WARNING**: v1.0 is insecure. Only rollback temporarily, then re-migrate.

---

## Migration Checklist

- [ ] Backup current credentials (optional)
- [ ] Install keytar: `npm install keytar`
- [ ] Linux only: Install libsecret
- [ ] Run migration: `openrouter-mcp migrate-encryption`
- [ ] Verify migration: `openrouter-mcp start`
- [ ] Run security audit: `openrouter-mcp security-audit`
- [ ] Test application functionality
- [ ] Delete backup after 7 days: `rm ~/.openrouter-mcp/.credentials.enc.v1.backup`
- [ ] Document master key location (OS Keystore)
- [ ] Set up key rotation reminder (90 days)

---

## Migration for Multiple Machines

If you use OpenRouter MCP on multiple machines:

### Option 1: Migrate Each Machine Independently

```bash
# Machine 1
openrouter-mcp migrate-encryption

# Machine 2
openrouter-mcp migrate-encryption

# Each machine gets its own master key
```

### Option 2: Re-initialize Credentials on the New Machine

The current CLI does not provide `export-key` or `import-key` commands.
If you move to a new machine, initialize secure storage there and register the API key again.

**Security Note**: Option 1 is more secure (separate keys per machine)

---

## FAQ

### Q: Do I need to migrate immediately?

**A**: **YES**. v1.0 is fundamentally insecure. Anyone with filesystem access can derive your encryption key from predictable machine data. Migrate as soon as possible.

### Q: Will migration delete my API key?

**A**: No. Migration backs up your v1.0 file and only replaces it after successful verification. Your API key remains accessible throughout.

### Q: What if I'm using multiple storage methods?

**A**: Migration only affects encrypted file storage. If you use OS Keychain, .env files, or config files, those are unaffected.

### Q: Can I migrate on a different machine?

**A**: No. v1.0 keys are machine-specific. You must migrate on the same machine where credentials were encrypted. On a different machine, initialize secure storage again and re-enter the API key.

### Q: How do I verify my encryption version?

```bash
# Check version in encrypted file
cat ~/.openrouter-mcp/.credentials.enc | jq '.version'

# Output:
# "2.0" = secure
# "1.0" or null = insecure (migrate now)
```

### Q: What happens to my old v1.0 backup?

**A**: It's kept as `.credentials.enc.v1.backup`. You can safely delete it after verifying v2.0 works (recommend waiting 7 days).

### Q: Can I skip migration and keep using v1.0?

**A**: **Technically yes, but strongly discouraged**. v1.0 will continue to work but provides no real security. You'll see warnings in security audits.

---

## Support

**Migration Issues**:
- Check troubleshooting section above
- Run: `openrouter-mcp security-audit` and share output
- Open GitHub issue with error logs

**Security Concerns**:
- Email: security@openrouter-mcp.com
- Include: OS, Node version, error messages

**General Help**:
- Documentation: `docs/ENCRYPTION_V2.md`
- Security guide: `docs/SECURITY.md`

---

**Migration Version**: 1.0
**Last Updated**: 2025-01-18
**Recommended**: Migrate within 7 days of v2.0 release
