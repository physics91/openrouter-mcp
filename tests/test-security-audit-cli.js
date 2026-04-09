#!/usr/bin/env node

const assert = require('assert');
const path = require('path');
const { spawnSync } = require('child_process');

const repoRoot = path.resolve(__dirname, '..');
const cliPath = path.join(repoRoot, 'bin', 'openrouter-mcp.js');

const result = spawnSync(process.execPath, [cliPath, 'security-audit'], {
  cwd: repoRoot,
  encoding: 'utf8',
});

const combinedOutput = `${result.stdout}\n${result.stderr}`;

assert.strictEqual(
  result.status,
  0,
  `security-audit should exit cleanly\n${combinedOutput}`
);

assert.ok(
  !combinedOutput.includes('TypeError: apiKey.substring is not a function'),
  `security-audit should never pass a Promise to maskApiKey\n${combinedOutput}`
);

console.log('security-audit CLI regression test passed');
