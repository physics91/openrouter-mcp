const fs = require('fs');
const path = require('path');

function writePrivateFile(filePath, content) {
  const destination = path.resolve(filePath);
  try {
    if (!fs.lstatSync(destination).isFile()) {
      throw new Error('Credential destination must be a regular file, not a link');
    }
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }

  // An exclusive directory and file protect new content before publication.
  // Renaming also avoids modifying another file through an existing hardlink.
  const temporaryDir = fs.mkdtempSync(path.join(path.dirname(destination), '.openrouter-'));
  const temporaryFile = path.join(temporaryDir, 'credentials');
  try {
    fs.writeFileSync(temporaryFile, content, { mode: 0o600, flag: 'wx' });
    fs.renameSync(temporaryFile, destination);
  } finally {
    fs.rmSync(temporaryDir, { recursive: true, force: true });
  }
}

module.exports = { writePrivateFile };
