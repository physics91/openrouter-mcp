function getEnvApiKey(env = process.env) {
  if (!env || typeof env.OPENROUTER_API_KEY !== 'string') {
    return null;
  }

  const apiKey = env.OPENROUTER_API_KEY.trim();
  return apiKey || null;
}

async function resolveApiKeyForStart({ env = process.env, secureCredentials } = {}) {
  const envApiKey = getEnvApiKey(env);
  if (envApiKey) {
    return { apiKey: envApiKey, source: 'environment-variable' };
  }

  const keyResult = secureCredentials ? await secureCredentials.getApiKey() : null;
  const storedApiKey =
    keyResult && typeof keyResult.key === 'string' ? keyResult.key.trim() : null;

  if (storedApiKey) {
    return { apiKey: storedApiKey, source: keyResult.source || 'secure-storage' };
  }

  throw new Error(
    "OpenRouter API key is required to start the MCP server. Run 'openrouter-mcp init' first or set OPENROUTER_API_KEY."
  );
}

module.exports = {
  resolveApiKeyForStart,
};
