#!/usr/bin/env node

/**
 * Secure Credential Management Module
 *
 * Provides multiple secure storage options for API keys:
 * 1. OS Keychain (most secure - encrypted at rest)
 * 2. Encrypted file storage (medium security - machine-specific encryption)
 * 3. Environment variables (.env file with strict permissions)
 * 4. Configuration files (with user consent and warnings)
 *
 * Security principles:
 * - Defense in depth
 * - Explicit user consent
 * - Secure by default
 * - Least privilege
 * - Audit logging
 * - API key validation and masking
 * - Automated permission enforcement
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const chalk = require('chalk');

// Try to load keytar for OS keychain support
let keytar = null;
let keytarAvailable = false;

try {
  keytar = require('keytar');
  keytarAvailable = true;
} catch (error) {
  // Keytar not available - will use fallback methods
  keytarAvailable = false;
}

const SERVICE_NAME = 'openrouter-mcp';
const ACCOUNT_API_KEY = 'api-key';

// Configuration paths
const CONFIG_DIR = path.join(os.homedir(), '.openrouter-mcp');
const ENCRYPTED_FILE = path.join(CONFIG_DIR, '.credentials.enc');
const AUDIT_LOG = path.join(CONFIG_DIR, 'security-audit.log');

/**
 * Storage options with security levels
 */
const StorageOptions = {
  KEYCHAIN: {
    id: 'keychain',
    name: 'OS Keychain/Credential Manager',
    securityLevel: 'HIGH',
    encrypted: true,
    description: 'Most secure - Uses system keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service)',
    platforms: ['darwin', 'win32', 'linux'],
    available: keytarAvailable
  },
  ENCRYPTED_FILE: {
    id: 'encrypted',
    name: 'Encrypted File Storage',
    securityLevel: 'MEDIUM-HIGH',
    encrypted: true,
    description: 'Machine-specific AES-256-GCM encryption - Keys derived from hardware/OS data',
    platforms: ['darwin', 'win32', 'linux'],
    available: true
  },
  ENV_FILE: {
    id: 'env',
    name: 'Environment Variables (.env file)',
    securityLevel: 'MEDIUM',
    encrypted: false,
    description: 'Plaintext file with restricted permissions (600) - Not committed to version control',
    platforms: ['darwin', 'win32', 'linux'],
    available: true
  },
  CONFIG_FILE: {
    id: 'config',
    name: 'Configuration File',
    securityLevel: 'MEDIUM',
    encrypted: false,
    description: 'Plaintext JSON with restricted permissions - Required for Claude integrations',
    platforms: ['darwin', 'win32', 'linux'],
    available: true
  }
};

/**
 * Security warnings for different storage methods
 */
const SecurityWarnings = {
  PLAINTEXT_STORAGE: {
    level: 'WARNING',
    message: `
${chalk.yellow('⚠️  SECURITY WARNING: PLAINTEXT STORAGE')}

The API key will be stored in ${chalk.bold('PLAINTEXT')} (unencrypted).

${chalk.red('RISKS:')}
• Anyone with file system access can read your API key
• Keys may be backed up to cloud services (Dropbox, OneDrive, etc.)
• Malware or other processes can access the key
• Accidental commits to version control expose your key

${chalk.green('MITIGATIONS IN PLACE:')}
• File permissions restricted to owner only (chmod 600)
• .gitignore patterns to prevent commits
• Regular key rotation recommended

${chalk.blue('RECOMMENDATIONS:')}
• Use OS Keychain storage instead (most secure option)
• Rotate API key every 90 days
• Monitor API usage for anomalies
• Never commit configuration files to version control
`
  },
  SHARED_ENVIRONMENT: {
    level: 'CRITICAL',
    message: `
${chalk.red('🚨 CRITICAL: SHARED/ENTERPRISE ENVIRONMENT DETECTED')}

${chalk.bold('STOP:')} Plaintext storage is ${chalk.red('NOT RECOMMENDED')} for:
• Shared workstations
• Enterprise environments
• Multi-user systems
• CI/CD environments

${chalk.yellow('REQUIRED ACTIONS:')}
1. Use OS Keychain storage (if available)
2. Implement enterprise secrets management (HashiCorp Vault, AWS Secrets Manager)
3. Enable audit logging
4. Use individual API keys per user/service

${chalk.blue('ALTERNATIVE:')}
Contact your security team for approved credential storage methods.
`
  },
  KEYCHAIN_LIMITATIONS: {
    level: 'INFO',
    message: `
${chalk.blue('ℹ️  OS Keychain Limitations')}

While OS Keychain is the most secure option available:

${chalk.yellow('IMPORTANT NOTES:')}
• Keys are encrypted at rest by the OS
• Protected by OS security mechanisms
• May require user authentication to access
• ${chalk.bold('BUT')}: User still has access to their own keys

${chalk.green('BEST PRACTICES:')}
• Keep OS security updates current
• Use strong system password/authentication
• Enable full disk encryption
• Lock screen when away from computer
`
  }
};

