#!/usr/bin/env node

const { spawn } = require('child_process');
const chalk = require('chalk');
const {
  getMissingPythonMessage,
  getUnsupportedPythonMessage,
  resolveSupportedPythonCommand,
} = require('./python-version');

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

    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) {
        resolve((output || error).trim());
      } else {
        reject(new Error(error || `Command failed with code ${code}`));
      }
    });
  });
}

function checkPython() {
  return resolveSupportedPythonCommand(runCommand).then((pythonInfo) => {
    if (pythonInfo.status === 'supported') {
      console.log(chalk.green(`✓ Python is available: ${pythonInfo.version} (${pythonInfo.command})`));
      return true;
    }

    if (pythonInfo.status === 'unsupported') {
      console.log(chalk.yellow('⚠️  Unsupported Python version detected'));
      console.log(chalk.blue(getUnsupportedPythonMessage(pythonInfo.version)));
      return false;
    }

    console.log(chalk.yellow('⚠️  Python not found in PATH'));
    console.log(chalk.blue(getMissingPythonMessage()));
    console.log(chalk.blue('Make sure Python is added to your system PATH'));
    return false;
  });
}

if (require.main === module) {
  checkPython().then((success) => {
    if (!success) {
      console.log(chalk.blue('\n💡 After installing Python, you can run:'));
      console.log(chalk.blue('   npx openrouter-mcp init    # Configure the server'));
      console.log(chalk.blue('   npx openrouter-mcp start   # Start the server'));
    }
  });
}

module.exports = { checkPython };
