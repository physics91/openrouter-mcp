#!/usr/bin/env node

const { program } = require('commander');
const chalk = require('chalk');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const {
  getMissingPythonMessage,
  getUnsupportedPythonMessage,
  resolveSupportedPythonCommand,
} = require('./python-version');

const packageJson = require('../package.json');
const secureCredentials = require('./secure-credentials');
const {
  buildClaudeCodeInstallCommand,
  buildClaudeCodeRemoveCommand,
  buildClaudeCodeServerConfig,
  configContainsPlaintextOpenRouterKey,
  getClaudeCodeUserConfigPath,
} = require('./claude-config-utils');
const MCP_PACKAGE_NAME = packageJson.name || 'openrouter-mcp';

program
  .name('openrouter-mcp')
  .description('OpenRouter MCP Server - Access multiple AI models through a unified interface')
  .version(packageJson.version);

// Global options
program
  .option('-v, --verbose', 'Enable verbose logging')
  .option('--debug', 'Enable debug mode');

// Start command
program
  .command('start')
  .description('Start the OpenRouter MCP server')
  .option('-p, --port <port>', 'Port to run the server on', '8000')
  .option('-h, --host <host>', 'Host to bind the server to', 'localhost')
  .action(async (options) => {
    console.log(chalk.blue('🚀 Starting OpenRouter MCP Server...'));

    const pythonCommand = await checkPythonRequirements();
    if (!pythonCommand) {
      process.exit(1);
    }

    if (!await checkApiKey()) {
      console.log(chalk.yellow('⚠️  No OpenRouter API key found. Run "openrouter-mcp init" to configure.'));
    }

    await startServer(options, pythonCommand);
  });

// Init command
program
  .command('init')
  .description('Initialize OpenRouter MCP configuration')
  .action(async () => {
    console.log(chalk.green('🔧 Initializing OpenRouter MCP...'));
    await initializeConfig();
  });

// Status command
program
  .command('status')
  .description('Check server status and configuration')
  .action(async () => {
    console.log(chalk.blue('📊 OpenRouter MCP Status'));
    await checkStatus();
  });

// Install command for Claude Desktop
program
  .command('install-claude')
  .description('Install configuration for Claude Desktop')
  .action(async () => {
    console.log(chalk.green('🤖 Installing Claude Desktop configuration...'));
    await installClaudeConfig();
  });

// Install command for Claude Code CLI
program
  .command('install-claude-code')
  .description('Register OpenRouter in Claude Code user scope')
  .action(async () => {
    console.log(chalk.green('💻 Registering OpenRouter in Claude Code user scope...'));
    await installClaudeCodeConfig();
  });

// Rotate API key command
program
  .command('rotate-key')
  .description('Rotate OpenRouter API key in all configured locations')
  .action(async () => {
    console.log(chalk.blue('🔄 API Key Rotation'));
    await rotateApiKey();
  });

// Delete credentials command
program
  .command('delete-credentials')
  .description('Remove API key from all configured locations')
  .action(async () => {
    console.log(chalk.red('🗑️  Delete Credentials'));
    await deleteCredentials();
  });

// Security audit command
program
  .command('security-audit')
  .description('Audit security configuration and credential storage')
  .action(async () => {
    console.log(chalk.blue('🔒 Security Audit'));
    await securityAudit();
  });

// Migrate encryption command
program
  .command('migrate-encryption')
  .description('Migrate credentials from v1.0 to v2.0 encryption')
  .action(async () => {
    console.log(chalk.blue('🔐 Encryption Migration'));
    await migrateEncryption();
  });

async function checkPythonRequirements() {
  console.log(chalk.blue('🐍 Checking Python environment...'));

  try {
    // Check Python version
    const pythonInfo = await resolveSupportedPythonCommand(runCommand);
    if (pythonInfo.status === 'missing') {
      console.log(chalk.red('✗ Python not found or not accessible'));
      console.log(chalk.blue(getMissingPythonMessage()));
      return null;
    }

    if (pythonInfo.status === 'unsupported') {
      console.log(chalk.red('✗ Unsupported Python version'));
      console.log(chalk.blue(getUnsupportedPythonMessage(pythonInfo.version)));
      return null;
    }

    console.log(chalk.green(`✓ Python found: ${pythonInfo.version} (${pythonInfo.command})`));

    // Check if in virtual environment
    const isVenv = process.env.VIRTUAL_ENV || process.env.CONDA_DEFAULT_ENV;
    if (isVenv) {
      console.log(chalk.green(`✓ Virtual environment: ${isVenv}`));
    } else {
      console.log(chalk.yellow('⚠️  No virtual environment detected. Consider using one.'));
    }

    // Check required packages
    try {
      await runCommand(pythonInfo.command, ['-c', 'import fastmcp, httpx, pydantic']);
      console.log(chalk.green('✓ Required Python packages are installed'));
      return pythonInfo.command;
    } catch (error) {
      console.log(chalk.red('✗ Missing required Python packages'));
      console.log(chalk.blue('Installing Python dependencies...'));

      try {
        await runCommand(
          pythonInfo.command,
          ['-m', 'pip', 'install', '-r', path.join(__dirname, '..', 'requirements.txt')]
        );
        console.log(chalk.green('✓ Python dependencies installed successfully'));
        return pythonInfo.command;
      } catch (installError) {
        console.log(chalk.red('✗ Failed to install Python dependencies'));
        console.log(chalk.blue(`Please run: ${pythonInfo.command} -m pip install -r requirements.txt`));
        return null;
      }
    }

  } catch (error) {
    console.log(chalk.red('✗ Python not found or not accessible'));
    console.log(chalk.blue(getMissingPythonMessage()));
    return null;
  }
}