/**
 * Display security warning
 */
function displaySecurityWarning(warningType) {
  const warning = SecurityWarnings[warningType];
  if (!warning) return;

  console.log(warning.message);
}

/**
 * Check if environment is shared/enterprise
 */
function isSharedEnvironment() {
  // Simple heuristics - can be enhanced
  const indicators = {
    hasMultipleUsers: false,
    isVirtualMachine: false,
    isDomain: false
  };

  try {
    // Check for multiple user accounts (Unix-like)
    if (os.platform() !== 'win32') {
      const passwdFile = '/etc/passwd';
      if (fs.existsSync(passwdFile)) {
        const users = fs.readFileSync(passwdFile, 'utf8')
          .split('\n')
          .filter(line => {
            const parts = line.split(':');
            const uid = parseInt(parts[2]);
            return uid >= 1000 && uid < 65000; // Regular user UIDs
          });
        indicators.hasMultipleUsers = users.length > 1;
      }
    }

    // Check for common VM indicators
    const hostname = os.hostname().toLowerCase();
    indicators.isVirtualMachine =
      hostname.includes('vm') ||
      hostname.includes('virtual') ||
      hostname.includes('cloud');

    // Check for domain membership (Windows)
    if (os.platform() === 'win32') {
      indicators.isDomain = !!process.env.USERDOMAIN &&
        process.env.USERDOMAIN !== process.env.COMPUTERNAME;
    }
  } catch (error) {
    // If we can't determine, err on the side of caution
    return true;
  }

  return Object.values(indicators).some(v => v);
}

/**
 * Set secure file permissions
 */
function setSecurePermissions(filePath) {
  try {
    if (os.platform() !== 'win32') {
      // Unix-like: Set to 600 (owner read/write only)
      fs.chmodSync(filePath, 0o600);
      console.log(chalk.green(`✓ Set secure permissions (600) on ${filePath}`));
    } else {
      // Windows: Use icacls to restrict access
      const { execSync } = require('child_process');
      const username = process.env.USERNAME;

      // Remove inheritance and grant only current user
      try {
        execSync(`icacls "${filePath}" /inheritance:r /grant:r "${username}:F"`, {
          stdio: 'pipe'
        });
        console.log(chalk.green(`✓ Set secure permissions on ${filePath}`));
      } catch (error) {
        console.log(chalk.yellow(`⚠️  Could not set Windows permissions. Please verify file security manually.`));
      }
    }
  } catch (error) {
    console.log(chalk.yellow(`⚠️  Warning: Could not set secure permissions: ${error.message}`));
  }
}

/**
 * Store API key in OS Keychain
 */
async function storeInKeychain(apiKey) {
  if (!keytarAvailable) {
    throw new Error('Keychain storage not available. Install keytar: npm install keytar');
  }

  try {
    await keytar.setPassword(SERVICE_NAME, ACCOUNT_API_KEY, apiKey);
    console.log(chalk.green('✓ API key stored securely in OS Keychain'));
    displaySecurityWarning('KEYCHAIN_LIMITATIONS');
    return true;
  } catch (error) {
    throw new Error(`Failed to store in keychain: ${error.message}`);
  }
}

/**
 * Retrieve API key from OS Keychain
 */
