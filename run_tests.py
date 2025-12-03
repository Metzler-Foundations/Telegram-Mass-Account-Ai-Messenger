#!/usr/bin/env python3
"""
Test runner script for the Telegram Bot application.
"""
import sys
import subprocess
import os
from pathlib import Path


def run_unit_tests():
    """Run unit tests."""
    print("🧪 Running Unit Tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "test_business_logic.py",
        "-v", "--tb=short"
    ], cwd=Path(__file__).parent)

    return result.returncode == 0


def run_integration_tests():
    """Run integration tests."""
    print("🔗 Running Integration Tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "test_integration.py",
        "-v", "--tb=short"
    ], cwd=Path(__file__).parent)

    return result.returncode == 0


def run_all_tests():
    """Run all tests."""
    print("🚀 Running Complete Test Suite...")
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "-v", "--tb=short", "--cov=.",
        "--cov-report=term-missing"
    ], cwd=Path(__file__).parent)

    return result.returncode == 0


def run_coverage_report():
    """Generate coverage report."""
    print("📊 Generating Coverage Report...")
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "--cov=.",
        "--cov-report=html:htmlcov",
        "--cov-report=term-missing"
    ], cwd=Path(__file__).parent)

    if result.returncode == 0:
        print("📄 Coverage report generated in htmlcov/ directory")

    return result.returncode == 0


def main():
    """Main test runner."""
    print("🤖 Telegram Bot Test Suite")
    print("=" * 40)

    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()

        if test_type == "unit":
            success = run_unit_tests()
        elif test_type == "integration":
            success = run_integration_tests()
        elif test_type == "coverage":
            success = run_coverage_report()
        else:
            print(f"Unknown test type: {test_type}")
            print("Usage: python run_tests.py [unit|integration|coverage|all]")
            return 1
    else:
        # Run all tests by default
        success = run_all_tests()

    if success:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
