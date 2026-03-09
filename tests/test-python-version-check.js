#!/usr/bin/env node

const assert = require('assert');
const path = require('path');
const { spawnSync } = require('child_process');

const {
  MINIMUM_PYTHON_VERSION,
  parsePythonVersion,
  isSupportedPythonVersion,
  getUnsupportedPythonMessage,
} = require('../bin/python-version');

function main() {
  assert.deepStrictEqual(parsePythonVersion('Python 3.9.18'), { major: 3, minor: 9, patch: 18 });
  assert.deepStrictEqual(parsePythonVersion('Python 3.10.14'), { major: 3, minor: 10, patch: 14 });
  assert.deepStrictEqual(parsePythonVersion('Python 3.12.3'), { major: 3, minor: 12, patch: 3 });
  assert.strictEqual(parsePythonVersion('not-a-version'), null);

  assert.strictEqual(MINIMUM_PYTHON_VERSION, '3.10');
  assert.strictEqual(isSupportedPythonVersion('Python 3.9.18'), false);
  assert.strictEqual(isSupportedPythonVersion('Python 3.10.0'), true);
  assert.strictEqual(isSupportedPythonVersion('Python 3.11.9'), true);
  assert.strictEqual(isSupportedPythonVersion('Python 3.12.3'), true);

  const message = getUnsupportedPythonMessage('Python 3.9.18');
  assert.ok(message.includes('Python 3.10+'));
  assert.ok(message.includes('3.9.18'));

  const statusCommand = spawnSync(
    'node',
    [path.join(__dirname, '..', 'bin', 'openrouter-mcp.js'), 'status'],
    {
      cwd: path.join(__dirname, '..'),
      encoding: 'utf8',
    }
  );
  assert.strictEqual(statusCommand.status, 0, statusCommand.stderr || statusCommand.stdout);

  console.log('python-version checks passed');
}

main();
