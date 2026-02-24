#!/usr/bin/env node

/**
 * Crypto Manager v2.0 - Secure Encryption System
 *
 * Implements cryptographically secure key management with:
 * - 256-bit random master keys (crypto.randomBytes)
 * - OS Keystore integration (Windows DPAPI, macOS Keychain, Linux libsecret)
 * - AES-256-GCM encryption with random IVs
 * - Authentication tag verification
 * - Version detection for migration
 *
 * SECURITY: This replaces the weak deterministic key derivation (v1.0)
 * with proper cryptographic primitives.
 */

const crypto = require('crypto');
const os = require('os');
const path = require('path');
const fs = require('fs');
const chalk = require('chalk');

// Platform-specific keystore implementations
let keytar = null;
let keytarAvailable = false;

try {
  keytar = require('keytar');
  keytarAvailable = true;
} catch (error) {
  keytarAvailable = false;
}

// Service identifiers
const SERVICE_NAME = 'openrouter-mcp-v2';
const MASTER_KEY_ACCOUNT = 'master-encryption-key';

// Configuration
const CONFIG_DIR = path.join(os.homedir(), '.openrouter-mcp');
const MASTER_KEY_FILE = path.join(CONFIG_DIR, '.master-key.enc');
const KEY_METADATA_FILE = path.join(CONFIG_DIR, '.key-metadata.json');

/**
 * Encryption versions
 */
const EncryptionVersion = {
  V1_0: '1.0', // Legacy: deterministic key derivation (INSECURE)
  V2_0: '2.0'  // Secure: random master key + OS keystore
};

/**
 * Generate a cryptographically secure 256-bit master key
 * @returns {Buffer} 32-byte random key
 */
function generateMasterKey() {
  return crypto.randomBytes(32);
}

/**
 * Store master key securely in OS keystore
 * @param {Buffer} masterKey - 32-byte master key
 * @returns {Promise<boolean>} Success status
 */
async function storeMasterKeySecurely(masterKey) {
  if (!keytarAvailable) {
    throw new Error('OS Keystore not available. Install keytar: npm install keytar');
  }

  try {
    // Convert Buffer to base64 for storage
    const keyBase64 = masterKey.toString('base64');

    // Store in OS keystore
    await keytar.setPassword(SERVICE_NAME, MASTER_KEY_ACCOUNT, keyBase64);

    // Store metadata
    const metadata = {
      version: EncryptionVersion.V2_0,
      created: new Date().toISOString(),
      algorithm: 'AES-256-GCM',
      keyLength: 32,
      platform: os.platform(),
      hostname: os.hostname()
    };

    ensureConfigDirectory();
    fs.writeFileSync(
      KEY_METADATA_FILE,
      JSON.stringify(metadata, null, 2),
      { mode: 0o600 }
    );

    console.log(chalk.green('✓ Master key stored securely in OS Keystore'));
    return true;
  } catch (error) {
    throw new Error(`Failed to store master key: ${error.message}`);
  }
}

/**
 * Retrieve master key from OS keystore
 * @returns {Promise<Buffer|null>} Master key or null if not found
 */
async function retrieveMasterKey() {
  if (!keytarAvailable) {
    return null;
  }

  try {
    const keyBase64 = await keytar.getPassword(SERVICE_NAME, MASTER_KEY_ACCOUNT);

    if (!keyBase64) {
      return null;
    }

    // Convert base64 back to Buffer
    return Buffer.from(keyBase64, 'base64');
  } catch (error) {
    console.error(chalk.yellow(`⚠️  Failed to retrieve master key: ${error.message}`));
    return null;
  }
}

/**
 * Delete master key from OS keystore
 * @returns {Promise<boolean>} Success status
 */
async function deleteMasterKey() {
  if (!keytarAvailable) {
    return false;
  }

  try {
    const deleted = await keytar.deletePassword(SERVICE_NAME, MASTER_KEY_ACCOUNT);

    // Delete metadata file
    if (fs.existsSync(KEY_METADATA_FILE)) {
      fs.unlinkSync(KEY_METADATA_FILE);
    }

    if (deleted) {
      console.log(chalk.green('✓ Master key removed from OS Keystore'));
    }

    return deleted;
  } catch (error) {
    console.error(chalk.red(`✗ Failed to delete master key: ${error.message}`));
    return false;
  }
}

/**
 * Encrypt data using master key with AES-256-GCM
 * @param {string} plaintext - Data to encrypt
 * @param {Buffer} masterKey - 32-byte master key
 * @returns {Object} Encrypted data with version, iv, authTag, and ciphertext
 */
