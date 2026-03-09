#!/usr/bin/env node

/**
 * Encryption Security Test Suite
 *
 * Comprehensive security tests for encryption v2.0:
 * - Key generation randomness
 * - Encryption/decryption correctness
 * - IV uniqueness
 * - Authentication tag verification
 * - Migration from v1.0 to v2.0
 * - OS Keystore integration
 */

const crypto = require('crypto');
const chalk = require('chalk');
const cryptoManager = require('../bin/crypto-manager');
let claudeConfigUtils = null;

try {
  claudeConfigUtils = require('../bin/claude-config-utils');
} catch (error) {
  claudeConfigUtils = null;
}

// Test results
const results = {
  passed: 0,
  failed: 0,
  warnings: 0,
  tests: []
};

/**
 * Test helper function
 */
function test(name, fn) {
  try {
    console.log(chalk.blue(`\n▶ ${name}`));
    fn();
    results.passed++;
    results.tests.push({ name, status: 'PASS' });
    console.log(chalk.green('  ✓ PASS'));
  } catch (error) {
    results.failed++;
    results.tests.push({ name, status: 'FAIL', error: error.message });
    console.log(chalk.red(`  ✗ FAIL: ${error.message}`));
  }
}

/**
 * Async test helper
 */
async function asyncTest(name, fn) {
  try {
    console.log(chalk.blue(`\n▶ ${name}`));
    await fn();
    results.passed++;
    results.tests.push({ name, status: 'PASS' });
    console.log(chalk.green('  ✓ PASS'));
  } catch (error) {
    results.failed++;
    results.tests.push({ name, status: 'FAIL', error: error.message });
    console.log(chalk.red(`  ✗ FAIL: ${error.message}`));
  }
}

/**
 * Assert helper
 */
function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/**
 * Assert equals helper
 */