async function checkApiKey() {
  // Use the unified secure credential retrieval method
  const keyResult = await secureCredentials.getApiKey();

  if (keyResult.key) {
    const maskedKey = secureCredentials.maskApiKey(keyResult.key);
    console.log(chalk.green(`✓ OpenRouter API key configured (${keyResult.source})`));
    console.log(chalk.gray(`  Masked key: ${maskedKey}`));
    return true;
  }

  return false;
}

async function startServer(options, pythonCommand) {
  const projectRoot = path.join(__dirname, '..');
  const srcPath = path.join(projectRoot, 'src');
  const mergedPythonPath = [srcPath, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);

  const env = {
    ...process.env,
    PYTHONPATH: mergedPythonPath,
    HOST: options.host,
    PORT: options.port.toString(),
    LOG_LEVEL: program.opts().debug ? 'debug' : (program.opts().verbose ? 'info' : 'warning')
  };

  // Retrieve API key from secure storage if not already in environment
  if (!env.OPENROUTER_API_KEY) {
    console.log(chalk.blue('🔑 Retrieving API key from secure storage...'));

    const keyResult = await secureCredentials.getApiKey();

    if (keyResult.key) {
      env.OPENROUTER_API_KEY = keyResult.key;
      const maskedKey = secureCredentials.maskApiKey(keyResult.key);
      console.log(chalk.green(`✓ API key loaded from ${keyResult.source}`));
      console.log(chalk.gray(`  Masked key: ${maskedKey}`));

      // Audit log for security tracking
      secureCredentials.auditLog('key-loaded-for-server', { source: keyResult.source });
    } else {
      console.log(chalk.yellow('⚠️  No API key found in secure storage'));
      console.log(chalk.blue('💡 To configure API key, run: openrouter-mcp init'));
      console.log(chalk.gray('   Server will start but API calls will fail without a valid key\n'));
    }
  } else {
    console.log(chalk.green('✓ Using API key from environment variable'));
    const maskedKey = secureCredentials.maskApiKey(env.OPENROUTER_API_KEY);
    console.log(chalk.gray(`  Masked key: ${maskedKey}`));
  }

  console.log(chalk.blue(`Starting server on ${options.host}:${options.port}`));

  const python = spawn(pythonCommand, ['-m', 'openrouter_mcp.server'], {
    env,
    stdio: 'inherit',
    cwd: projectRoot
  });

  python.on('close', (code) => {
    if (code !== 0) {
      console.log(chalk.red(`Server exited with code ${code}`));
      process.exit(code);
    }
  });

  // Handle graceful shutdown
  process.on('SIGINT', () => {
    console.log(chalk.yellow('\n🛑 Shutting down server...'));
    python.kill('SIGINT');
  });

  process.on('SIGTERM', () => {
    console.log(chalk.yellow('\n🛑 Shutting down server...'));
    python.kill('SIGTERM');
  });
}