async function getFromKeychain() {
  if (!keytarAvailable) {
    return null;
  }

  try {
    const apiKey = await keytar.getPassword(SERVICE_NAME, ACCOUNT_API_KEY);
    return apiKey;
  } catch (error) {
    console.error(chalk.yellow(`⚠️  Failed to retrieve from keychain: ${error.message}`));
    return null;
  }
}

/**
 * Delete API key from OS Keychain
 */
async function deleteFromKeychain() {
  if (!keytarAvailable) {
    return false;
  }

  try {
    const deleted = await keytar.deletePassword(SERVICE_NAME, ACCOUNT_API_KEY);
    if (deleted) {
      console.log(chalk.green('✓ API key removed from OS Keychain'));
    }
    return deleted;
  } catch (error) {
    console.error(chalk.red(`✗ Failed to delete from keychain: ${error.message}`));
    return false;
  }
}

/**
 * Store API key in .env file
 */
function storeInEnvFile(apiKey, appName, httpReferer, envPath = '.env') {
  const envContent = `# OpenRouter API Configuration
# ${chalk.yellow('WARNING: This file contains sensitive credentials in PLAINTEXT')}
# DO NOT commit this file to version control
# Keep this file secure with proper permissions (600)

OPENROUTER_API_KEY=${apiKey}
OPENROUTER_APP_NAME=${appName || 'openrouter-mcp'}
OPENROUTER_HTTP_REFERER=${httpReferer || 'https://localhost'}

# Server Configuration
HOST=localhost
PORT=8000
LOG_LEVEL=info
`;

  fs.writeFileSync(envPath, envContent, { mode: 0o600 });
  setSecurePermissions(envPath);

  console.log(chalk.green(`✓ Configuration saved to ${envPath}`));

  // Add to .gitignore if in a git repo
  addToGitignore(envPath);

  return true;
}

/**
 * Store API key in configuration file
 */
function storeInConfigFile(apiKey, configPath, configType = 'claude-desktop') {
  // Ensure directory exists
  const configDir = path.dirname(configPath);
  if (!fs.existsSync(configDir)) {
    fs.mkdirSync(configDir, { recursive: true, mode: 0o700 });
  }

  // Read existing config or create new one
  let config = { mcpServers: {} };
  if (fs.existsSync(configPath)) {
    try {
      config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    } catch (error) {
      console.log(chalk.yellow('⚠️  Existing config file is invalid, creating new one'));
    }
  }

  // Add OpenRouter MCP server configuration
  config.mcpServers = config.mcpServers || {};
  config.mcpServers.openrouter = {
    command: "npx",
    args: ["openrouter-mcp", "start"],
    env: {
      OPENROUTER_API_KEY: apiKey
    }
  };

  // Write config with secure permissions
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2), { mode: 0o600 });
  setSecurePermissions(configPath);

  console.log(chalk.green(`✓ Configuration saved to ${configPath}`));

  return true;
}

/**
 * Add file to .gitignore
 */
function addToGitignore(filePath) {
  const gitignorePath = path.join(process.cwd(), '.gitignore');
  const fileName = path.basename(filePath);

  try {
    let gitignoreContent = '';
    if (fs.existsSync(gitignorePath)) {
      gitignoreContent = fs.readFileSync(gitignorePath, 'utf8');
    }

    // Check if already in .gitignore
    if (!gitignoreContent.includes(fileName)) {
      const newContent = gitignoreContent +
        (gitignoreContent.endsWith('\n') ? '' : '\n') +
        `\n# OpenRouter MCP - Sensitive credentials\n${fileName}\n`;

      fs.writeFileSync(gitignorePath, newContent);
      console.log(chalk.green(`✓ Added ${fileName} to .gitignore`));
    }
  } catch (error) {
    console.log(chalk.yellow(`⚠️  Note: Could not update .gitignore. Please manually add ${fileName} to .gitignore`));
  }
}

/**
 * Retrieve API key from environment
 */
function getFromEnvironment() {
  // Check environment variable
  if (process.env.OPENROUTER_API_KEY) {
    return process.env.OPENROUTER_API_KEY;
  }

  // Check .env file in multiple locations
  const possibleEnvPaths = [
    path.join(process.cwd(), '.env'),
    path.join(__dirname, '..', '.env'),
    path.join(os.homedir(), '.openrouter-mcp.env')
  ];

  for (const envPath of possibleEnvPaths) {
    if (fs.existsSync(envPath)) {
      try {
        const envContent = fs.readFileSync(envPath, 'utf8');
        const match = envContent.match(/OPENROUTER_API_KEY=(.+)/);
        if (match && match[1]) {
          return match[1].trim();
        }
      } catch (error) {
        continue;
      }
    }
  }

  return null;
}

