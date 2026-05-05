#!/usr/bin/env node

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const repoRoot = path.resolve(__dirname, '..');
const cliPath = path.join(repoRoot, 'bin', 'openrouter-mcp.js');
const tempHome = fs.mkdtempSync(path.join(os.tmpdir(), 'openrouter-mcp-audit-'));
fs.chmodSync(tempHome, 0o755);

const result = spawnSync(process.execPath, [cliPath, 'security-audit'], {
  cwd: repoRoot,
  encoding: 'utf8',
  env: {
    ...process.env,
    HOME: tempHome,
    USERPROFILE: tempHome
  }
});
fs.rmSync(tempHome, { recursive: true, force: true });

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

const environmentJudgments = combinedOutput.match(
  /Shared Environment: Detected|Environment: Single-user/g
) || [];
assert.strictEqual(
  environmentJudgments.length,
  1,
  `security-audit should emit exactly one environment judgment\n${combinedOutput}`
);
assert.ok(
  !combinedOutput.includes('✓ Single-user environment detected'),
  `forced shared environment should not be summarized as a good practice\n${combinedOutput}`
);

const mockDir = fs.mkdtempSync(path.join(os.tmpdir(), 'openrouter-mcp-keytar-mock-'));
const mockHome = fs.mkdtempSync(path.join(os.tmpdir(), 'openrouter-mcp-audit-'));
const keytarMockPath = path.join(mockDir, 'mock-keytar-failure.js');
fs.writeFileSync(
  keytarMockPath,
  `
const Module = require('module');
const originalLoad = Module._load;

Module._load = function mockedKeytarLoad(request, parent, isMain) {
  if (request === 'keytar') {
    return {
      getPassword: async () => {
        throw new Error('mock keychain failure');
      },
      setPassword: async () => true,
      deletePassword: async () => false
    };
  }
  return originalLoad.apply(this, arguments);
};
`
);

const mockedResult = spawnSync(process.execPath, [cliPath, 'security-audit'], {
  cwd: repoRoot,
  encoding: 'utf8',
  env: {
    ...process.env,
    HOME: mockHome,
    USERPROFILE: mockHome,
    NODE_OPTIONS: `${process.env.NODE_OPTIONS || ''} --require ${keytarMockPath}`.trim()
  }
});
fs.rmSync(mockDir, { recursive: true, force: true });
fs.rmSync(mockHome, { recursive: true, force: true });

const mockedOutput = `${mockedResult.stdout}\n${mockedResult.stderr}`;
assert.strictEqual(
  mockedResult.status,
  0,
  `security-audit should exit cleanly with mocked keytar failure\n${mockedOutput}`
);
const keychainFailureWarnings = mockedOutput.match(/Failed to retrieve from keychain/g) || [];
assert.strictEqual(
  keychainFailureWarnings.length,
  1,
  `security-audit should report a keychain retrieval failure once\n${mockedOutput}`
);

console.log('security-audit CLI regression test passed');