function encryptWithMasterKey(plaintext, masterKey) {
  if (!masterKey || masterKey.length !== 32) {
    throw new Error('Master key must be 32 bytes (256 bits)');
  }

  try {
    // Generate random IV (12 bytes recommended for GCM)
    const iv = crypto.randomBytes(12);

    // Create cipher
    const cipher = crypto.createCipheriv('aes-256-gcm', masterKey, iv);

    // Encrypt
    let ciphertext = cipher.update(plaintext, 'utf8', 'hex');
    ciphertext += cipher.final('hex');

    // Get authentication tag
    const authTag = cipher.getAuthTag();

    return {
      version: EncryptionVersion.V2_0,
      algorithm: 'aes-256-gcm',
      iv: iv.toString('hex'),
      authTag: authTag.toString('hex'),
      ciphertext,
      created: new Date().toISOString()
    };
  } catch (error) {
    throw new Error(`Encryption failed: ${error.message}`);
  }
}

/**
 * Decrypt data using master key with authentication tag verification
 * @param {Object} encryptedData - Object with iv, authTag, and ciphertext
 * @param {Buffer} masterKey - 32-byte master key
 * @returns {string} Decrypted plaintext
 */
function decryptWithMasterKey(encryptedData, masterKey) {
  if (!masterKey || masterKey.length !== 32) {
    throw new Error('Master key must be 32 bytes (256 bits)');
  }

  try {
    const { iv, authTag, ciphertext } = encryptedData;

    // Create decipher
    const decipher = crypto.createDecipheriv(
      'aes-256-gcm',
      masterKey,
      Buffer.from(iv, 'hex')
    );

    // Set authentication tag for verification
    decipher.setAuthTag(Buffer.from(authTag, 'hex'));

    // Decrypt
    let plaintext = decipher.update(ciphertext, 'hex', 'utf8');
    plaintext += decipher.final('utf8');

    return plaintext;
  } catch (error) {
    // Authentication tag verification failure indicates tampering
    if (error.message.includes('auth')) {
      throw new Error('Decryption failed: Authentication tag verification failed (data may be corrupted or tampered)');
    }
    throw new Error(`Decryption failed: ${error.message}`);
  }
}

/**
 * Initialize master key (generate and store if not exists)
 * @returns {Promise<Buffer>} Master key
 */
async function initializeMasterKey() {
  // Try to retrieve existing master key
  let masterKey = await retrieveMasterKey();

  if (masterKey) {
    console.log(chalk.green('✓ Using existing master key from OS Keystore'));
    return masterKey;
  }

  // Generate new master key
  console.log(chalk.blue('🔐 Generating new 256-bit master key...'));
  masterKey = generateMasterKey();

  // Store in OS keystore
  await storeMasterKeySecurely(masterKey);

  return masterKey;
}

/**
 * Detect encryption version from encrypted data
 * @param {Object} encryptedData - Encrypted data object
 * @returns {string} Version identifier
 */
function detectEncryptionVersion(encryptedData) {
  if (encryptedData.version) {
    return encryptedData.version;
  }

  // Legacy v1.0 detection
  if (encryptedData.encrypted && encryptedData.iv && encryptedData.authTag) {
    return EncryptionVersion.V1_0;
  }

  throw new Error('Unknown encryption format');
}

/**
 * Ensure config directory exists with secure permissions
 */
function ensureConfigDirectory() {
  if (!fs.existsSync(CONFIG_DIR)) {
    fs.mkdirSync(CONFIG_DIR, { recursive: true, mode: 0o700 });
  } else {
    // Fix permissions if needed
    if (os.platform() !== 'win32') {
      try {
        fs.chmodSync(CONFIG_DIR, 0o700);
      } catch (error) {
        // Ignore permission errors
      }
    }
  }
}

/**
 * Generate legacy v1.0 machine key (for migration only)
 * DEPRECATED: Used only for decrypting old v1.0 data
 * @returns {Buffer} 32-byte key derived from machine data
 */
function getLegacyMachineKey() {
  // Same weak derivation as v1.0 for backward compatibility
  const machineId = os.hostname() + os.userInfo().username + os.platform() + os.arch();
  return crypto.createHash('sha256').update(machineId).digest();
}

/**
 * Decrypt legacy v1.0 encrypted data
 * @param {Object} legacyData - Legacy encrypted data
 * @returns {string} Decrypted plaintext
 */
function decryptLegacyV1(legacyData) {
  try {
    const key = getLegacyMachineKey();
    const decipher = crypto.createDecipheriv(
      'aes-256-gcm',
      key,
      Buffer.from(legacyData.iv, 'hex')
    );

    decipher.setAuthTag(Buffer.from(legacyData.authTag, 'hex'));

    let decrypted = decipher.update(legacyData.encrypted, 'hex', 'utf8');
    decrypted += decipher.final('utf8');

    return decrypted;
  } catch (error) {
    throw new Error(`Failed to decrypt legacy v1.0 data: ${error.message}`);
  }
}

