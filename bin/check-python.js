#!/usr/bin/env node

const { spawn } = require('child_process');
const chalk = require('chalk');

function checkPython() {
  return new Promise((resolve) => {
    const python = spawn('python', ['--version'], { stdio: 'pipe' });
    
    python.on('close', (code) => {
      if (code === 0) {
        console.log(chalk.green('✓ Python is available'));
        resolve(true);
      } else {
        console.log(chalk.yellow('⚠️  Python not found in PATH'));
        console.log(chalk.blue('Please install Python 3.9+ from https://python.org'));
        console.log(chalk.blue('Make sure Python is added to your system PATH'));
        resolve(false);
      }
    });
    
    python.on('error', () => {
      console.log(chalk.yellow('⚠️  Python not found'));
      console.log(chalk.blue('Please install Python 3.9+ from https://python.org'));
      resolve(false);
    });
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