/**
 * Get API key from any available source (priority order)
 */
async function getApiKey() {
  // 1. Try environment variable first (runtime override)
  if (process.env.OPENROUTER_API_KEY) {
    auditLog('key-retrieved', { method: 'env-var' });
    return { key: process.env.OPENROUTER_API_KEY, source: 'environment-variable' };
  }

  // 2. Try keychain (most secure)
  const keychainKey = await getFromKeychain();
  if (keychainKey) {
    return { key: keychainKey, source: 'keychain' };
  }

  // 3. Try encrypted file
  const encryptedKey = await getFromEncryptedFile();
  if (encryptedKey) {
    return { key: encryptedKey, source: 'encrypted-file' };
  }

  // 4. Try .env file
  const envKey = getFromEnvironment();
  if (envKey) {
    return { key: envKey, source: 'env-file' };
  }

  return { key: null, source: null };
}

/**
 * Rotate API key
 */
async function rotateApiKey(newApiKey) {
  console.log(chalk.blue('🔄 Rotating API key...'));

  const validation = validateApiKey(newApiKey);
  if (!validation.valid && !validation.warning) {
    throw new Error(validation.error);
  }

  const locations = [];

  // Update keychain
  if (keytarAvailable) {
    try {
      const hasKeychainKey = await getFromKeychain();
      if (hasKeychainKey) {
        await storeInKeychain(newApiKey);
        locations.push('OS Keychain');
      }
    } catch (error) {
      console.log(chalk.yellow(`⚠️  Could not update keychain: ${error.message}`));
    }
  }

  // Update encrypted file
  if (fs.existsSync(ENCRYPTED_FILE)) {
    try {
      storeInEncryptedFile(newApiKey);
      locations.push('Encrypted file');
    } catch (error) {
      console.log(chalk.yellow(`⚠️  Could not update encrypted file: ${error.message}`));
    }
  }

  // Update .env file
  const envPath = path.join(process.cwd(), '.env');
  if (fs.existsSync(envPath)) {
    try {
      const envContent = fs.readFileSync(envPath, 'utf8');
      const newContent = envContent.replace(
        /OPENROUTER_API_KEY=.+/,
        `OPENROUTER_API_KEY=${newApiKey}`
      );
      fs.writeFileSync(envPath, newContent, { mode: 0o600 });
      setSecurePermissions(envPath);
      locations.push('.env file');
    } catch (error) {
      console.log(chalk.yellow(`⚠️  Could not update .env: ${error.message}`));
    }
  }

  // Update Claude Desktop config
  const claudeDesktopPath = getClaudeDesktopConfigPath();
  if (fs.existsSync(claudeDesktopPath)) {
    try {
      const config = JSON.parse(fs.readFileSync(claudeDesktopPath, 'utf8'));
      if (config.mcpServers?.openrouter?.env?.OPENROUTER_API_KEY) {
        config.mcpServers.openrouter.env.OPENROUTER_API_KEY = newApiKey;
        fs.writeFileSync(claudeDesktopPath, JSON.stringify(config, null, 2), { mode: 0o600 });
        setSecurePermissions(claudeDesktopPath);
        locations.push('Claude Desktop config');
      }
    } catch (error) {
      console.log(chalk.yellow(`⚠️  Could not update Claude Desktop config: ${error.message}`));
    }
  }

  // Update Claude Code config
  const claudeCodePath = getClaudeCodeConfigPath();
  if (fs.existsSync(claudeCodePath)) {
    try {
      const config = JSON.parse(fs.readFileSync(claudeCodePath, 'utf8'));
      if (config.mcpServers?.openrouter?.env?.OPENROUTER_API_KEY) {
        config.mcpServers.openrouter.env.OPENROUTER_API_KEY = newApiKey;
        fs.writeFileSync(claudeCodePath, JSON.stringify(config, null, 2), { mode: 0o600 });
        setSecurePermissions(claudeCodePath);
        locations.push('Claude Code config');
      }
    } catch (error) {
      console.log(chalk.yellow(`⚠️  Could not update Claude Code config: ${error.message}`));
    }
  }

  if (locations.length > 0) {
    console.log(chalk.green(`✓ API key rotated in: ${locations.join(', ')}`));
  } else {
    console.log(chalk.yellow('⚠️  No existing credential storage found to update'));
  }

  return locations;
}

