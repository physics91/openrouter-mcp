const { buildNpxStartArgs } = require('./package-launch-utils');

const CODEX_SERVER_NAME = 'openrouter-local';

function buildCodexInstallCommand(packageName, name = CODEX_SERVER_NAME) {
  return {
    command: 'codex',
    args: [
      'mcp',
      'add',
      name,
      '--env',
      'OPENROUTER_APP_NAME=codex-openrouter-local',
      '--env',
      'OPENROUTER_HTTP_REFERER=https://localhost:3000',
      '--env',
      'HOST=localhost',
      '--env',
      'PORT=8000',
      '--env',
      'LOG_LEVEL=info',
      '--',
      'npx',
      ...buildNpxStartArgs(packageName),
    ],
  };
}

function buildCodexRemoveCommand(name = CODEX_SERVER_NAME) {
  return {
    command: 'codex',
    args: ['mcp', 'remove', name],
  };
}

module.exports = {
  CODEX_SERVER_NAME,
  buildCodexInstallCommand,
  buildCodexRemoveCommand,
};
