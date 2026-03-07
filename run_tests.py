#!/usr/bin/env python3
"""
Test Runner Script for OpenRouter MCP Server

Provides convenient commands to run different test suites.
"""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:  # Optional for environments without python-dotenv.
    load_dotenv = None


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
  %(prog)s assurance         # Run PR assurance gate (unit/contract/replay + Node security)
  %(prog)s all               # Run all tests except real API tests
  %(prog)s real              # Run real API tests (requires API key)
  %(prog)s coverage          # Run tests with coverage report
  %(prog)s quick             # Quick smoke test
        """
    )

    parser.add_argument(
        'suite',
        choices=['unit', 'integration', 'assurance', 'all', 'real', 'coverage', 'quick', 'regression'],
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

    # Load .env once so real API tests can pick up OPENROUTER_API_KEY.
    if load_dotenv is not None:
        load_dotenv()

    # Base pytest command (use current Python interpreter for portability)
    base_cmd = [sys.executable, '-m', 'pytest']
    extra_cmds: list[list[str]] = []

    if args.verbose:
        base_cmd.append('-vv')

    enable_cov = not args.no_cov
    pytest_cov_installed = importlib.util.find_spec('pytest_cov') is not None

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

    elif args.suite == 'assurance':
        print("Running ASSURANCE tests (PR gate: unit/contract/property/replay + Node security)")
        if enable_cov and not pytest_cov_installed:
            print("\nASSURANCE_COVERAGE_REQUIRED: pytest-cov is required for assurance suite.")
            print("Install development dependencies before running assurance:")
            print(f"  {sys.executable} -m pip install -r requirements-dev.txt\n")
            return 1
        cmd = base_cmd + [
            '--ignore=tests/test_real_world_integration.py',
            '-m', 'unit or contract or property or replay',
            'tests/'
        ]
        if enable_cov:
            cmd.extend([
                '--cov=src/openrouter_mcp',
                '--cov-branch',
                '--cov-report=term-missing',
                '--cov-fail-under=70'
            ])
        if shutil.which('npm') is None:
            print("\nERROR: npm executable not found. Assurance suite requires Node security tests.")
            return 1
        if not (Path.cwd() / 'node_modules').exists():
            print("\nNode dependencies not found. Installing npm packages for assurance suite.")
            extra_cmds.append(['npm', 'install', '--no-audit', '--no-fund'])
        extra_cmds.append(['npm', 'run', 'test:security'])

    elif args.suite == 'real':
        print("Running REAL API tests (requires API key, will consume credits)")

        # Check for API key
        if not os.getenv('OPENROUTER_API_KEY'):
            print("\n⚠️  ERROR: OPENROUTER_API_KEY environment variable not set")
            print("Set it before running real API tests:")
            print("  export OPENROUTER_API_KEY=sk-or-...")
            print(f"  {sys.executable} run_tests.py real\n")
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
        if enable_cov and not pytest_cov_installed:
            print("\nCOVERAGE_DEPENDENCY_MISSING: pytest-cov is required for coverage suite.")
            print("Install development dependencies before running coverage:")
            print(f"  {sys.executable} -m pip install -r requirements-dev.txt\n")
            return 1
        cmd = base_cmd + ['--ignore=tests/test_real_world_integration.py']
        if enable_cov:
            cmd.extend([
                '--cov=src/openrouter_mcp',
                '--cov-report=html',
                '--cov-report=term-missing',
            ])
        cmd.append('tests/')

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

    # Run the command(s)
    exit_code = run_command(cmd)
    if exit_code == 0:
        for extra_cmd in extra_cmds:
            exit_code = run_command(extra_cmd)
            if exit_code != 0:
                break

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