async function initializeConfig() {
  const inquirer = (await import('inquirer')).default;

  console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════'));
  console.log(chalk.cyan('  OpenRouter MCP - Secure Configuration Wizard'));
  console.log(chalk.cyan('═══════════════════════════════════════════════════════════\n'));

  // Security notice
  console.log(chalk.yellow('🔒 SECURITY NOTICE'));
  console.log(chalk.white('This wizard will help you securely configure your OpenRouter API key.'));
  console.log(chalk.white('We recommend using OS Keychain for maximum security.\n'));

  // Detect shared environment
  if (secureCredentials.isSharedEnvironment()) {
    secureCredentials.displaySecurityWarning('SHARED_ENVIRONMENT');

    const { continueSetup } = await inquirer.prompt([
      {
        type: 'confirm',
        name: 'continueSetup',
        message: chalk.yellow('Do you understand the risks and wish to continue?'),
        default: false
      }
    ]);

    if (!continueSetup) {
      console.log(chalk.blue('Setup cancelled. Please consult your security team.'));
      return;
    }
  }

  // API key input
  const answers = await inquirer.prompt([
    {
      type: 'password',
      name: 'apiKey',
      message: 'Enter your OpenRouter API key:',
      mask: '*',
      validate: (input) => {
        if (input.length === 0) return 'API key cannot be empty';
        if (!input.startsWith('sk-or-')) {
          return chalk.yellow('Warning: OpenRouter API keys typically start with "sk-or-". Continue anyway? (y/n)');
        }
        return true;
      }
    },
    {
      type: 'input',
      name: 'appName',
      message: 'Enter your app name (optional):',
      default: 'openrouter-mcp'
    },
    {
      type: 'input',
      name: 'httpReferer',
      message: 'Enter your HTTP referer (optional):',
      default: 'https://localhost'
    }
  ]);

  console.log(chalk.cyan('\n─────────────────────────────────────────────────────────────\n'));
  console.log(chalk.bold('Storage Options\n'));

  // Show available storage options
  const storageChoices = [];

  if (secureCredentials.keytarAvailable) {
    storageChoices.push({
      name: `${chalk.green('●')} ${secureCredentials.StorageOptions.KEYCHAIN.name} ${chalk.green('[RECOMMENDED]')}`,
      short: 'OS Keychain',
      value: 'keychain'
    });
  } else {
    console.log(chalk.yellow('⚠️  OS Keychain not available. To enable, run: npm install keytar\n'));
  }

  storageChoices.push({
    name: `${chalk.cyan('●')} ${secureCredentials.StorageOptions.ENCRYPTED_FILE.name} ${chalk.cyan('[RECOMMENDED FOR CI/CD]')}`,
    short: 'Encrypted File',
    value: 'encrypted'
  });

  storageChoices.push({
    name: `${chalk.yellow('●')} ${secureCredentials.StorageOptions.ENV_FILE.name}`,
    short: '.env file',
    value: 'env'
  });

  // Ask for storage preference
  const { storageMethod } = await inquirer.prompt([
    {
      type: 'list',
      name: 'storageMethod',
      message: 'Where would you like to store your API key?',
      choices: storageChoices,
      default: secureCredentials.keytarAvailable ? 'keychain' : 'env'
    }
  ]);

  // Store API key based on choice
  if (storageMethod === 'keychain') {
    try {
      await secureCredentials.storeInKeychain(answers.apiKey);

      // Also create .env file WITHOUT the API key for other settings
      const envContent = `# OpenRouter Configuration
# API key is stored securely in OS Keychain
OPENROUTER_APP_NAME=${answers.appName}
OPENROUTER_HTTP_REFERER=${answers.httpReferer}

# Server Configuration
HOST=localhost
PORT=8000
LOG_LEVEL=info
`;
      fs.writeFileSync('.env', envContent, { mode: 0o600 });
      secureCredentials.setSecurePermissions('.env');
      console.log(chalk.green('✓ Configuration saved to .env file (without API key)'));
    } catch (error) {
      console.log(chalk.red(`✗ Failed to store in keychain: ${error.message}`));
      console.log(chalk.yellow('Falling back to encrypted file storage...'));

      try {
        secureCredentials.storeInEncryptedFile(answers.apiKey);

        // Also create .env file WITHOUT the API key
        const envContent = `# OpenRouter Configuration
# API key is stored securely in encrypted file
OPENROUTER_APP_NAME=${answers.appName}
OPENROUTER_HTTP_REFERER=${answers.httpReferer}

# Server Configuration
HOST=localhost
PORT=8000
LOG_LEVEL=info
`;
        fs.writeFileSync('.env', envContent, { mode: 0o600 });
        secureCredentials.setSecurePermissions('.env');
        console.log(chalk.green('✓ Configuration saved to .env file (without API key)'));
      } catch (encError) {
        console.log(chalk.red(`✗ Failed to store in encrypted file: ${encError.message}`));
        console.log(chalk.yellow('Falling back to .env file storage...'));
        secureCredentials.displaySecurityWarning('PLAINTEXT_STORAGE');

        const { confirmPlaintext } = await inquirer.prompt([
          {
            type: 'confirm',
            name: 'confirmPlaintext',
            message: 'Store API key in plaintext .env file?',
            default: false
          }
        ]);

        if (!confirmPlaintext) {
          console.log(chalk.blue('Setup cancelled.'));
          return;
        }

        secureCredentials.storeInEnvFile(answers.apiKey, answers.appName, answers.httpReferer);
      }
    }
  } else if (storageMethod === 'encrypted') {
    try {
      secureCredentials.storeInEncryptedFile(answers.apiKey);

      // Also create .env file WITHOUT the API key
      const envContent = `# OpenRouter Configuration
# API key is stored securely in encrypted file
OPENROUTER_APP_NAME=${answers.appName}
OPENROUTER_HTTP_REFERER=${answers.httpReferer}

# Server Configuration
HOST=localhost
PORT=8000
LOG_LEVEL=info
`;
      fs.writeFileSync('.env', envContent, { mode: 0o600 });
      secureCredentials.setSecurePermissions('.env');
      console.log(chalk.green('✓ Configuration saved to .env file (without API key)'));
    } catch (error) {
      console.log(chalk.red(`✗ Failed to store in encrypted file: ${error.message}`));
      console.log(chalk.yellow('Falling back to .env file storage...'));
      secureCredentials.displaySecurityWarning('PLAINTEXT_STORAGE');

      const { confirmPlaintext } = await inquirer.prompt([
        {
          type: 'confirm',
          name: 'confirmPlaintext',
          message: 'Store API key in plaintext .env file?',
          default: false
        }
      ]);

      if (!confirmPlaintext) {
        console.log(chalk.blue('Setup cancelled.'));
        return;
      }

      secureCredentials.storeInEnvFile(answers.apiKey, answers.appName, answers.httpReferer);
    }
  } else if (storageMethod === 'env') {
    // Show security warning for plaintext storage
    secureCredentials.displaySecurityWarning('PLAINTEXT_STORAGE');

    const { confirmPlaintext } = await inquirer.prompt([
      {
        type: 'confirm',
        name: 'confirmPlaintext',
        message: chalk.yellow('I understand the risks. Store API key in plaintext .env file?'),
        default: false
      }
    ]);

    if (!confirmPlaintext) {
      console.log(chalk.blue('Setup cancelled. Consider installing keytar for secure storage:'));
      console.log(chalk.gray('  npm install keytar'));
      return;
    }

    secureCredentials.storeInEnvFile(answers.apiKey, answers.appName, answers.httpReferer);
  }

  console.log(chalk.cyan('\n─────────────────────────────────────────────────────────────\n'));
  console.log(chalk.bold('Claude Integration Configuration\n'));

  // Ask about Claude integrations with security warnings
  const { integrations } = await inquirer.prompt([
    {
      type: 'checkbox',
      name: 'integrations',
      message: 'Which Claude integrations would you like to configure?',
      choices: [
        {
          name: `Claude Desktop ${chalk.gray('(stores API key in config file)')}`,
          value: 'desktop',
          checked: false
        },
        {
          name: `Claude Code CLI ${chalk.gray('(registers via claude mcp add)')}`,
          value: 'code',
          checked: false
        }
      ]
    }
  ]);

  if (integrations.length > 0) {
    if (integrations.includes('desktop')) {
      console.log(chalk.yellow('\n⚠️  Claude Desktop stores the API key in its configuration file.'));
      console.log(chalk.yellow('The Claude Desktop config will contain your API key in PLAINTEXT.\n'));

      const { confirmClaudeDesktopConfig } = await inquirer.prompt([
        {
          type: 'confirm',
          name: 'confirmClaudeDesktopConfig',
          message: 'Do you consent to storing your API key in Claude Desktop config?',
          default: false
        }
      ]);

      if (confirmClaudeDesktopConfig) {
        await installClaudeConfig(answers.apiKey);
      } else {
        console.log(chalk.blue('Skipping Claude Desktop integration.'));
      }
    }

    if (integrations.includes('code')) {
      await installClaudeCodeConfig();
    }
  }

  console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════'));
  console.log(chalk.green('✅ Initialization complete!\n'));
  console.log(chalk.white('Next steps:'));
  console.log(chalk.gray('  1. Run: openrouter-mcp start'));
  console.log(chalk.gray('  2. Review security documentation: docs/SECURITY.md'));
  console.log(chalk.gray('  3. Set up API key rotation reminders (recommended: every 90 days)'));
  console.log(chalk.cyan('═══════════════════════════════════════════════════════════\n'));
}