/**
 * Delete API key from all locations
 */
async function deleteAllCredentials() {
  console.log(chalk.blue('🗑️  Removing API key from all locations...'));

  const locations = [];

  // Delete from keychain
  if (await deleteFromKeychain()) {
    locations.push('OS Keychain');
  }

  // Delete encrypted file
  if (deleteEncryptedFile()) {
    locations.push('Encrypted file');
  }

  // Delete .env file
  const envPath = path.join(process.cwd(), '.env');
  if (fs.existsSync(envPath)) {
    fs.unlinkSync(envPath);
    auditLog('key-deleted', { method: 'env-file' });
    locations.push('.env file');
  }

  // Remove from Claude configs (just the API key, not the entire config)
  const claudeDesktopPath = getClaudeDesktopConfigPath();
  if (fs.existsSync(claudeDesktopPath)) {
    try {
      const config = JSON.parse(fs.readFileSync(claudeDesktopPath, 'utf8'));
      if (config.mcpServers?.openrouter) {
        delete config.mcpServers.openrouter;
        fs.writeFileSync(claudeDesktopPath, JSON.stringify(config, null, 2));
        locations.push('Claude Desktop config');
      }
    } catch (error) {
      // Ignore
    }
  }

  const claudeCodePath = getClaudeCodeConfigPath();
  if (fs.existsSync(claudeCodePath)) {
    try {
      const config = JSON.parse(fs.readFileSync(claudeCodePath, 'utf8'));
      if (config.mcpServers?.openrouter) {
        delete config.mcpServers.openrouter;
        fs.writeFileSync(claudeCodePath, JSON.stringify(config, null, 2));
        locations.push('Claude Code config');
      }
    } catch (error) {
      // Ignore
    }
  }

  if (locations.length > 0) {
    console.log(chalk.green(`✓ API key removed from: ${locations.join(', ')}`));
  } else {
    console.log(chalk.yellow('⚠️  No credentials found to remove'));
  }

  return locations;
}

/**
 * Get Claude Desktop config path for current platform
 */
function getClaudeDesktopConfigPath() {
  const homeDir = os.homedir();

  switch (os.platform()) {
    case 'darwin':
      return path.join(homeDir, 'Library', 'Application Support', 'Claude', 'claude_desktop_config.json');
    case 'win32':
      return path.join(homeDir, 'AppData', 'Roaming', 'Claude', 'claude_desktop_config.json');
    default:
      return path.join(homeDir, '.config', 'claude', 'claude_desktop_config.json');
  }
}

/**
 * Get Claude Code config path
 */
function getClaudeCodeConfigPath() {
  const homeDir = os.homedir();
  return path.join(homeDir, '.claude', 'claude_code_config.json');
}

/**
 * Ensure config directory exists with proper permissions
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
 * Log security audit event
 */
function auditLog(event, details = {}) {
  ensureConfigDirectory();

  const logEntry = {
    timestamp: new Date().toISOString(),
    event,
    user: os.userInfo().username,
    hostname: os.hostname(),
    platform: os.platform(),
    ...details
  };

  const logLine = JSON.stringify(logEntry) + '\n';

  try {
    fs.appendFileSync(AUDIT_LOG, logLine, { mode: 0o600 });
  } catch (error) {
    // Audit logging failure should not break functionality
  }
}

/**
 * Mask API key for display (show first 8 and last 4 characters)
 */
function maskApiKey(apiKey) {
  if (!apiKey || apiKey.length < 12) {
    return '****';
  }
  return `${apiKey.substring(0, 8)}...${apiKey.substring(apiKey.length - 4)}`;
}

/**
 * Validate API key format
 */