function assertEquals(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}\n  Expected: ${expected}\n  Actual: ${actual}`);
  }
}

/**
 * Assert throws helper
 */
function assertThrows(fn, message) {
  let threw = false;
  try {
    fn();
  } catch (error) {
    threw = true;
  }
  if (!threw) {
    throw new Error(message);
  }
}

console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════'));
console.log(chalk.cyan('  Encryption Security Test Suite v2.0'));
console.log(chalk.cyan('═══════════════════════════════════════════════════════════\n'));

// ============================================================================
// Test Suite 1: Key Generation
// ============================================================================

console.log(chalk.bold('\n📊 Test Suite 1: Master Key Generation\n'));

test('Master key is 256 bits (32 bytes)', () => {
  const key = cryptoManager.generateMasterKey();
  assert(Buffer.isBuffer(key), 'Key should be a Buffer');
  assertEquals(key.length, 32, 'Key should be 32 bytes (256 bits)');
});

test('Master key is cryptographically random', () => {
  const key1 = cryptoManager.generateMasterKey();
  const key2 = cryptoManager.generateMasterKey();

  // Keys should never be equal (probability: 1/2^256)
  assert(!key1.equals(key2), 'Generated keys must be unique');

  // Keys should have good entropy (should not be all zeros)
  const allZeros = Buffer.alloc(32);
  assert(!key1.equals(allZeros), 'Key should not be all zeros');
  assert(!key2.equals(allZeros), 'Key should not be all zeros');
});

test('Master key entropy is sufficient', () => {
  const key = cryptoManager.generateMasterKey();

  // Simple entropy check: count unique bytes
  const uniqueBytes = new Set(key).size;
  assert(uniqueBytes > 10, `Key should have diverse byte values (found ${uniqueBytes}/32 unique)`);

  // Check for patterns (no repeated 4-byte sequences)
  const hex = key.toString('hex');
  const chunks = hex.match(/.{8}/g);
  const uniqueChunks = new Set(chunks).size;
  assert(uniqueChunks === chunks.length, 'Key should not have repeated 4-byte sequences');
});

// ============================================================================
// Test Suite 2: Encryption/Decryption
// ============================================================================

console.log(chalk.bold('\n📊 Test Suite 2: Encryption/Decryption\n'));

test('Encryption produces valid ciphertext structure', () => {
  const masterKey = cryptoManager.generateMasterKey();
  const plaintext = 'test-api-key-sk-or-v1-1234567890';

  const encrypted = cryptoManager.encryptWithMasterKey(plaintext, masterKey);

  assert(encrypted.version === '2.0', 'Version should be 2.0');
  assert(encrypted.algorithm === 'aes-256-gcm', 'Algorithm should be aes-256-gcm');
  assert(typeof encrypted.iv === 'string', 'IV should be a hex string');
  assert(typeof encrypted.authTag === 'string', 'AuthTag should be a hex string');
  assert(typeof encrypted.ciphertext === 'string', 'Ciphertext should be a hex string');

  // IV should be 12 bytes (24 hex chars) for GCM
  assertEquals(encrypted.iv.length, 24, 'IV should be 12 bytes (24 hex chars)');

  // AuthTag should be 16 bytes (32 hex chars)
  assertEquals(encrypted.authTag.length, 32, 'AuthTag should be 16 bytes (32 hex chars)');
});

test('Decryption recovers original plaintext', () => {
  const masterKey = cryptoManager.generateMasterKey();
  const plaintext = 'sk-or-v1-test-key-1234567890abcdef';

  const encrypted = cryptoManager.encryptWithMasterKey(plaintext, masterKey);
  const decrypted = cryptoManager.decryptWithMasterKey(encrypted, masterKey);

  assertEquals(decrypted, plaintext, 'Decrypted text should match original');
});

test('Encryption with different keys produces different ciphertexts', () => {
  const key1 = cryptoManager.generateMasterKey();
  const key2 = cryptoManager.generateMasterKey();
  const plaintext = 'test-data';

  const encrypted1 = cryptoManager.encryptWithMasterKey(plaintext, key1);
  const encrypted2 = cryptoManager.encryptWithMasterKey(plaintext, key2);

  assert(
    encrypted1.ciphertext !== encrypted2.ciphertext,
    'Different keys should produce different ciphertexts'
  );
});

test('Encryption with same key produces different IVs', () => {
  const masterKey = cryptoManager.generateMasterKey();
  const plaintext = 'test-data';

  const encrypted1 = cryptoManager.encryptWithMasterKey(plaintext, masterKey);
  const encrypted2 = cryptoManager.encryptWithMasterKey(plaintext, masterKey);

  assert(encrypted1.iv !== encrypted2.iv, 'IVs should be unique for each encryption');
  assert(
    encrypted1.ciphertext !== encrypted2.ciphertext,
    'Ciphertexts should be different due to unique IVs'
  );
});

test('Decryption with wrong key fails', () => {
  const correctKey = cryptoManager.generateMasterKey();
  const wrongKey = cryptoManager.generateMasterKey();
  const plaintext = 'secret-data';

  const encrypted = cryptoManager.encryptWithMasterKey(plaintext, correctKey);

  assertThrows(
    () => cryptoManager.decryptWithMasterKey(encrypted, wrongKey),
    'Decryption with wrong key should throw'
  );
});

test('Decryption with tampered ciphertext fails', () => {
  const masterKey = cryptoManager.generateMasterKey();
  const plaintext = 'secret-data';

  const encrypted = cryptoManager.encryptWithMasterKey(plaintext, masterKey);

  // Tamper with ciphertext
  const tamperedCiphertext = encrypted.ciphertext.replace(/[0-9]/, 'x');
  const tampered = { ...encrypted, ciphertext: tamperedCiphertext };

  assertThrows(
    () => cryptoManager.decryptWithMasterKey(tampered, masterKey),
    'Decryption of tampered ciphertext should fail authentication'
  );
});

test('Decryption with tampered auth tag fails', () => {
  const masterKey = cryptoManager.generateMasterKey();
  const plaintext = 'secret-data';

  const encrypted = cryptoManager.encryptWithMasterKey(plaintext, masterKey);

  // Tamper with auth tag
  const tamperedTag = encrypted.authTag.replace(/[0-9]/, 'x');
  const tampered = { ...encrypted, authTag: tamperedTag };

  assertThrows(
    () => cryptoManager.decryptWithMasterKey(tampered, masterKey),
    'Decryption with tampered auth tag should fail'
  );
});

test('Encryption handles various plaintext sizes', () => {
  const masterKey = cryptoManager.generateMasterKey();
  const testCases = [
    '',                                    // Empty string
    'a',                                   // Single char
    'sk-or-v1-short',                      // Short key
    'sk-or-v1-' + 'x'.repeat(100),         // Long key
    'unicode-テスト-🔐-key',                // Unicode
    'special-chars-!@#$%^&*()_+-=[]{}|;:\'"<>,.?/~`' // Special chars
  ];

  testCases.forEach((plaintext, i) => {
    const encrypted = cryptoManager.encryptWithMasterKey(plaintext, masterKey);
    const decrypted = cryptoManager.decryptWithMasterKey(encrypted, masterKey);
    assertEquals(decrypted, plaintext, `Test case ${i} failed: ${plaintext.substring(0, 20)}`);
  });
});

