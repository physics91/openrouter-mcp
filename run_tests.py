#!/usr/bin/env python3
"""
Test Runner Script for OpenRouter MCP Server

Provides convenient commands to run different test suites.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], env: dict = None) -> int:
    """Run a command and return the exit code."""
    print(f"\n{'=' * 70}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'=' * 70}\n")

    result = subprocess.run(cmd, env=env or os.environ.copy())
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Test runner for OpenRouter MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s unit              # Run only unit tests (fast)
  %(prog)s integration       # Run integration tests (mocked APIs)
  %(prog)s all               # Run all tests except real API tests
  %(prog)s real              # Run real API tests (requires API key)
  %(prog)s coverage          # Run tests with coverage report
  %(prog)s quick             # Quick smoke test
        """
    )

    parser.add_argument(
        'suite',
        choices=['unit', 'integration', 'all', 'real', 'coverage', 'quick', 'regression'],
        help='Test suite to run'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.add_argument(
        '--no-cov',
        action='store_true',
        help='Disable coverage reporting'
    )

    args = parser.parse_args()

    # Base pytest command
    base_cmd = ['pytest']

    if args.verbose:
        base_cmd.append('-vv')

    if args.no_cov:
        base_cmd.extend(['--no-cov'])

    # Suite-specific commands
    if args.suite == 'unit':
        print("Running UNIT tests (fast, isolated)")
        cmd = base_cmd + [
            '-m', 'unit',
            'tests/'
        ]

    elif args.suite == 'integration':
        print("Running INTEGRATION tests (mocked APIs)")
        cmd = base_cmd + [
            'tests/test_mcp_integration.py',
            'tests/test_collective_intelligence_mocked.py',
            'tests/test_mcp_server_fixed.py',
            '-v'
        ]

    elif args.suite == 'all':
        print("Running ALL tests (except real API tests)")
        cmd = base_cmd + [
            '--ignore=tests/test_real_world_integration.py',
            'tests/'
        ]

    elif args.suite == 'real':
        print("Running REAL API tests (requires API key, will consume credits)")

        # Check for API key
        if not os.getenv('OPENROUTER_API_KEY'):
            print("\n⚠️  ERROR: OPENROUTER_API_KEY environment variable not set")
            print("Set it before running real API tests:")
            print("  export OPENROUTER_API_KEY=sk-or-...")
            print("  python run_tests.py real\n")
            return 1

        response = input("\n⚠️  This will make REAL API calls and consume credits. Continue? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return 0

        cmd = base_cmd + [
            'tests/test_real_world_integration.py',
            '-v', '-s'
        ]

    elif args.suite == 'coverage':
        print("Running tests with detailed coverage report")
        cmd = base_cmd + [
            '--ignore=tests/test_real_world_integration.py',
            '--cov=src/openrouter_mcp',
            '--cov-report=html',
            '--cov-report=term-missing',
            'tests/'
        ]

    elif args.suite == 'quick':
        print("Running QUICK smoke test (critical tests only)")
        cmd = base_cmd + [
            'tests/test_mcp_integration.py::TestMCPServerToolRegistration::test_tool_count_regression',
            'tests/test_mcp_server_fixed.py::TestMCPServerBasicFunctionality::test_no_zero_tools_regression',
            '-v'
        ]

    elif args.suite == 'regression':
        print("Running REGRESSION tests (critical bug prevention)")
        cmd = base_cmd + [
            '-k', 'regression',
            'tests/',
            '-v'
        ]

    else:
        print(f"Unknown suite: {args.suite}")
        return 1

    # Run the command
    exit_code = run_command(cmd)

    # Print summary
    print(f"\n{'=' * 70}")
    if exit_code == 0:
        print("✓ TESTS PASSED")
    else:
        print("✗ TESTS FAILED")
    print(f"{'=' * 70}\n")

    # If coverage was run, show the report
    if args.suite == 'coverage' and exit_code == 0:
        print("\n📊 Coverage report generated:")
        print(f"   HTML: file://{Path.cwd() / 'htmlcov' / 'index.html'}")
        print()

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