function validateApiKey(apiKey) {
  if (!apiKey || typeof apiKey !== 'string') {
    return { valid: false, error: 'API key is required' };
  }

  // Trim whitespace
  apiKey = apiKey.trim();

  // Check minimum length (OpenRouter keys are typically 32+ chars)
  if (apiKey.length < 20) {
    return { valid: false, error: 'API key appears too short' };
  }

  // Check for common patterns (sk-or-v1-...)
  if (!apiKey.startsWith('sk-or-')) {
    return {
      valid: false,
      error: 'API key should start with "sk-or-" (OpenRouter format)',
      warning: true
    };
  }

  // Check for suspicious characters
  if (!/^[a-zA-Z0-9\-_]+$/.test(apiKey)) {
    return { valid: false, error: 'API key contains invalid characters' };
  }

  return { valid: true, key: apiKey };
}

// Import crypto manager v2.0
const cryptoManager = require('./crypto-manager');

/**
 * Generate encryption key from machine-specific data (DEPRECATED - v1.0 only)
 * @deprecated Use cryptoManager.generateMasterKey() instead
 */
function getMachineKey() {
  // Use machine-specific data to derive encryption key
  const machineId = os.hostname() + os.userInfo().username + os.platform() + os.arch();
  return crypto.createHash('sha256').update(machineId).digest();
}

/**
 * Encrypt data using AES-256-GCM with v2.0 crypto manager
 * @param {string} data - Data to encrypt
 * @returns {Promise<Object>} Encrypted data object
 */
async function encryptData(data) {
  try {
    // Initialize or retrieve master key
    const masterKey = await cryptoManager.initializeMasterKey();

    // Encrypt using v2.0
    const encrypted = cryptoManager.encryptWithMasterKey(data, masterKey);

    return {
      ...encrypted,
      version: '2.0'
    };
  } catch (error) {
    console.error(chalk.red(`✗ Encryption failed: ${error.message}`));
    throw error;
  }
}

/**
 * Decrypt data using AES-256-GCM with version detection
 * @param {Object} encryptedData - Encrypted data object
 * @returns {Promise<string>} Decrypted plaintext
 */
async function decryptData(encryptedData) {
  try {
    // Detect encryption version
    const version = cryptoManager.detectEncryptionVersion(encryptedData);

    if (version === '2.0') {
      // Decrypt using v2.0
      const masterKey = await cryptoManager.retrieveMasterKey();

      if (!masterKey) {
        throw new Error('Master key not found. Run migration: openrouter-mcp migrate-encryption');
      }

      return cryptoManager.decryptWithMasterKey(encryptedData, masterKey);
    } else {
      // Legacy v1.0 decryption
      console.warn(chalk.yellow('⚠️  Using legacy v1.0 decryption. Consider migrating to v2.0'));
      return cryptoManager.decryptLegacyV1(encryptedData);
    }
  } catch (error) {
    console.error(chalk.red(`✗ Decryption failed: ${error.message}`));
    throw error;
  }
}

/**
 * Decrypt legacy v1.0 data (for backward compatibility)
 * @param {string} encrypted - Encrypted ciphertext
 * @param {string} iv - Initialization vector
 * @param {string} authTag - Authentication tag
 * @returns {string} Decrypted plaintext
 * @deprecated Use decryptData() with automatic version detection
 */
function decryptDataLegacy(encrypted, iv, authTag) {
  const key = getMachineKey();
  const decipher = crypto.createDecipheriv(
    'aes-256-gcm',
    key,
    Buffer.from(iv, 'hex')
  );

  decipher.setAuthTag(Buffer.from(authTag, 'hex'));

  let decrypted = decipher.update(encrypted, 'hex', 'utf8');
  decrypted += decipher.final('utf8');

  return decrypted;
}

/**
 * Store API key in encrypted file (v2.0)
 * @param {string} apiKey - API key to store
 * @returns {Promise<void>}
 */
