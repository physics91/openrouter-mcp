#!/usr/bin/env python3
"""
Comprehensive test runner for Collective Intelligence system.

This script provides various test execution modes and reporting capabilities.
"""

import os
import sys
import argparse
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any


class TestRunner:
    """Main test runner class."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_dir = self.project_root / "tests" / "test_collective_intelligence"
        
    def run_unit_tests(self, verbose: bool = True) -> int:
        """Run unit tests only."""
        cmd = [
            "pytest",
            str(self.test_dir),
            "-m", "unit",
            "--cov=src/openrouter_mcp/collective_intelligence",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov/unit",
            "--cov-report=xml:coverage-unit.xml",
        ]
        
        if verbose:
            cmd.append("-v")
            
        return subprocess.call(cmd)
    
    def run_integration_tests(self, verbose: bool = True) -> int:
        """Run integration tests only."""
        cmd = [
            "pytest", 
            str(self.test_dir),
            "-m", "integration",
            "--cov=src/openrouter_mcp/collective_intelligence",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov/integration", 
            "--cov-report=xml:coverage-integration.xml",
        ]
        
        if verbose:
            cmd.append("-v")
            
        return subprocess.call(cmd)
    
    def run_performance_tests(self, verbose: bool = True) -> int:
        """Run performance and benchmark tests."""
        cmd = [
            "pytest",
            str(self.test_dir),
            "-m", "performance",
            "--benchmark-json=benchmark-results.json",
            "--maxfail=5",  # Allow some performance test failures
        ]
        
        if verbose:
            cmd.append("-v")
            
        return subprocess.call(cmd)
    
    def run_all_tests(self, verbose: bool = True, parallel: bool = False) -> int:
        """Run all tests with comprehensive coverage."""
        cmd = [
            "pytest",
            str(self.test_dir),
            "--cov=src/openrouter_mcp/collective_intelligence",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov/all",
            "--cov-report=xml:coverage-all.xml",
            "--html=test-report.html",
            "--self-contained-html",
            "--junitxml=test-results.xml"
        ]
        
        if verbose:
            cmd.append("-v")
            
        if parallel:
            cmd.extend(["-n", "auto"])
            
        return subprocess.call(cmd)
    
    def run_specific_test(self, test_path: str, verbose: bool = True) -> int:
        """Run a specific test file or test function."""
        cmd = [
            "pytest",
            test_path,
            "--cov=src/openrouter_mcp/collective_intelligence",
            "--cov-report=term-missing"
        ]
        
        if verbose:
            cmd.append("-v")
            
        return subprocess.call(cmd)
    
    def run_smoke_tests(self) -> int:
        """Run quick smoke tests to verify basic functionality."""
        # Run a subset of fast tests
        cmd = [
            "pytest",
            str(self.test_dir),
            "-m", "unit and not slow",
            "--maxfail=5",
            "-x",  # Stop on first failure
            "-q"   # Quiet output
        ]
        
        return subprocess.call(cmd)
    
    def check_test_coverage(self, threshold: float = 90.0) -> int:
        """Check if test coverage meets the threshold."""
        cmd = [
            "pytest",
            str(self.test_dir),
            "--cov=src/openrouter_mcp/collective_intelligence",
            f"--cov-fail-under={threshold}",
            "--cov-report=term-missing",
            "-q"
        ]
        
        return subprocess.call(cmd)
    
    def run_linting(self) -> Dict[str, int]:
        """Run all linting tools."""
        results = {}
        
        # Black
        print("Running black...")
        results['black'] = subprocess.call([
            "black", "--check", "--diff", "src/", "tests/"
        ])
        
        # isort
        print("Running isort...")
        results['isort'] = subprocess.call([
            "isort", "--check-only", "--diff", "src/", "tests/"
        ])
        
        # flake8
        print("Running flake8...")
        results['flake8'] = subprocess.call([
            "flake8", "src/", "tests/"
        ])
        
        # pylint
        print("Running pylint...")
        results['pylint'] = subprocess.call([
            "pylint", "src/"
        ])
        
        # mypy
        print("Running mypy...")
        results['mypy'] = subprocess.call([
            "mypy", "src/"
        ])
        
        return results
    
    def run_security_checks(self) -> Dict[str, int]:
        """Run security scanning tools."""
        results = {}
        
        # Bandit
        print("Running bandit security scan...")
        results['bandit'] = subprocess.call([
            "bandit", "-r", "src/", "-f", "json", "-o", "bandit-report.json"
        ])
        
        # Safety
        print("Running safety check...")
        results['safety'] = subprocess.call([
            "safety", "check", "--json", "--output", "safety-report.json"
        ])
        
        return results
    
    def generate_test_report(self) -> None:
        """Generate a comprehensive test report."""
        print("Generating comprehensive test report...")
        
        # Run all tests with detailed reporting
        subprocess.call([
            "pytest",
            str(self.test_dir),
            "--cov=src/openrouter_mcp/collective_intelligence",
            "--cov-report=html:htmlcov/comprehensive",
            "--cov-report=xml:coverage-comprehensive.xml",
            "--html=comprehensive-test-report.html",
            "--self-contained-html",
            "--junitxml=comprehensive-test-results.xml",
            "-v"
        ])
        
        print("Test report generated:")
        print("- HTML Coverage: htmlcov/comprehensive/index.html")
        print("- Test Report: comprehensive-test-report.html")
        print("- XML Results: comprehensive-test-results.xml")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Collective Intelligence Test Runner")
    parser.add_argument(
        "mode",
        choices=[
            "unit", "integration", "performance", "all", "smoke", 
            "coverage", "lint", "security", "report", "specific"
        ],
        help="Test mode to run"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--parallel", "-p", action="store_true", help="Run tests in parallel")
    parser.add_argument("--test-path", help="Specific test path (for 'specific' mode)")
    parser.add_argument("--threshold", type=float, default=90.0, help="Coverage threshold")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    start_time = time.time()
    
    try:
        if args.mode == "unit":
            exit_code = runner.run_unit_tests(args.verbose)
        elif args.mode == "integration":
            exit_code = runner.run_integration_tests(args.verbose)
        elif args.mode == "performance":
            exit_code = runner.run_performance_tests(args.verbose)
        elif args.mode == "all":
            exit_code = runner.run_all_tests(args.verbose, args.parallel)
        elif args.mode == "smoke":
            exit_code = runner.run_smoke_tests()
        elif args.mode == "coverage":
            exit_code = runner.check_test_coverage(args.threshold)
        elif args.mode == "lint":
            results = runner.run_linting()
            exit_code = max(results.values()) if results else 0
            print("\nLinting Results:")
            for tool, code in results.items():
                status = "PASS" if code == 0 else "FAIL"
                print(f"  {tool}: {status}")
        elif args.mode == "security":
            results = runner.run_security_checks()
            exit_code = max(results.values()) if results else 0
            print("\nSecurity Check Results:")
            for tool, code in results.items():
                status = "PASS" if code == 0 else "FAIL"
                print(f"  {tool}: {status}")
        elif args.mode == "report":
            runner.generate_test_report()
            exit_code = 0
        elif args.mode == "specific":
            if not args.test_path:
                print("Error: --test-path is required for 'specific' mode")
                exit_code = 1
            else:
                exit_code = runner.run_specific_test(args.test_path, args.verbose)
        else:
            print(f"Unknown mode: {args.mode}")
            exit_code = 1
            
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        exit_code = 130
    except Exception as e:
        print(f"Error running tests: {e}")
        exit_code = 1
    
    elapsed_time = time.time() - start_time
    print(f"\nTest execution completed in {elapsed_time:.2f} seconds")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()