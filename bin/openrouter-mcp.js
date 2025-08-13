#!/usr/bin/env node

const { program } = require('commander');
const chalk = require('chalk');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const packageJson = require('../package.json');

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
    
    if (!await checkPythonRequirements()) {
      process.exit(1);
    }
    
    if (!await checkApiKey()) {
      console.log(chalk.yellow('⚠️  No OpenRouter API key found. Run "openrouter-mcp init" to configure.'));
    }
    
    await startServer(options);
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
  .description('Install configuration for Claude Code CLI')
  .action(async () => {
    console.log(chalk.green('💻 Installing Claude Code CLI configuration...'));
    await installClaudeCodeConfig();
  });

async function checkPythonRequirements() {
  console.log(chalk.blue('🐍 Checking Python environment...'));
  
  try {
    // Check Python version
    const pythonVersion = await runCommand('python', ['--version']);
    console.log(chalk.green(`✓ Python found: ${pythonVersion.trim()}`));
    
    // Check if in virtual environment
    const isVenv = process.env.VIRTUAL_ENV || process.env.CONDA_DEFAULT_ENV;
    if (isVenv) {
      console.log(chalk.green(`✓ Virtual environment: ${isVenv}`));
    } else {
      console.log(chalk.yellow('⚠️  No virtual environment detected. Consider using one.'));
    }
    
    // Check required packages
    try {
      await runCommand('python', ['-c', 'import fastmcp, httpx, pydantic']);
      console.log(chalk.green('✓ Required Python packages are installed'));
      return true;
    } catch (error) {
      console.log(chalk.red('✗ Missing required Python packages'));
      console.log(chalk.blue('Installing Python dependencies...'));
      
      try {
        await runCommand('pip', ['install', '-r', path.join(__dirname, '..', 'requirements.txt')]);
        console.log(chalk.green('✓ Python dependencies installed successfully'));
        return true;
      } catch (installError) {
        console.log(chalk.red('✗ Failed to install Python dependencies'));
        console.log(chalk.blue('Please run: pip install -r requirements.txt'));
        return false;
      }
    }
    
  } catch (error) {
    console.log(chalk.red('✗ Python not found or not accessible'));
    console.log(chalk.blue('Please install Python 3.9+ and ensure it\'s in your PATH'));
    return false;
  }
}

async function checkApiKey() {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (apiKey) {
    console.log(chalk.green('✓ OpenRouter API key is configured'));
    return true;
  }
  
  // Check .env file in multiple locations
  const possibleEnvPaths = [
    path.join(process.cwd(), '.env'),
    path.join(__dirname, '..', '.env'),
    path.join(os.homedir(), '.openrouter-mcp.env')
  ];
  
  for (const envPath of possibleEnvPaths) {
    if (fs.existsSync(envPath) && fs.statSync(envPath).isFile()) {
      try {
        const envContent = fs.readFileSync(envPath, 'utf8');
        if (envContent.includes('OPENROUTER_API_KEY=')) {
          console.log(chalk.green(`✓ OpenRouter API key found in ${envPath}`));
          return true;
        }
      } catch (error) {
        // Ignore read errors and continue
        continue;
      }
    }
  }
  
  return false;
}

