const { parseEnv } = require('node:util');

function readEnvApiKey(content) {
  const value = parseEnv(content).OPENROUTER_API_KEY;
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function replaceEnvApiKey(content, replacement = null) {
  // Consume complete quoted assignments so a key-like line inside another
  // variable's multiline value is never treated as a credential assignment.
  const assignments = /(^|\n)[\t \uFEFF]*(?:export[\t ]+)?([A-Za-z_][A-Za-z0-9_]*)[\t ]*=[\t ]*(?:'[^']*'|"[^"]*"|`[^`]*`|[^\r\n]*)[^\r\n]*/g;
  if (replacement !== null && !/^[A-Za-z0-9_-]+$/.test(replacement)) {
    throw new Error('API key contains invalid characters');
  }
  let changed = false;
  const updated = content.replace(assignments, (assignment, prefix, name) => {
    if (name !== 'OPENROUTER_API_KEY') {
      return assignment;
    }
    changed = true;
    return replacement === null ? prefix : `${prefix}OPENROUTER_API_KEY=${replacement}`;
  });
  return changed ? updated : null;
}

module.exports = { readEnvApiKey, replaceEnvApiKey };
