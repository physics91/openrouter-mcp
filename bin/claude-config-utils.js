const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);

function buildClaudeCodeServerConfig(packageName) {
  return {
    command: 'npx',
    args: [packageName, 'start']
  };
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
  buildClaudeCodeServerConfig,
  configContainsPlaintextOpenRouterKey,
};
