const os = require('os');
const path = require('path');

const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);

function buildClaudeCodeServerConfig(packageName) {
  return {
    type: 'stdio',
    command: 'npx',
    args: [packageName, 'start']
  };
}

function buildClaudeCodeInstallCommand(packageName, scope = 'user') {
  return {
    command: 'claude',
    args: [
      'mcp',
      'add',
      '-t',
      'stdio',
      '-s',
      scope,
      'openrouter',
      '--',
      'npx',
      packageName,
      'start'
    ]
  };
}

function buildClaudeCodeRemoveCommand(name = 'openrouter', scope = 'user') {
  return {
    command: 'claude',
    args: ['mcp', 'remove', '-s', scope, name]
  };
}

function getClaudeCodeUserConfigPath(homeDir = os.homedir()) {
  return path.join(homeDir, '.claude.json');
}

function configContainsPlaintextOpenRouterKey(config) {
  if (!config || typeof config !== 'object') {
    return false;
  }

  const { mcpServers } = config;
  if (!mcpServers || typeof mcpServers !== 'object') {
    return false;
  }

  return Object.values(mcpServers).some((serverConfig) => {
    if (!serverConfig || typeof serverConfig !== 'object') {
      return false;
    }

    const { env } = serverConfig;
    return (
      env &&
      typeof env === 'object' &&
      hasOwn(env, 'OPENROUTER_API_KEY') &&
      typeof env.OPENROUTER_API_KEY === 'string' &&
      env.OPENROUTER_API_KEY.trim().length > 0
    );
  });
}

module.exports = {
  buildClaudeCodeInstallCommand,
  buildClaudeCodeRemoveCommand,
  buildClaudeCodeServerConfig,
  configContainsPlaintextOpenRouterKey,
  getClaudeCodeUserConfigPath,
};
