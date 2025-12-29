#!/usr/bin/env node

/**
 * Test Script for Secure Credential Storage Integration
 *
 * This script demonstrates and tests the secure credential retrieval
 * functionality that has been integrated into the server startup process.
 */

const chalk = require('chalk');
const secureCredentials = require('./bin/secure-credentials');

console.log(chalk.cyan('═══════════════════════════════════════════════════════════'));
console.log(chalk.cyan('  Secure Credential Storage Integration Test'));
console.log(chalk.cyan('═══════════════════════════════════════════════════════════\n'));

async function testCredentialRetrieval() {
  console.log(chalk.bold('Test 1: Retrieve API Key from All Sources\n'));

  try {
    const keyResult = await secureCredentials.getApiKey();

    if (keyResult.key) {
      const maskedKey = secureCredentials.maskApiKey(keyResult.key);
      console.log(chalk.green(`✓ API key found!`));
      console.log(chalk.gray(`  Source: ${keyResult.source}`));
      console.log(chalk.gray(`  Masked key: ${maskedKey}`));
    } else {
      console.log(chalk.yellow('⚠️  No API key found in any storage location'));
      console.log(chalk.blue('💡 Run "openrouter-mcp init" to configure'));
    }

    console.log('\n' + chalk.cyan('─────────────────────────────────────────────────────────────'));
    console.log(chalk.bold('\nTest 2: Check Individual Storage Locations\n'));

    // Check environment variable
    const envKey = process.env.OPENROUTER_API_KEY;
    if (envKey) {
      console.log(chalk.green('✓ Environment Variable:'), chalk.gray(secureCredentials.maskApiKey(envKey)));
    } else {
      console.log(chalk.gray('○ Environment Variable: Not set'));
    }

    // Check OS Keychain
    if (secureCredentials.keytarAvailable) {
      const keychainKey = await secureCredentials.getFromKeychain();
      if (keychainKey) {
        console.log(chalk.green('✓ OS Keychain:'), chalk.gray(secureCredentials.maskApiKey(keychainKey)));
      } else {
        console.log(chalk.gray('○ OS Keychain: Not configured'));
      }
    } else {
      console.log(chalk.yellow('⚠ OS Keychain: Not available (install keytar)'));
    }

    // Check encrypted file
    const encryptedKey = await secureCredentials.getFromEncryptedFile();
    if (encryptedKey) {
      console.log(chalk.green('✓ Encrypted File:'), chalk.gray(secureCredentials.maskApiKey(encryptedKey)));
    } else {
      console.log(chalk.gray('○ Encrypted File: Not configured'));
    }

    // Check .env file
    const envFileKey = secureCredentials.getFromEnvironment();
    if (envFileKey && !envKey) { // Only show if not from environment variable
      console.log(chalk.green('✓ .env File:'), chalk.gray(secureCredentials.maskApiKey(envFileKey)));
    } else if (!envKey) {
      console.log(chalk.gray('○ .env File: Not configured'));
    }

    console.log('\n' + chalk.cyan('─────────────────────────────────────────────────────────────'));
    console.log(chalk.bold('\nTest 3: Storage Priority Order\n'));

    console.log(chalk.gray('The getApiKey() function checks sources in this order:'));
    console.log(chalk.gray('  1. Environment variable (OPENROUTER_API_KEY)'));
    console.log(chalk.gray('  2. OS Keychain (most secure)'));
    console.log(chalk.gray('  3. Encrypted file storage'));
    console.log(chalk.gray('  4. .env file'));
    console.log('');

    if (keyResult.key) {
      console.log(chalk.green(`Your key was retrieved from: ${chalk.bold(keyResult.source)}`));
    }

    console.log('\n' + chalk.cyan('─────────────────────────────────────────────────────────────'));
    console.log(chalk.bold('\nTest 4: Server Startup Simulation\n'));

    // Simulate server startup logic
    const env = { ...process.env };

    if (!env.OPENROUTER_API_KEY) {
      console.log(chalk.blue('🔑 Retrieving API key from secure storage...'));

      const startupKeyResult = await secureCredentials.getApiKey();

      if (startupKeyResult.key) {
        env.OPENROUTER_API_KEY = startupKeyResult.key;
        const maskedKey = secureCredentials.maskApiKey(startupKeyResult.key);
        console.log(chalk.green(`✓ API key loaded from ${startupKeyResult.source}`));
        console.log(chalk.gray(`  Masked key: ${maskedKey}`));
        console.log(chalk.green('✓ Ready to start server!'));
      } else {
        console.log(chalk.yellow('⚠️  No API key found in secure storage'));
        console.log(chalk.blue('💡 To configure API key, run: openrouter-mcp init'));
        console.log(chalk.gray('   Server would start but API calls will fail without a valid key'));
      }
    } else {
      console.log(chalk.green('✓ Using API key from environment variable'));
      const maskedKey = secureCredentials.maskApiKey(env.OPENROUTER_API_KEY);
      console.log(chalk.gray(`  Masked key: ${maskedKey}`));
      console.log(chalk.green('✓ Ready to start server!'));
    }

    console.log('\n' + chalk.cyan('═══════════════════════════════════════════════════════════'));
    console.log(chalk.green('\n✅ All tests completed successfully!\n'));

    if (!keyResult.key) {
      console.log(chalk.bold('Next Steps:'));
      console.log(chalk.gray('  1. Run: openrouter-mcp init'));
      console.log(chalk.gray('  2. Configure your API key with preferred storage method'));
      console.log(chalk.gray('  3. Run this test again to verify integration'));
      console.log('');
    }

  } catch (error) {
    console.log(chalk.red(`\n✗ Test failed: ${error.message}`));
    console.log(chalk.gray(error.stack));
  }
}

// Run tests
testCredentialRetrieval().catch(error => {
  console.error(chalk.red('Fatal error:'), error);
  process.exit(1);
});