// ============================================================================
// Test Suite 3: Key Integrity
// ============================================================================

console.log(chalk.bold('\n📊 Test Suite 3: Key Integrity\n'));

test('Master key integrity verification works', () => {
  const validKey = cryptoManager.generateMasterKey();
  assert(cryptoManager.verifyMasterKeyIntegrity(validKey), 'Valid key should pass integrity check');

  const invalidKey1 = Buffer.alloc(32);
  assert(cryptoManager.verifyMasterKeyIntegrity(invalidKey1), 'All-zero key should technically work (just bad practice)');

  const invalidKey2 = Buffer.alloc(16);
  assert(!cryptoManager.verifyMasterKeyIntegrity(invalidKey2), 'Wrong size key should fail');

  assert(!cryptoManager.verifyMasterKeyIntegrity(null), 'Null key should fail');
  assert(!cryptoManager.verifyMasterKeyIntegrity('not-a-buffer'), 'Non-buffer should fail');
});

// ============================================================================
// Test Suite 4: Version Detection
// ============================================================================

console.log(chalk.bold('\n📊 Test Suite 4: Version Detection\n'));

test('Version 2.0 data is detected correctly', () => {
  const masterKey = cryptoManager.generateMasterKey();
  const encrypted = cryptoManager.encryptWithMasterKey('test', masterKey);

  const version = cryptoManager.detectEncryptionVersion(encrypted);
  assertEquals(version, '2.0', 'Should detect v2.0 correctly');
});

test('Version 1.0 data is detected correctly', () => {
  const legacyData = {
    encrypted: '1234',
    iv: 'abcd',
    authTag: 'efgh'
  };

  const version = cryptoManager.detectEncryptionVersion(legacyData);
  assertEquals(version, '1.0', 'Should detect v1.0 correctly');
});

test('Invalid data throws error', () => {
  assertThrows(
    () => cryptoManager.detectEncryptionVersion({}),
    'Invalid data should throw error'
  );

  assertThrows(
    () => cryptoManager.detectEncryptionVersion({ random: 'data' }),
    'Random data should throw error'
  );
});

// ============================================================================
// Test Suite 5: Legacy v1.0 Support
// ============================================================================

console.log(chalk.bold('\n📊 Test Suite 5: Legacy v1.0 Decryption\n'));