async function checkStatus() {
  console.log(chalk.blue('Environment:'));

  // Python check
  const pythonInfo = await resolveSupportedPythonCommand(runCommand);
  if (pythonInfo.status === 'supported') {
    console.log(chalk.green(`  ✓ Python: ${pythonInfo.version} (${pythonInfo.command})`));
  } else if (pythonInfo.status === 'unsupported') {
    console.log(chalk.red(`  ✗ Python: ${pythonInfo.version}`));
    console.log(chalk.yellow(`    ${getUnsupportedPythonMessage(pythonInfo.version)}`));
  } else {
    console.log(chalk.red('  ✗ Python: Not found'));
    console.log(chalk.yellow(`    ${getMissingPythonMessage()}`));
  }

  // API key check
  if (await checkApiKey()) {
    console.log(chalk.green('  ✓ OpenRouter API Key: Configured'));
  } else {
    console.log(chalk.red('  ✗ OpenRouter API Key: Not configured'));
  }

  // Dependencies check
  if (pythonInfo.status === 'supported') {
    try {
      await runCommand(pythonInfo.command, ['-c', 'import fastmcp, httpx, pydantic']);
      console.log(chalk.green('  ✓ Python Dependencies: Installed'));
    } catch {
      console.log(chalk.red('  ✗ Python Dependencies: Missing'));
    }
  } else {
    console.log(chalk.yellow('  ⚠ Python Dependencies: Not checked (Python unavailable)'));
  }

  console.log(chalk.blue('\nConfiguration:'));
  const envPath = path.join(process.cwd(), '.env');
  if (fs.existsSync(envPath)) {
    console.log(chalk.green('  ✓ .env file: Found'));
  } else {
    console.log(chalk.yellow('  ⚠  .env file: Not found'));
  }
}

async function installClaudeConfig(apiKey = null) {
  const inquirer = (await import('inquirer')).default;

  // Get API key if not provided
  if (!apiKey) {
    const keyResult = await secureCredentials.getApiKey();
    if (!keyResult.key) {
      console.log(chalk.red('✗ No API key found. Please run "openrouter-mcp init" first.'));
      return;
    }
    apiKey = keyResult.key;

    // Show security warning and get consent
    console.log(chalk.yellow('\n⚠️  Claude Desktop requires storing the API key in a configuration file.'));
    console.log(chalk.yellow('The API key will be stored in PLAINTEXT.\n'));

    const { confirmInstall } = await inquirer.prompt([
      {
        type: 'confirm',
        name: 'confirmInstall',
        message: 'Do you consent to storing your API key in Claude Desktop config?',
        default: false
      }
    ]);

    if (!confirmInstall) {
      console.log(chalk.blue('Installation cancelled.'));
      return;
    }
  }

  const configPath = secureCredentials.getClaudeDesktopConfigPath();

  // Create directory if it doesn't exist
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

  // Add OpenRouter MCP server
  config.mcpServers = config.mcpServers || {};
  config.mcpServers.openrouter = {
    command: "npx",
    args: [MCP_PACKAGE_NAME, "start"],
    env: {
      OPENROUTER_API_KEY: apiKey
    }
  };

  // Write config with secure permissions
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2), { mode: 0o600 });
  secureCredentials.setSecurePermissions(configPath);

  console.log(chalk.green(`✓ Claude Desktop configuration updated: ${configPath}`));
  console.log(chalk.blue('💡 Restart Claude Desktop to use OpenRouter tools'));
}

