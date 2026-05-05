function packageNeedsLatestSpecifier(packageName) {
  if (!packageName || packageName.startsWith('.') || packageName.startsWith('/')) {
    return false;
  }

  if (packageName.startsWith('@')) {
    const slashIndex = packageName.indexOf('/');
    if (slashIndex === -1) {
      return false;
    }
    return !packageName.slice(slashIndex + 1).includes('@');
  }

  return !packageName.includes('@');
}

function withLatestSpecifier(packageName) {
  return packageNeedsLatestSpecifier(packageName) ? `${packageName}@latest` : packageName;
}

function buildNpxStartArgs(packageName) {
  return ['-y', withLatestSpecifier(packageName), 'start'];
}

module.exports = {
  buildNpxStartArgs,
  packageNeedsLatestSpecifier,
  withLatestSpecifier,
};
