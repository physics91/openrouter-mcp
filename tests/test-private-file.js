#!/usr/bin/env node

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { writePrivateFile } = require('../bin/secure-file');
const { storeInEnvFile, setSecurePermissions } = require('../bin/secure-credentials');

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'openrouter-private-file-'));
try {
  const destination = path.join(root, '.env');
  const outside = path.join(root, 'outside');
  fs.writeFileSync(outside, 'must remain unchanged');
  if (process.platform !== 'win32') {
    fs.symlinkSync(outside, destination);
    assert.throws(() => storeInEnvFile('audit-placeholder-for-file-security', '', '', destination), /regular file/);
    assert.strictEqual(fs.readFileSync(outside, 'utf8'), 'must remain unchanged');
    fs.unlinkSync(destination);

    fs.linkSync(outside, destination);
    storeInEnvFile('audit-placeholder-for-file-security', '', '', destination);
    assert.strictEqual(fs.readFileSync(outside, 'utf8'), 'must remain unchanged');
    assert.strictEqual(fs.statSync(destination).mode & 0o777, 0o600);
    fs.chmodSync(destination, 0o644);
  }
  writePrivateFile(destination, 'replacement');
  assert.strictEqual(fs.readFileSync(destination, 'utf8'), 'replacement');
  if (process.platform !== 'win32') {
    assert.strictEqual(fs.statSync(destination).mode & 0o777, 0o600);
    setSecurePermissions(root);
    assert.strictEqual(fs.statSync(root).mode & 0o777, 0o700);
    assert.strictEqual(fs.readFileSync(destination, 'utf8'), 'replacement');
  }
  assert.strictEqual(fs.readdirSync(root).some(name => name.startsWith('.openrouter-')), false);
} finally {
  fs.rmSync(root, { recursive: true, force: true });
}
console.log('Private credential file security tests passed.');