async function installClaudeCodeConfig() {
  const keyResult = await secureCredentials.getApiKey();
  const installCommand = buildClaudeCodeInstallCommand(MCP_PACKAGE_NAME);
  const removeCommand = buildClaudeCodeRemoveCommand();
  const configPath = getClaudeCodeUserConfigPath();

  try {
    try {
      await runCommand(removeCommand.command, removeCommand.args);
      console.log(chalk.gray('ℹ️  Replacing existing Claude Code user-scope OpenRouter entry'));
    } catch (error) {
      // Ignore if the server is not already registered.
    }

    await runCommand(installCommand.command, installCommand.args);
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      console.log(chalk.red('✗ Claude Code CLI not found in PATH'));
      console.log(chalk.blue('Install Claude Code first, then rerun this command.'));
    } else {
      console.log(chalk.red(`✗ Failed to configure Claude Code CLI: ${error.message}`));
    }

    console.log(chalk.blue('\nRun this command manually in Claude Code-enabled shell:'));
    console.log(chalk.gray(`  ${formatCommand(installCommand.command, installCommand.args)}`));
    return;
  }

  if (fs.existsSync(configPath)) {
    secureCredentials.setSecurePermissions(configPath);
  }

  console.log(chalk.green(`✓ Claude Code CLI configuration updated: ${configPath}`));
  console.log(chalk.blue('💡 Installed via native "claude mcp add" user-scope flow.'));
  console.log(chalk.blue('💡 Claude Code stores only the MCP command, not your API key.'));
  console.log(chalk.blue('💡 openrouter-mcp start resolves the key from secure storage or environment at runtime.'));
  if (!keyResult.key) {
    console.log(chalk.yellow('⚠️  No API key is configured yet. Run "openrouter-mcp init" or export OPENROUTER_API_KEY before use.'));
  }
  console.log(chalk.blue('💡 Use commands like: "List available AI models using OpenRouter"'));

  console.log(chalk.cyan('\n📝 Claude Code registration command:'));
  console.log(chalk.gray(`  ${formatCommand(installCommand.command, installCommand.args)}`));
}

async function rotateApiKey() {
  const inquirer = (await import('inquirer')).default;

  console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════'));
  console.log(chalk.cyan('  API Key Rotation'));
  console.log(chalk.cyan('═══════════════════════════════════════════════════════════\n'));

  console.log(chalk.white('This will update your API key in all configured locations.\n'));

  // Get new API key
  const { newApiKey, confirmRotation } = await inquirer.prompt([
    {
      type: 'password',
      name: 'newApiKey',
      message: 'Enter your new OpenRouter API key:',
      mask: '*',
      validate: (input) => input.length > 0 || 'API key cannot be empty'
    },
    {
      type: 'confirm',
      name: 'confirmRotation',
      message: 'Update API key in all configured locations?',
      default: true
    }
  ]);

  if (!confirmRotation) {
    console.log(chalk.blue('Rotation cancelled.'));
    return;
  }

  try {
    const locations = await secureCredentials.rotateApiKey(newApiKey);

    if (locations.length > 0) {
      console.log(chalk.green('\n✅ API key rotation complete!'));
      console.log(chalk.white('\nNext steps:'));
      console.log(chalk.gray('  1. Revoke your old API key on OpenRouter dashboard'));
      console.log(chalk.gray('  2. Restart Claude Desktop/Code if they were configured'));
      console.log(chalk.gray('  3. Test the new key: openrouter-mcp start'));
    } else {
      console.log(chalk.yellow('\n⚠️  No existing credential storage found.'));
      console.log(chalk.blue('Run "openrouter-mcp init" to configure credentials.'));
    }
  } catch (error) {
    console.log(chalk.red(`\n✗ Rotation failed: ${error.message}`));
  }

  console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════\n'));
}

async function deleteCredentials() {
  const inquirer = (await import('inquirer')).default;

  console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════'));
  console.log(chalk.cyan('  Delete Credentials'));
  console.log(chalk.cyan('═══════════════════════════════════════════════════════════\n'));

  console.log(chalk.red('⚠️  WARNING: This will remove your API key from all locations:'));
  console.log(chalk.gray('  • OS Keychain (if configured)'));
  console.log(chalk.gray('  • .env file'));
  console.log(chalk.gray('  • Claude Desktop config'));
  console.log(chalk.gray('  • Claude Code config\n'));

  const { confirmDelete } = await inquirer.prompt([
    {
      type: 'confirm',
      name: 'confirmDelete',
      message: chalk.red('Are you sure you want to delete all credentials?'),
      default: false
    }
  ]);

  if (!confirmDelete) {
    console.log(chalk.blue('Deletion cancelled.'));
    return;
  }

  try {
    const locations = await secureCredentials.deleteAllCredentials();

    if (locations.length > 0) {
      console.log(chalk.green('\n✅ Credentials deleted successfully!'));
      console.log(chalk.gray('Run "openrouter-mcp init" to reconfigure.'));
    } else {
      console.log(chalk.yellow('\n⚠️  No credentials found to delete.'));
    }
  } catch (error) {
    console.log(chalk.red(`\n✗ Deletion failed: ${error.message}`));
  }

  console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════\n'));
}