async function storeInEncryptedFile(apiKey) {
  const validation = validateApiKey(apiKey);
  if (!validation.valid && !validation.warning) {
    throw new Error(validation.error);
  }

  ensureConfigDirectory();

  // Encrypt using v2.0
  const encrypted = await encryptData(validation.key || apiKey);
  const data = JSON.stringify({
    ...encrypted,
    created: new Date().toISOString(),
    hostname: os.hostname()
  });

  fs.writeFileSync(ENCRYPTED_FILE, data, { mode: 0o600 });
  setSecurePermissions(ENCRYPTED_FILE);
  auditLog('key-stored', { method: 'encrypted-file', version: '2.0' });

  console.log(chalk.green('✓ API key stored in encrypted file (v2.0)'));
  console.log(chalk.gray(`  Location: ${ENCRYPTED_FILE}`));
  console.log(chalk.gray(`  Masked key: ${maskApiKey(validation.key || apiKey)}`));
  console.log(chalk.gray(`  Encryption: AES-256-GCM with OS Keystore`));
}

/**
 * Retrieve API key from encrypted file (supports v1.0 and v2.0)
 * @returns {Promise<string|null>}
 */
async function getFromEncryptedFile() {
  if (!fs.existsSync(ENCRYPTED_FILE)) {
    return null;
  }

  try {
    const data = JSON.parse(fs.readFileSync(ENCRYPTED_FILE, 'utf8'));

    // Decrypt with version detection
    const decrypted = await decryptData(data);
    auditLog('key-retrieved', { method: 'encrypted-file', version: data.version || '1.0' });

    return decrypted;
  } catch (error) {
    console.error(chalk.yellow('⚠️  Failed to decrypt credentials. File may be corrupted or migration required.'));
    console.error(chalk.gray(`  Error: ${error.message}`));
    return null;
  }
}

/**
 * Delete encrypted credentials file
 */
function deleteEncryptedFile() {
  if (fs.existsSync(ENCRYPTED_FILE)) {
    fs.unlinkSync(ENCRYPTED_FILE);
    auditLog('key-deleted', { method: 'encrypted-file' });
    return true;
  }
  return false;
}

/**
 * Enhanced shared environment detection
 */
function detectSharedEnvironment() {
  const indicators = [];

  // Check for CI/CD environment variables
  const ciVars = [
    'CI', 'CONTINUOUS_INTEGRATION', 'GITHUB_ACTIONS', 'GITLAB_CI',
    'CIRCLECI', 'TRAVIS', 'JENKINS_HOME', 'TEAMCITY_VERSION'
  ];

  if (ciVars.some(v => process.env[v])) {
    indicators.push({ type: 'ci-cd', severity: 'high' });
  }

  // Check hostname for server patterns
  const hostname = os.hostname().toLowerCase();
  const serverPatterns = ['aws', 'azure', 'gcp', 'ec2', 'compute', 'instance', 'cloud', 'server'];
  if (serverPatterns.some(p => hostname.includes(p))) {
    indicators.push({ type: 'cloud-server', severity: 'medium' });
  }

  // Check for multiple users (Unix-like)
  if (os.platform() !== 'win32') {
    try {
      const homeDir = os.homedir();
      const stats = fs.statSync(homeDir);
      const mode = stats.mode & parseInt('777', 8);
      if (mode & parseInt('077', 8)) {
        indicators.push({ type: 'shared-filesystem', severity: 'medium' });
      }
    } catch (error) {
      // Ignore
    }
  }

  return {
    shared: indicators.length > 0,
    indicators,
    recommendation: indicators.length > 0 ?
      'Use OS Keychain or encrypted file storage' :
      'Any storage method acceptable'
  };
}

/**
 * Perform comprehensive security audit
 */