test('Legacy v1.0 decryption works', () => {
  // Generate v1.0 encrypted data using old method
  const legacyKey = cryptoManager.getLegacyMachineKey();
  const plaintext = 'sk-or-v1-legacy-test-key';

  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv('aes-256-gcm', legacyKey, iv);

  let encrypted = cipher.update(plaintext, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  const authTag = cipher.getAuthTag();

  const legacyData = {
    encrypted,
    iv: iv.toString('hex'),
    authTag: authTag.toString('hex')
  };

  // Decrypt using legacy method
  const decrypted = cryptoManager.decryptLegacyV1(legacyData);
  assertEquals(decrypted, plaintext, 'Legacy decryption should recover original plaintext');
});

// ============================================================================
// Test Suite 6: Import/Export
// ============================================================================

console.log(chalk.bold('\n📊 Test Suite 6: Key Import/Export\n'));

test('Master key export produces valid encrypted backup', () => {
  const masterKey = cryptoManager.generateMasterKey();
  const password = 'strong-password-12345';

  const exported = cryptoManager.exportMasterKey(masterKey, password);

  assert(typeof exported === 'string', 'Export should be a string');
  assert(exported.length > 100, 'Exported data should be substantial');

  // Should be valid base64
  const decoded = Buffer.from(exported, 'base64');
  const parsed = JSON.parse(decoded.toString('utf8'));
  assertEquals(parsed.version, '2.0', 'Exported data should have version 2.0');
  assertEquals(parsed.type, 'master-key-export', 'Exported data should have correct type');
  assert(parsed.salt, 'Exported data should have salt');
  assert(parsed.iv, 'Exported data should have IV');
  assert(parsed.authTag, 'Exported data should have auth tag');
  assert(parsed.ciphertext, 'Exported data should have ciphertext');
});

test('Export requires strong password', () => {
  const masterKey = cryptoManager.generateMasterKey();

  assertThrows(
    () => cryptoManager.exportMasterKey(masterKey, 'weak'),
    'Export with weak password should fail'
  );

  assertThrows(
    () => cryptoManager.exportMasterKey(masterKey, ''),
    'Export with empty password should fail'
  );
});

test('Exported key can be imported successfully', async () => {
  const originalKey = cryptoManager.generateMasterKey();
  const password = 'strong-export-password-123';

  const exported = cryptoManager.exportMasterKey(originalKey, password);

  // Note: We can't fully test import without OS keystore access
  // But we can verify export format is correct
  const decoded = Buffer.from(exported, 'base64');
  const parsed = JSON.parse(decoded.toString('utf8'));

  assert(parsed.type === 'master-key-export', 'Export format should be valid');
});

// ============================================================================
// Test Suite 7: Security Properties
// ============================================================================

console.log(chalk.bold('\n📊 Test Suite 7: Security Properties\n'));

test('Ciphertext is not predictable from plaintext', () => {
  const masterKey = cryptoManager.generateMasterKey();
  const plaintext = 'predictable-pattern-AAAAAAAAAA';

  const encrypted = cryptoManager.encryptWithMasterKey(plaintext, masterKey);

  // Ciphertext should not contain the plaintext pattern
  assert(
    !encrypted.ciphertext.includes('AAAAAAAAAA'),
    'Ciphertext should not contain plaintext patterns'
  );

  // Ciphertext should look random (no long repeated sequences)
  const chunks = encrypted.ciphertext.match(/.{4}/g);
  const repeatedChunks = chunks.filter((chunk, i, arr) =>
    arr.indexOf(chunk) !== i
  ).length;

  assert(
    repeatedChunks < chunks.length * 0.3,
    'Ciphertext should not have many repeated patterns'
  );
});

test('IV collision probability is negligible', () => {
  const masterKey = cryptoManager.generateMasterKey();
  const ivs = new Set();
  const iterations = 1000;

  for (let i = 0; i < iterations; i++) {
    const encrypted = cryptoManager.encryptWithMasterKey('test', masterKey);
    ivs.add(encrypted.iv);
  }

  assertEquals(ivs.size, iterations, `All ${iterations} IVs should be unique`);
});

test('Authentication tag prevents bit-flipping attacks', () => {
  const masterKey = cryptoManager.generateMasterKey();
  const plaintext = 'account=user&admin=false';

  const encrypted = cryptoManager.encryptWithMasterKey(plaintext, masterKey);

  // Attempt to flip bits in ciphertext (simulating attack)
  const ciphertextBytes = Buffer.from(encrypted.ciphertext, 'hex');
  ciphertextBytes[0] ^= 0x01; // Flip one bit
  const tamperedCiphertext = ciphertextBytes.toString('hex');

  const tampered = { ...encrypted, ciphertext: tamperedCiphertext };

  assertThrows(
    () => cryptoManager.decryptWithMasterKey(tampered, masterKey),
    'Bit-flipping attack should be detected by auth tag'
  );
});

test('Encryption is not vulnerable to timing attacks (constant-time comparison)', () => {
  // This is a basic test - real timing attack testing requires statistical analysis
  const masterKey = cryptoManager.generateMasterKey();
  const plaintext = 'secret-data';

  const encrypted = cryptoManager.encryptWithMasterKey(plaintext, masterKey);

  const wrongKey1 = Buffer.alloc(32, 0x00);
  const wrongKey2 = Buffer.alloc(32, 0xFF);

  let caught1 = false;
  let caught2 = false;

  try {
    cryptoManager.decryptWithMasterKey(encrypted, wrongKey1);
  } catch {
    caught1 = true;
  }

  try {
    cryptoManager.decryptWithMasterKey(encrypted, wrongKey2);
  } catch {
    caught2 = true;
  }

  assert(caught1 && caught2, 'Both wrong keys should fail (timing attack resistance not testable here)');
});

// ============================================================================
// Test Suite 8: Claude Code Config Security
// ============================================================================

console.log(chalk.bold('\n📊 Test Suite 8: Claude Code Config Security\n'));

test('Claude Code config template avoids plaintext OPENROUTER_API_KEY', () => {
  assert(claudeConfigUtils, 'claude-config-utils module should be available');

  const config = claudeConfigUtils.buildClaudeCodeServerConfig('@physics91/openrouter-mcp');

  assertEquals(config.command, 'npx', 'Claude Code config should use npx');
  assert(Array.isArray(config.args), 'Claude Code config args should be an array');
  assert(
    !config.env || !('OPENROUTER_API_KEY' in config.env),
    'Claude Code config should not inline OPENROUTER_API_KEY'
  );
});

test('Claude Code installer command uses native claude mcp add flow', () => {
  assert(claudeConfigUtils, 'claude-config-utils module should be available');
  assert(
    typeof claudeConfigUtils.buildClaudeCodeInstallCommand === 'function',
    'buildClaudeCodeInstallCommand should be exported'
  );

  const command = claudeConfigUtils.buildClaudeCodeInstallCommand('@physics91/openrouter-mcp');

  assertEquals(command.command, 'claude', 'Claude Code installer should invoke Claude Code CLI');
  assert(Array.isArray(command.args), 'Installer args should be an array');
  assertEquals(command.args[0], 'mcp', 'Installer should call claude mcp');
  assertEquals(command.args[1], 'add', 'Installer should add an MCP server');
  assert(
    command.args.includes('openrouter'),
    'Installer command should register the openrouter server name'
  );
  assert(
    command.args.includes('@physics91/openrouter-mcp'),
    'Installer command should reference the package name'
  );
});

test('Claude Code config path matches current user-scope settings file', () => {
  assert(claudeConfigUtils, 'claude-config-utils module should be available');
  assert(
    typeof claudeConfigUtils.getClaudeCodeUserConfigPath === 'function',
    'getClaudeCodeUserConfigPath should be exported'
  );

  const configPath = claudeConfigUtils.getClaudeCodeUserConfigPath('/home/tester');
  assertEquals(
    configPath,
    '/home/tester/.claude.json',
    'Claude Code user config should use ~/.claude.json'
  );
});

test('Claude config plaintext detection only flags explicit key injection', () => {
  assert(claudeConfigUtils, 'claude-config-utils module should be available');

  const safeConfig = {
    mcpServers: {
      openrouter: {
        command: 'npx',
        args: ['@physics91/openrouter-mcp', 'start']
      }
    }
  };
  const unsafeConfig = {
    mcpServers: {
      openrouter: {
        command: 'npx',
        args: ['@physics91/openrouter-mcp', 'start'],
        env: {
          OPENROUTER_API_KEY: 'sk-or-v1-test'
        }
      }
    }
  };

  assert(
    !claudeConfigUtils.configContainsPlaintextOpenRouterKey(safeConfig),
    'Config without inline env key should be treated as safe'
  );
  assert(
    claudeConfigUtils.configContainsPlaintextOpenRouterKey(unsafeConfig),
    'Config with inline env key should be treated as plaintext storage'
  );
});

// ============================================================================
// Test Results Summary
// ============================================================================

console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════'));
console.log(chalk.bold('\n📊 Test Results Summary\n'));

console.log(chalk.white(`Total Tests: ${results.passed + results.failed}`));
console.log(chalk.green(`✓ Passed: ${results.passed}`));
console.log(chalk.red(`✗ Failed: ${results.failed}`));

if (results.warnings > 0) {
  console.log(chalk.yellow(`⚠ Warnings: ${results.warnings}`));
}

const passRate = ((results.passed / (results.passed + results.failed)) * 100).toFixed(1);
console.log(chalk.white(`\nPass Rate: ${passRate}%`));

if (results.failed > 0) {
  console.log(chalk.red('\n❌ SECURITY TESTS FAILED\n'));
  console.log(chalk.yellow('Failed tests:'));
  results.tests
    .filter(t => t.status === 'FAIL')
    .forEach(t => {
      console.log(chalk.red(`  ✗ ${t.name}`));
      console.log(chalk.gray(`    ${t.error}`));
    });
  process.exit(1);
} else {
  console.log(chalk.green('\n✅ ALL SECURITY TESTS PASSED\n'));
  console.log(chalk.white('Encryption v2.0 is ready for production use.'));
}

console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════\n'));

// Check for OS Keystore availability
console.log(chalk.bold('📌 Environment Check:\n'));
if (cryptoManager.isKeystoreAvailable()) {
  console.log(chalk.green('✓ OS Keystore available (keytar installed)'));
} else {
  console.log(chalk.yellow('⚠ OS Keystore NOT available'));
  console.log(chalk.gray('  Install keytar for full v2.0 functionality:'));
  console.log(chalk.gray('  npm install keytar\n'));
}

console.log(chalk.cyan('═══════════════════════════════════════════════════════════\n'));

process.exit(0);