async function securityAudit() {
  console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════'));
  console.log(chalk.cyan('  Security Audit'));
  console.log(chalk.cyan('═══════════════════════════════════════════════════════════\n'));

  // Perform comprehensive audit
  const audit = await secureCredentials.performSecurityAudit();

  const issues = [];
  const warnings = [];
  const good = [];

  // Display environment analysis
  console.log(chalk.bold('Environment Analysis:\n'));
  if (audit.environment.shared) {
    issues.push('! Shared/enterprise environment detected');
    console.log(chalk.red('  ! Shared Environment: Detected'));
    audit.environment.indicators.forEach(ind => {
      console.log(chalk.yellow(`    - ${ind.type} (${ind.severity} severity)`));
    });
    console.log(chalk.yellow(`\n  Recommendation: ${audit.environment.recommendation}\n`));
  } else {
    good.push('✓ Single-user environment detected');
    console.log(chalk.green('  ✓ Environment: Single-user\n'));
  }

  // Check for API key storage locations
  console.log(chalk.bold('Credential Storage:\n'));

  // Check OS Keychain
  if (secureCredentials.keytarAvailable) {
    const keychainKey = await secureCredentials.getFromKeychain();
    if (keychainKey) {
      good.push('✓ API key stored in OS Keychain (encrypted)');
      console.log(chalk.green('  ✓ OS Keychain: API key found (encrypted)'));
      console.log(chalk.gray(`    Masked key: ${secureCredentials.maskApiKey(keychainKey)}`));
    } else {
      console.log(chalk.gray('  ○ OS Keychain: Not configured'));
    }
  } else {
    warnings.push('⚠ OS Keychain not available - install keytar for secure storage');
    console.log(chalk.yellow('  ⚠  OS Keychain: Not available (install keytar)'));
  }

  // Check encrypted file
  const encryptedKey = secureCredentials.getFromEncryptedFile();
  if (encryptedKey) {
    good.push('✓ API key stored in encrypted file');
    console.log(chalk.green('  ✓ Encrypted File: API key found (AES-256-GCM)'));
    console.log(chalk.gray(`    Masked key: ${secureCredentials.maskApiKey(encryptedKey)}`));
  } else {
    console.log(chalk.gray('  ○ Encrypted File: Not configured'));
  }

  // Check .env file
  const envPath = path.join(process.cwd(), '.env');
  if (fs.existsSync(envPath)) {
    const stats = fs.statSync(envPath);
    const envContent = fs.readFileSync(envPath, 'utf8');
    const hasApiKey = envContent.includes('OPENROUTER_API_KEY=sk-or-');

    if (hasApiKey) {
      console.log(chalk.yellow('  ⚠  .env file: Contains API key (plaintext)'));
      warnings.push('⚠ API key stored in plaintext .env file');

      // Check file permissions
      if (os.platform() !== 'win32') {
        const mode = stats.mode & parseInt('777', 8);
        if (mode === parseInt('600', 8)) {
          good.push('✓ .env file has secure permissions (600)');
          console.log(chalk.green('    ✓ Permissions: 600 (secure)'));
        } else {
          issues.push(`! .env file has insecure permissions (${mode.toString(8)})`);
          console.log(chalk.red(`    ! Permissions: ${mode.toString(8)} (should be 600)`));
        }
      }
    } else {
      console.log(chalk.green('  ✓ .env file: No API key (settings only)'));
      good.push('✓ .env file does not contain API key');
    }
  } else {
    console.log(chalk.gray('  ○ .env file: Not found'));
  }

  // Check .gitignore
  const gitignorePath = path.join(process.cwd(), '.gitignore');
  if (fs.existsSync(gitignorePath)) {
    const gitignoreContent = fs.readFileSync(gitignorePath, 'utf8');
    if (gitignoreContent.includes('.env')) {
      good.push('✓ .env is in .gitignore');
      console.log(chalk.green('  ✓ .gitignore: .env is excluded from version control'));
    } else {
      issues.push('! .env not in .gitignore - risk of credential exposure');
      console.log(chalk.red('  ! .gitignore: .env NOT excluded (add it!)'));
    }
  }

  // Check Claude configs
  console.log(chalk.bold('\n\nClaude Integrations:\n'));

  const claudeDesktopPath = secureCredentials.getClaudeDesktopConfigPath();
  if (fs.existsSync(claudeDesktopPath)) {
    const stats = fs.statSync(claudeDesktopPath);
    let claudeDesktopConfig = null;
    let claudeDesktopParseFailed = false;

    try {
      claudeDesktopConfig = JSON.parse(fs.readFileSync(claudeDesktopPath, 'utf8'));
    } catch (error) {
      claudeDesktopParseFailed = true;
    }

    if (claudeDesktopParseFailed) {
      warnings.push('⚠ Claude Desktop config could not be parsed for secret audit');
      console.log(chalk.yellow('  ⚠  Claude Desktop: Config exists but could not be parsed for secret audit'));
    } else if (configContainsPlaintextOpenRouterKey(claudeDesktopConfig)) {
      console.log(chalk.yellow('  ⚠  Claude Desktop: Config contains API key (plaintext)'));
      warnings.push('⚠ Claude Desktop config contains plaintext API key');
    } else {
      console.log(chalk.green('  ✓ Claude Desktop: No inline OpenRouter API key detected'));
      good.push('✓ Claude Desktop config does not inline OpenRouter API key');
    }

    if (os.platform() !== 'win32') {
      const mode = stats.mode & parseInt('777', 8);
      if (mode === parseInt('600', 8)) {
        good.push('✓ Claude Desktop config has secure permissions');
        console.log(chalk.green('    ✓ Permissions: 600 (secure)'));
      } else {
        issues.push('! Claude Desktop config has insecure permissions');
        console.log(chalk.red(`    ! Permissions: ${mode.toString(8)} (should be 600)`));
      }
    }
  } else {
    console.log(chalk.gray('  ○ Claude Desktop: Not configured'));
  }

  const claudeCodePath = secureCredentials.getClaudeCodeConfigPath();
  if (fs.existsSync(claudeCodePath)) {
    const stats = fs.statSync(claudeCodePath);
    let claudeCodeConfig = null;
    let claudeCodeParseFailed = false;

    try {
      claudeCodeConfig = JSON.parse(fs.readFileSync(claudeCodePath, 'utf8'));
    } catch (error) {
      claudeCodeParseFailed = true;
    }

    if (claudeCodeParseFailed) {
      warnings.push('⚠ Claude Code config could not be parsed for secret audit');
      console.log(chalk.yellow('  ⚠  Claude Code: Config exists but could not be parsed for secret audit'));
    } else if (configContainsPlaintextOpenRouterKey(claudeCodeConfig)) {
      console.log(chalk.yellow('  ⚠  Claude Code: Config contains API key (plaintext)'));
      warnings.push('⚠ Claude Code config contains plaintext API key');
    } else {
      console.log(chalk.green('  ✓ Claude Code: No inline OpenRouter API key detected'));
      good.push('✓ Claude Code config does not inline OpenRouter API key');
    }

    if (os.platform() !== 'win32') {
      const mode = stats.mode & parseInt('777', 8);
      if (mode === parseInt('600', 8)) {
        good.push('✓ Claude Code config has secure permissions');
        console.log(chalk.green('    ✓ Permissions: 600 (secure)'));
      } else {
        issues.push('! Claude Code config has insecure permissions');
        console.log(chalk.red(`    ! Permissions: ${mode.toString(8)} (should be 600)`));
      }
    }
  } else {
    console.log(chalk.gray('  ○ Claude Code: Not configured'));
  }

  // Environment detection
  console.log(chalk.bold('\n\nEnvironment Analysis:\n'));

  if (secureCredentials.isSharedEnvironment()) {
    issues.push('! Shared/enterprise environment detected');
    console.log(chalk.red('  ! Shared Environment: Detected'));
    console.log(chalk.red('    Recommend: Use enterprise secrets management'));
  } else {
    good.push('✓ Single-user environment detected');
    console.log(chalk.green('  ✓ Environment: Single-user'));
  }

  // Summary
  console.log(chalk.cyan('\n─────────────────────────────────────────────────────────────'));
  console.log(chalk.bold('Summary:\n'));

  if (issues.length > 0) {
    console.log(chalk.red(`  Critical Issues (${issues.length}):`));
    issues.forEach(issue => console.log(chalk.red(`    ${issue}`)));
    console.log('');
  }

  if (warnings.length > 0) {
    console.log(chalk.yellow(`  Warnings (${warnings.length}):`));
    warnings.forEach(warning => console.log(chalk.yellow(`    ${warning}`)));
    console.log('');
  }

  if (good.length > 0) {
    console.log(chalk.green(`  Good Practices (${good.length}):`));
    good.forEach(item => console.log(chalk.green(`    ${item}`)));
    console.log('');
  }

  console.log(chalk.bold('Recommendations:\n'));

  if (!secureCredentials.keytarAvailable) {
    console.log(chalk.blue('  1. Install keytar for OS Keychain support:'));
    console.log(chalk.gray('     npm install keytar'));
  }

  if (warnings.some(w => w.includes('plaintext'))) {
    console.log(chalk.blue('  2. Consider migrating to OS Keychain storage'));
    console.log(chalk.gray('     openrouter-mcp rotate-key'));
  }

  if (issues.some(i => i.includes('.gitignore'))) {
    console.log(chalk.blue('  3. Add .env to .gitignore immediately'));
    console.log(chalk.gray('     echo ".env" >> .gitignore'));
  }

  console.log(chalk.blue('  4. Review security documentation:'));
  console.log(chalk.gray('     docs/SECURITY.md'));

  console.log(chalk.blue('  5. Set up API key rotation reminder (every 90 days)'));

  // Offer to fix permissions
  if (audit.vulnerabilities.some(v => v.issue.includes('permissions'))) {
    console.log(chalk.cyan('\n─────────────────────────────────────────────────────────────'));
    console.log(chalk.yellow('\nPermission issues detected. Would you like to fix them automatically?'));
    console.log(chalk.gray('This will set file permissions to 600 (owner read/write only)\n'));

    const inquirer = (await import('inquirer')).default;
    const { fixPerms } = await inquirer.prompt([
      {
        type: 'confirm',
        name: 'fixPerms',
        message: 'Fix file permissions now?',
        default: true
      }
    ]);

    if (fixPerms) {
      const fixed = secureCredentials.fixPermissions();
      if (fixed.length > 0) {
        console.log(chalk.green('\n✓ Fixed permissions for:'));
        fixed.forEach(f => console.log(chalk.gray(`  - ${f.path}`)));
      }
    }
  }

  console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════\n'));
}