async function performSecurityAudit() {
  const audit = {
    timestamp: new Date().toISOString(),
    platform: os.platform(),
    environment: detectSharedEnvironment(),
    credentials: [],
    permissions: {},
    vulnerabilities: [],
    recommendations: []
  };

  // Check OS Keychain
  if (keytarAvailable) {
    try {
      const key = await getFromKeychain();
      if (key) {
        audit.credentials.push({
          location: 'OS Keychain',
          security: 'HIGH',
          encrypted: true,
          masked: maskApiKey(key)
        });
      }
    } catch (error) {
      // Ignore
    }
  } else {
    audit.recommendations.push({
      priority: 'HIGH',
      action: 'Install keytar for OS Keychain support',
      command: 'npm install keytar'
    });
  }

  // Check encrypted file
  if (fs.existsSync(ENCRYPTED_FILE)) {
    const stats = fs.statSync(ENCRYPTED_FILE);
    const mode = stats.mode & parseInt('777', 8);

    audit.credentials.push({
      location: ENCRYPTED_FILE,
      security: 'MEDIUM-HIGH',
      encrypted: true,
      permissions: mode.toString(8),
      size: stats.size
    });

    if (os.platform() !== 'win32' && mode !== parseInt('600', 8)) {
      audit.vulnerabilities.push({
        severity: 'HIGH',
        issue: 'Encrypted file has insecure permissions',
        file: ENCRYPTED_FILE,
        currentMode: mode.toString(8),
        recommendedMode: '600'
      });
    }
  }

  // Check .env file
  const envPath = path.join(process.cwd(), '.env');
  if (fs.existsSync(envPath)) {
    const stats = fs.statSync(envPath);
    const mode = stats.mode & parseInt('777', 8);
    const content = fs.readFileSync(envPath, 'utf8');
    const hasApiKey = content.includes('OPENROUTER_API_KEY=sk-or-');

    if (hasApiKey) {
      audit.credentials.push({
        location: envPath,
        security: 'LOW',
        encrypted: false,
        permissions: mode.toString(8)
      });

      if (os.platform() !== 'win32' && mode !== parseInt('600', 8)) {
        audit.vulnerabilities.push({
          severity: 'CRITICAL',
          issue: 'Plaintext credentials with insecure permissions',
          file: envPath,
          currentMode: mode.toString(8),
          recommendedMode: '600'
        });
      }

      if (audit.environment.shared) {
        audit.vulnerabilities.push({
          severity: 'HIGH',
          issue: 'Plaintext credentials in shared environment',
          recommendation: 'Migrate to OS Keychain or encrypted storage'
        });
      }
    }
  }

  // Check .gitignore
  const gitignorePath = path.join(process.cwd(), '.gitignore');
  if (fs.existsSync(gitignorePath)) {
    const content = fs.readFileSync(gitignorePath, 'utf8');
    if (!content.includes('.env')) {
      audit.vulnerabilities.push({
        severity: 'CRITICAL',
        issue: '.env not in .gitignore',
        recommendation: 'Add .env to .gitignore immediately'
      });
    }
  }

  return audit;
}

/**
 * Fix common permission issues
 */
function fixPermissions() {
  const fixed = [];

  try {
    // Fix config directory
    if (fs.existsSync(CONFIG_DIR)) {
      setSecurePermissions(CONFIG_DIR);
      fixed.push({ path: CONFIG_DIR, type: 'directory' });
    }

    // Fix encrypted file
    if (fs.existsSync(ENCRYPTED_FILE)) {
      setSecurePermissions(ENCRYPTED_FILE);
      fixed.push({ path: ENCRYPTED_FILE, type: 'file' });
    }

    // Fix .env file
    const envPath = path.join(process.cwd(), '.env');
    if (fs.existsSync(envPath)) {
      setSecurePermissions(envPath);
      fixed.push({ path: envPath, type: 'file' });
    }

    if (fixed.length > 0) {
      auditLog('permissions-fixed', { files: fixed });
      console.log(chalk.green(`✓ Fixed permissions for ${fixed.length} file(s)`));
    }
  } catch (error) {
    console.error(chalk.red(`✗ Failed to fix permissions: ${error.message}`));
  }

  return fixed;
}

module.exports = {
  StorageOptions,
  SecurityWarnings,
  displaySecurityWarning,
  isSharedEnvironment,
  setSecurePermissions,
  storeInKeychain,
  getFromKeychain,
  deleteFromKeychain,
  storeInEncryptedFile,
  getFromEncryptedFile,
  deleteEncryptedFile,
  storeInEnvFile,
  storeInConfigFile,
  getFromEnvironment,
  getApiKey,
  rotateApiKey,
  deleteAllCredentials,
  getClaudeDesktopConfigPath,
  getClaudeCodeConfigPath,
  maskApiKey,
  validateApiKey,
  auditLog,
  detectSharedEnvironment,
  performSecurityAudit,
  fixPermissions,
  keytarAvailable
};
