#!/usr/bin/env node

const MINIMUM_PYTHON_VERSION = '3.10';
const MINIMUM_PYTHON_MAJOR = 3;
const MINIMUM_PYTHON_MINOR = 10;

function parsePythonVersion(versionOutput) {
  if (!versionOutput) {
    return null;
  }

  const match = String(versionOutput).match(/Python\s+(\d+)\.(\d+)\.(\d+)/i);
  if (!match) {
    return null;
  }

  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
  };
}

function isSupportedPythonVersion(versionOutput) {
  const parsed = parsePythonVersion(versionOutput);
  if (!parsed) {
    return false;
  }

  if (parsed.major !== MINIMUM_PYTHON_MAJOR) {
    return parsed.major > MINIMUM_PYTHON_MAJOR;
  }

  return parsed.minor >= MINIMUM_PYTHON_MINOR;
}

function getUnsupportedPythonMessage(versionOutput) {
  const detected = versionOutput || 'unknown version';
  return `FastMCP requires Python ${MINIMUM_PYTHON_VERSION}+ (detected: ${detected}).`;
}

function getMissingPythonMessage() {
  return `Please install Python ${MINIMUM_PYTHON_VERSION}+ and ensure "python" or "python3" is in your PATH.`;
}

async function resolveSupportedPythonCommand(runCommand, candidates = ['python', 'python3']) {
  let unsupportedVersion = null;

  for (const command of candidates) {
    try {
      const version = await runCommand(command, ['--version']);

      if (isSupportedPythonVersion(version)) {
        return {
          status: 'supported',
          command,
          version: version || 'Unknown version',
        };
      }

      unsupportedVersion = version || 'Unknown version';
    } catch {
      // Try next candidate
    }
  }

  if (unsupportedVersion) {
    return {
      status: 'unsupported',
      version: unsupportedVersion,
      message: getUnsupportedPythonMessage(unsupportedVersion),
    };
  }

  return {
    status: 'missing',
    message: getMissingPythonMessage(),
  };
}

module.exports = {
  MINIMUM_PYTHON_VERSION,
  getMissingPythonMessage,
  getUnsupportedPythonMessage,
  isSupportedPythonVersion,
  parsePythonVersion,
  resolveSupportedPythonCommand,
};