async function migrateEncryption() {
  const inquirer = (await import('inquirer')).default;
  const cryptoManager = require('./crypto-manager');

  console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════'));
  console.log(chalk.cyan('  Encryption Migration v1.0 → v2.0'));
  console.log(chalk.cyan('═══════════════════════════════════════════════════════════\n'));

  console.log(chalk.white('This will migrate your encrypted credentials from v1.0 to v2.0:'));
  console.log(chalk.gray('  • v1.0: Deterministic key derivation (INSECURE - machine-specific)'));
  console.log(chalk.gray('  • v2.0: Random 256-bit master key + OS Keystore (SECURE)\n'));

  // Check if keytar is available
  if (!cryptoManager.isKeystoreAvailable()) {
    console.log(chalk.red('✗ OS Keystore not available'));
    console.log(chalk.yellow('⚠️  v2.0 requires keytar for OS Keystore integration'));
    console.log(chalk.blue('\nInstall keytar to continue:'));
    console.log(chalk.gray('  npm install keytar\n'));
    return;
  }

  // Check for v1.0 encrypted file
  const CONFIG_DIR = path.join(os.homedir(), '.openrouter-mcp');
  const ENCRYPTED_FILE = path.join(CONFIG_DIR, '.credentials.enc');

  if (!fs.existsSync(ENCRYPTED_FILE)) {
    console.log(chalk.yellow('⚠️  No encrypted credentials file found'));
    console.log(chalk.gray('  Location: ' + ENCRYPTED_FILE));
    console.log(chalk.blue('\nNothing to migrate.'));
    return;
  }

  // Read and detect version
  try {
    const encryptedData = JSON.parse(fs.readFileSync(ENCRYPTED_FILE, 'utf8'));
    const version = cryptoManager.detectEncryptionVersion(encryptedData);

    if (version === '2.0') {
      console.log(chalk.green('✓ Credentials are already using v2.0 encryption'));
      console.log(chalk.gray('  No migration needed.\n'));
      return;
    }

    console.log(chalk.yellow(`⚠️  Detected v${version} encryption format`));
    console.log(chalk.gray(`  File: ${ENCRYPTED_FILE}\n`));

    // Confirm migration
    const { confirmMigration } = await inquirer.prompt([
      {
        type: 'confirm',
        name: 'confirmMigration',
        message: 'Proceed with migration to v2.0?',
        default: true
      }
    ]);

    if (!confirmMigration) {
      console.log(chalk.blue('Migration cancelled.'));
      return;
    }

    console.log(chalk.blue('\n🔄 Starting migration...\n'));

    // Step 1: Decrypt using v1.0
    console.log(chalk.gray('  [1/4] Decrypting v1.0 credentials...'));
    const decrypted = cryptoManager.decryptLegacyV1(encryptedData);
    console.log(chalk.green('  ✓ Decryption successful'));

    // Step 2: Generate and store master key
    console.log(chalk.gray('  [2/4] Generating 256-bit master key...'));
    const masterKey = cryptoManager.generateMasterKey();
    console.log(chalk.green('  ✓ Master key generated'));

    console.log(chalk.gray('  [3/4] Storing master key in OS Keystore...'));
    await cryptoManager.storeMasterKeySecurely(masterKey);
    console.log(chalk.green('  ✓ Master key stored securely'));

    // Step 3: Re-encrypt with v2.0
    console.log(chalk.gray('  [4/4] Re-encrypting with v2.0...'));
    const encryptedV2 = cryptoManager.encryptWithMasterKey(decrypted, masterKey);

    const newData = JSON.stringify({
      ...encryptedV2,
      created: new Date().toISOString(),
      hostname: os.hostname(),
      migratedFrom: version,
      migratedAt: new Date().toISOString()
    });

    // Backup old file
    const backupFile = ENCRYPTED_FILE + '.v1.backup';
    fs.copyFileSync(ENCRYPTED_FILE, backupFile);
    console.log(chalk.gray(`  ✓ Backup created: ${backupFile}`));

    // Write new encrypted file
    fs.writeFileSync(ENCRYPTED_FILE, newData, { mode: 0o600 });
    secureCredentials.setSecurePermissions(ENCRYPTED_FILE);

    console.log(chalk.green('  ✓ Migration complete!\n'));

    // Verify migration
    console.log(chalk.gray('  Verifying migration...'));
    const verification = JSON.parse(fs.readFileSync(ENCRYPTED_FILE, 'utf8'));
    const verifiedDecrypted = cryptoManager.decryptWithMasterKey(verification, masterKey);

    if (verifiedDecrypted === decrypted) {
      console.log(chalk.green('  ✓ Verification successful\n'));
    } else {
      throw new Error('Verification failed - decrypted data does not match');
    }

    console.log(chalk.cyan('─────────────────────────────────────────────────────────────'));
    console.log(chalk.green('\n✅ Migration Complete!\n'));
    console.log(chalk.white('Summary:'));
    console.log(chalk.gray(`  • Old version: v${version} (deterministic key)`));
    console.log(chalk.gray('  • New version: v2.0 (random master key + OS Keystore)'));
    console.log(chalk.gray(`  • Backup location: ${backupFile}`));
    console.log(chalk.gray(`  • Master key stored in: OS Keystore`));

    console.log(chalk.white('\nNext steps:'));
    console.log(chalk.gray('  1. Test decryption: openrouter-mcp start'));
    console.log(chalk.gray('  2. Run security audit: openrouter-mcp security-audit'));
    console.log(chalk.gray('  3. Delete backup once verified: rm ' + backupFile));

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════\n'));

  } catch (error) {
    console.log(chalk.red(`\n✗ Migration failed: ${error.message}\n`));
    console.log(chalk.yellow('Your original credentials are still intact.'));
    console.log(chalk.blue('Please report this issue with the error message above.'));
    console.log(chalk.cyan('\n═══════════════════════════════════════════════════════════\n'));
  }
}

function runCommand(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ['pipe', 'pipe', 'pipe'] });
    let output = '';
    let error = '';
    let settled = false;

    child.stdout.on('data', (data) => {
      output += data.toString();
    });

    child.stderr.on('data', (data) => {
      error += data.toString();
    });

    child.on('error', (spawnError) => {
      if (settled) return;
      settled = true;
      reject(spawnError);
    });

    child.on('close', (code) => {
      if (settled) return;
      settled = true;
      if (code === 0) {
        resolve((output || error).trim());
      } else {
        reject(new Error(error || `Command failed with code ${code}`));
      }
    });
  });
}

function formatCommand(command, args) {
  return [command, ...args]
    .map((part) => {
      if (/[\s"]/u.test(part)) {
        return `"${part.replace(/"/g, '\\"')}"`;
      }
      return part;
    })
    .join(' ');
}

// Parse command line arguments
program.parse();

// If no command is provided, show help
if (!process.argv.slice(2).length) {
  program.outputHelp();
}