/**
 * Check if OS keystore is available
 * @returns {boolean} Availability status
 */
function isKeystoreAvailable() {
  return keytarAvailable;
}

/**
 * Get encryption version metadata
 * @returns {Object|null} Metadata object or null
 */
function getKeyMetadata() {
  if (!fs.existsSync(KEY_METADATA_FILE)) {
    return null;
  }

  try {
    return JSON.parse(fs.readFileSync(KEY_METADATA_FILE, 'utf8'));
  } catch (error) {
    return null;
  }
}

/**
 * Rotate master key (generate new key and re-encrypt all data)
 * @returns {Promise<Buffer>} New master key
 */
async function rotateMasterKey() {
  console.log(chalk.blue('🔄 Rotating master encryption key...'));

  // Generate new master key
  const newMasterKey = generateMasterKey();

  // Delete old master key
  await deleteMasterKey();

  // Store new master key
  await storeMasterKeySecurely(newMasterKey);

  console.log(chalk.green('✓ Master key rotation complete'));
  console.log(chalk.yellow('⚠️  You must re-encrypt all credentials with the new key'));

  return newMasterKey;
}

/**
 * Verify master key integrity
 * @param {Buffer} masterKey - Master key to verify
 * @returns {boolean} Integrity status
 */
function verifyMasterKeyIntegrity(masterKey) {
  if (!masterKey) {
    return false;
  }

  if (!Buffer.isBuffer(masterKey)) {
    return false;
  }

  if (masterKey.length !== 32) {
    return false;
  }

  // Test encryption/decryption round-trip
  try {
    const testData = 'integrity-test';
    const encrypted = encryptWithMasterKey(testData, masterKey);
    const decrypted = decryptWithMasterKey(encrypted, masterKey);

    return decrypted === testData;
  } catch (error) {
    return false;
  }
}

/**
 * Export master key securely (for backup purposes)
 * @param {Buffer} masterKey - Master key to export
 * @param {string} password - Password for export encryption
 * @returns {string} Base64-encoded encrypted export
 */
function exportMasterKey(masterKey, password) {
  if (!password || password.length < 12) {
    throw new Error('Export password must be at least 12 characters');
  }

  // Derive key from password using PBKDF2
  const salt = crypto.randomBytes(32);
  const derivedKey = crypto.pbkdf2Sync(password, salt, 100000, 32, 'sha256');

  // Encrypt master key
  const encrypted = encryptWithMasterKey(masterKey.toString('base64'), derivedKey);

  // Combine salt and encrypted data
  const exportData = {
    version: EncryptionVersion.V2_0,
    type: 'master-key-export',
    salt: salt.toString('hex'),
    ...encrypted
  };

  return Buffer.from(JSON.stringify(exportData)).toString('base64');
}

/**
 * Import master key from backup
 * @param {string} exportedData - Base64-encoded export
 * @param {string} password - Password for decryption
 * @returns {Promise<Buffer>} Imported master key
 */
async function importMasterKey(exportedData, password) {
  try {
    const exportData = JSON.parse(Buffer.from(exportedData, 'base64').toString('utf8'));

    if (exportData.type !== 'master-key-export') {
      throw new Error('Invalid export data');
    }

    // Derive key from password
    const derivedKey = crypto.pbkdf2Sync(
      password,
      Buffer.from(exportData.salt, 'hex'),
      100000,
      32,
      'sha256'
    );

    // Decrypt master key
    const masterKeyBase64 = decryptWithMasterKey(exportData, derivedKey);
    const masterKey = Buffer.from(masterKeyBase64, 'base64');

    // Verify integrity
    if (!verifyMasterKeyIntegrity(masterKey)) {
      throw new Error('Imported master key failed integrity check');
    }

    // Store in OS keystore
    await storeMasterKeySecurely(masterKey);

    console.log(chalk.green('✓ Master key imported successfully'));
    return masterKey;
  } catch (error) {
    throw new Error(`Import failed: ${error.message}`);
  }
}

module.exports = {
  // Core functions
  generateMasterKey,
  storeMasterKeySecurely,
  retrieveMasterKey,
  deleteMasterKey,
  initializeMasterKey,

  // Encryption/Decryption
  encryptWithMasterKey,
  decryptWithMasterKey,

  // Version management
  detectEncryptionVersion,
  decryptLegacyV1,
  EncryptionVersion,

  // Utilities
  isKeystoreAvailable,
  getKeyMetadata,
  rotateMasterKey,
  verifyMasterKeyIntegrity,

  // Import/Export
  exportMasterKey,
  importMasterKey,

  // Legacy support
  getLegacyMachineKey
};
