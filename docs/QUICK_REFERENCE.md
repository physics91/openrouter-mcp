# Secure Credential Storage - Quick Reference

## What Changed?

**File:** `bin/openrouter-mcp.js`

**Functions Modified:**
1. `checkApiKey()` - Lines 158-170
2. `startServer()` - Lines 172-231

**What it does now:**
- ✅ Retrieves API keys from OS Keychain
- ✅ Retrieves API keys from encrypted files
- ✅ Falls back to .env files
- ✅ Shows masked keys for security
- ✅ Logs all access for audit trail
- ✅ Provides helpful user guidance

---

## Quick Test

```bash
# Test the integration
node tests/test-secure-integration.js

# Start the server (will now use secure storage)
openrouter-mcp start
```

---

## Expected Behavior

### With OS Keychain
```bash
$ openrouter-mcp start
🔑 Retrieving API key from secure storage...
✓ API key loaded from keychain
  Masked key: sk-or-v1...abc4
Starting server on localhost:8000
```

### With Encrypted File
```bash
$ openrouter-mcp start
🔑 Retrieving API key from secure storage...
✓ API key loaded from encrypted-file
  Masked key: sk-or-v1...xyz9
Starting server on localhost:8000
```

### With .env File (Backward Compatible)
```bash
$ openrouter-mcp start
🔑 Retrieving API key from secure storage...
✓ API key loaded from env-file
  Masked key: sk-or-v1...def5
Starting server on localhost:8000
```

### Environment Variable Override
```bash
$ OPENROUTER_API_KEY=sk-or-custom openrouter-mcp start
✓ Using API key from environment variable
  Masked key: sk-or-cu...stom
Starting server on localhost:8000
```

### No Credentials
```bash
$ openrouter-mcp start
🔑 Retrieving API key from secure storage...
⚠️  No API key found in secure storage
💡 To configure API key, run: openrouter-mcp init
   Server will start but API calls will fail without a valid key

Starting server on localhost:8000
```

---

## Code Changes Summary

### Before
```javascript
async function checkApiKey() {
  // Manually scanned .env files only
  // Did not use secure storage
}

async function startServer(options) {
  // Started server without retrieving credentials
  // Secure storage system was unused
}
```

### After
```javascript
async function checkApiKey() {
  // Uses secureCredentials.getApiKey()
  // Checks all storage locations
  // Shows masked key and source
}

async function startServer(options) {
  // Retrieves from secure storage automatically
  // Populates env.OPENROUTER_API_KEY
  // Audit logging + user guidance
}
```

---

## Storage Priority

The system checks sources in this order:

1. **Environment variable** (`OPENROUTER_API_KEY`)
   - Takes precedence (allows overrides)
   - Most flexible for CI/CD

2. **OS Keychain** (macOS Keychain, Windows Credential Manager, Linux Secret Service)
   - Most secure
   - Encrypted at rest
   - Requires `keytar` package

3. **Encrypted file** (`~/.openrouter-mcp/.credentials.enc`)
   - Machine-specific encryption
   - AES-256-GCM with OS Keystore
   - Good for CI/CD

4. **.env file** (multiple locations)
   - Backward compatibility
   - Least secure (plaintext)
   - Still supported

---

## Security Features

| Feature | Status |
|---------|--------|
| OS Keychain integration | ✅ Active |
| Encrypted file support | ✅ Active |
| API key masking | ✅ Active |
| Audit logging | ✅ Active |
| Source transparency | ✅ Active |
| .env backward compat | ✅ Active |
| Environment override | ✅ Active |

---

## Documentation

- **Full details:** `SECURE_STORAGE_INTEGRATION.md`
- **Migration:** `MIGRATION_GUIDE.md`
- **Encryption internals:** `ENCRYPTION_V2.md`
- **Security:** `SECURITY.md`
- **Best practices:** `SECURITY_BEST_PRACTICES.md`

---

## Commands

```bash
# Initialize with secure storage
openrouter-mcp init

# Start server (uses secure storage)
openrouter-mcp start

# Check configuration
openrouter-mcp status

# Run security audit
openrouter-mcp security-audit

# Rotate API key
openrouter-mcp rotate-key

# Delete all credentials
openrouter-mcp delete-credentials

# Test integration
node tests/test-secure-integration.js
```

---

## For Developers

### Pattern Used
```javascript
// Standard pattern for retrieving credentials
const keyResult = await secureCredentials.getApiKey();

if (keyResult.key) {
  // Use the key
  env.OPENROUTER_API_KEY = keyResult.key;

  // Show masked version
  const masked = secureCredentials.maskApiKey(keyResult.key);
  console.log(`Loaded from ${keyResult.source}: ${masked}`);

  // Audit log
  secureCredentials.auditLog('event-name', { source: keyResult.source });
} else {
  // Handle missing key
  console.log('No API key found. Run init.');
}
```

### Return Value
```javascript
{
  key: "sk-or-v1-...",  // The actual API key (or null)
  source: "keychain"     // Where it came from
}
```

### Possible Sources
- `"environment-variable"` - From `process.env.OPENROUTER_API_KEY`
- `"keychain"` - From OS Keychain
- `"encrypted-file"` - From encrypted file storage
- `"env-file"` - From .env file

---

## Troubleshooting

### "No API key found"
```bash
# Run initialization wizard
openrouter-mcp init
```

### "Failed to decrypt credentials"
```bash
# May need migration from v1.0 to v2.0
openrouter-mcp migrate-encryption
```

### "OS Keychain not available"
```bash
# Install keytar for OS Keychain support
npm install keytar
```

### "Permission denied"
```bash
# Fix file permissions
openrouter-mcp security-audit
# Follow prompts to fix permissions automatically
```

---

## Audit Log

All credential access is logged to:
```
~/.openrouter-mcp/security-audit.log
```

Log entries include:
- Timestamp
- Event type
- User
- Hostname
- Source storage method

Example:
```json
{
  "timestamp": "2025-01-18T10:30:00.000Z",
  "event": "key-loaded-for-server",
  "user": "john",
  "hostname": "macbook-pro",
  "platform": "darwin",
  "source": "keychain"
}
```

---

## Backward Compatibility

✅ **All existing configurations work without changes**

- .env files continue to work
- Environment variables take precedence
- No breaking changes
- Gradual migration path available

---

## Next Steps

1. **Test the integration:**
   ```bash
   node tests/test-secure-integration.js
   ```

2. **Configure secure storage:**
   ```bash
   openrouter-mcp init
   ```

3. **Start the server:**
   ```bash
   openrouter-mcp start
   ```

4. **Run security audit:**
   ```bash
   openrouter-mcp security-audit
   ```

5. **Review documentation:**
   - Read `SECURE_STORAGE_INTEGRATION.md`
   - Check `SECURITY.md`