async function startServer(options) {
  const serverPath = path.join(__dirname, '..', 'src', 'openrouter_mcp', 'server.py');
  
  const env = {
    ...process.env,
    HOST: options.host,
    PORT: options.port.toString(),
    LOG_LEVEL: program.opts().debug ? 'debug' : (program.opts().verbose ? 'info' : 'warning')
  };
  
  console.log(chalk.blue(`Starting server on ${options.host}:${options.port}`));
  
  const python = spawn('python', [serverPath], {
    env,
    stdio: 'inherit'
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
  
  const answers = await inquirer.prompt([
    {
      type: 'input',
      name: 'apiKey',
      message: 'Enter your OpenRouter API key:',
      validate: (input) => input.length > 0 || 'API key cannot be empty'
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
  
  // Create .env file
  const envContent = `# OpenRouter API Configuration
OPENROUTER_API_KEY=${answers.apiKey}
OPENROUTER_APP_NAME=${answers.appName}
OPENROUTER_HTTP_REFERER=${answers.httpReferer}

# Server Configuration
HOST=localhost
PORT=8000
LOG_LEVEL=info
`;
  
  fs.writeFileSync('.env', envContent);
  console.log(chalk.green('✓ Configuration saved to .env file'));
  
  // Ask about Claude integrations
  const { integrations } = await inquirer.prompt([
    {
      type: 'checkbox',
      name: 'integrations',
      message: 'Which Claude integrations would you like to configure?',
      choices: [
        { name: 'Claude Desktop', value: 'desktop', checked: true },
        { name: 'Claude Code CLI', value: 'code', checked: true }
      ]
    }
  ]);
  
  if (integrations.includes('desktop')) {
    await installClaudeConfig();
  }
  
  if (integrations.includes('code')) {
    await installClaudeCodeConfig();
  }
  
  console.log(chalk.green('🎉 Initialization complete! Run "openrouter-mcp start" to begin.'));
}

async function checkStatus() {
  console.log(chalk.blue('Environment:'));
  
  // Python check
  try {
    const pythonVersion = await runCommand('python', ['--version']);
    console.log(chalk.green(`  ✓ Python: ${pythonVersion.trim()}`));
  } catch {
    console.log(chalk.red('  ✗ Python: Not found'));
  }
  
  // API key check
  if (await checkApiKey()) {
    console.log(chalk.green('  ✓ OpenRouter API Key: Configured'));
  } else {
    console.log(chalk.red('  ✗ OpenRouter API Key: Not configured'));
  }
  
  // Dependencies check
  try {
    await runCommand('python', ['-c', 'import fastmcp, httpx, pydantic']);
    console.log(chalk.green('  ✓ Python Dependencies: Installed'));
  } catch {
    console.log(chalk.red('  ✗ Python Dependencies: Missing'));
  }
  
  console.log(chalk.blue('\nConfiguration:'));
  const envPath = path.join(process.cwd(), '.env');
  if (fs.existsSync(envPath)) {
    console.log(chalk.green('  ✓ .env file: Found'));
  } else {
    console.log(chalk.yellow('  ⚠  .env file: Not found'));
  }
}

async function installClaudeConfig() {
  const homeDir = os.homedir();
  let configPath;
  
  // Determine Claude Desktop config path based on OS
  switch (os.platform()) {
    case 'darwin':
      configPath = path.join(homeDir, 'Library', 'Application Support', 'Claude', 'claude_desktop_config.json');
      break;
    case 'win32':
      configPath = path.join(homeDir, 'AppData', 'Roaming', 'Claude', 'claude_desktop_config.json');
      break;
    default:
      configPath = path.join(homeDir, '.config', 'claude', 'claude_desktop_config.json');
  }
  
  // Create directory if it doesn't exist
  const configDir = path.dirname(configPath);
  if (!fs.existsSync(configDir)) {
    fs.mkdirSync(configDir, { recursive: true });
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
    args: ["openrouter-mcp", "start"],
    env: {
      OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY || "your-openrouter-api-key"
    }
  };
  
  // Write config
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  console.log(chalk.green(`✓ Claude Desktop configuration updated: ${configPath}`));
  console.log(chalk.blue('💡 Restart Claude Desktop to use OpenRouter tools'));
}

async function installClaudeCodeConfig() {
  const homeDir = os.homedir();
  let configPath;
  
  // Determine Claude Code CLI config path based on OS
  switch (os.platform()) {
    case 'darwin':
      configPath = path.join(homeDir, '.claude', 'claude_code_config.json');
      break;
    case 'win32':
      configPath = path.join(homeDir, '.claude', 'claude_code_config.json');
      break;
    default:
      configPath = path.join(homeDir, '.claude', 'claude_code_config.json');
  }
  
  // Check if Claude Code CLI is installed
  try {
    await runCommand('claude-code', ['--version']);
    console.log(chalk.green('✓ Claude Code CLI detected'));
  } catch (error) {
    console.log(chalk.yellow('⚠️  Claude Code CLI not found. Please install it first:'));
    console.log(chalk.blue('   npm install -g @anthropic/claude-code'));
    console.log(chalk.blue('   or visit: https://docs.anthropic.com/en/docs/claude-code'));
    return;
  }
  
  // Create directory if it doesn't exist
  const configDir = path.dirname(configPath);
  if (!fs.existsSync(configDir)) {
    fs.mkdirSync(configDir, { recursive: true });
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
  
  // Check if API key is available
  const apiKey = process.env.OPENROUTER_API_KEY || 
    (fs.existsSync('.env') && fs.readFileSync('.env', 'utf8').match(/OPENROUTER_API_KEY=(.+)/)?.[1]) ||
    'your-openrouter-api-key';
  
  if (apiKey === 'your-openrouter-api-key') {
    console.log(chalk.yellow('⚠️  No API key found. Run "openrouter-mcp init" first to configure your API key.'));
  }
  
  // Add OpenRouter MCP server
  config.mcpServers = config.mcpServers || {};
  config.mcpServers.openrouter = {
    command: "npx",
    args: ["openrouter-mcp", "start"],
    env: {
      OPENROUTER_API_KEY: apiKey
    }
  };
  
  // Write config
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  console.log(chalk.green(`✓ Claude Code CLI configuration updated: ${configPath}`));
  console.log(chalk.blue('💡 OpenRouter tools are now available in Claude Code CLI'));
  console.log(chalk.blue('💡 Use commands like: "List available AI models using OpenRouter"'));
  
  // Show configuration example
  console.log(chalk.cyan('\n📝 Configuration added:'));
  console.log(chalk.gray(JSON.stringify({
    mcpServers: {
      openrouter: {
        command: "npx",
        args: ["openrouter-mcp", "start"],
        env: {
          OPENROUTER_API_KEY: "***"
        }
      }
    }
  }, null, 2)));
}

function runCommand(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ['pipe', 'pipe', 'pipe'] });
    let output = '';
    let error = '';
    
    child.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    child.stderr.on('data', (data) => {
      error += data.toString();
    });
    
    child.on('close', (code) => {
      if (code === 0) {
        resolve(output);
      } else {
        reject(new Error(error || `Command failed with code ${code}`));
      }
    });
  });
}

// Parse command line arguments
program.parse();

// If no command is provided, show help
if (!process.argv.slice(2).length) {
  program.outputHelp();
}