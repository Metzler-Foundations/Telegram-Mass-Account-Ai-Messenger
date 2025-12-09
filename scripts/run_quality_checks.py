#!/usr/bin/env python3
"""
Quality Assurance Script - Run all code quality checks locally
"""
import subprocess
import sys
import os
from pathlib import Path
import argparse


def run_command(cmd, description, fail_on_error=True):
    """Run a command and return success status."""
    print(f"\n🔍 {description}")
    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        if result.returncode == 0:
            print(f"✅ {description} passed")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ {description} failed")
            if result.stdout:
                print("STDOUT:", result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            if fail_on_error:
                return False
            return True
    except Exception as e:
        print(f"❌ Error running {description}: {e}")
        if fail_on_error:
            return False
        return True


def main():
    parser = argparse.ArgumentParser(description="Run code quality checks")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues where possible")
    parser.add_argument("--skip-slow", action="store_true", help="Skip slow checks")
    args = parser.parse_args()

    print("🚀 Telegram Bot Quality Assurance Suite")
    print("=" * 50)

    # Check if we're in the right directory
    if not Path("main.py").exists():
        print("❌ Not in bot directory - please run from bot root")
        return 1

    success_count = 0
    total_checks = 0

    # 1. Import tests
    total_checks += 1
    if run_command([sys.executable, "tests/test_app.py"], "Import Tests"):
        success_count += 1

    # 2. Unit tests
    total_checks += 1
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "-m", "not integration"]
    if args.skip_slow:
        cmd.extend(["-m", "not slow"])
    if run_command(cmd, "Unit Tests"):
        success_count += 1

    # 3. Integration tests (skip if --skip-slow)
    if not args.skip_slow:
        total_checks += 1
        if run_command(
            [sys.executable, "-m", "pytest", "tests/", "-k", "integration", "-v", "--tb=short"],
            "Integration Tests",
        ):
            success_count += 1

    # 4. Coverage
    total_checks += 1
    if run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--cov=.",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=70",
        ],
        "Coverage Analysis",
    ):
        success_count += 1

    # 5. Ruff linting (if available)
    total_checks += 1
    try:
        import ruff

        cmd = ["ruff", "check", "."]
        if args.fix:
            cmd.append("--fix")
        if run_command(cmd, "Ruff Linting"):
            success_count += 1
    except ImportError:
        print("ℹ️  Ruff not installed - skipping linting")
        success_count += 1  # Don't fail for optional tools

    # 6. MyPy type checking (if available)
    total_checks += 1
    try:
        import mypy

        if run_command(["mypy", ".", "--ignore-missing-imports"], "MyPy Type Checking"):
            success_count += 1
    except ImportError:
        print("ℹ️  MyPy not installed - skipping type checking")
        success_count += 1  # Don't fail for optional tools

    # 7. Black formatting check (if available)
    total_checks += 1
    try:
        import black

        cmd = ["black", "--check", "--diff", "."]
        if args.fix:
            cmd = ["black", "."]
        if run_command(cmd, "Black Formatting Check"):
            success_count += 1
    except ImportError:
        print("ℹ️  Black not installed - skipping formatting check")
        success_count += 1  # Don't fail for optional tools

    # 8. Security checks (if available)
    total_checks += 1
    try:
        import bandit

        if run_command(
            ["bandit", "-r", ".", "-f", "json", "-o", "bandit-report.json"],
            "Security Analysis (Bandit)",
        ):
            success_count += 1
    except ImportError:
        print("ℹ️  Bandit not installed - skipping security analysis")
        success_count += 1  # Don't fail for optional tools

    # 9. Pre-commit hooks (if available)
    total_checks += 1
    try:
        import pre_commit

        if run_command(["pre-commit", "run", "--all-files"], "Pre-commit Hooks"):
            success_count += 1
    except ImportError:
        print("ℹ️  Pre-commit not installed - skipping pre-commit checks")
        success_count += 1  # Don't fail for optional tools

    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Quality Check Results: {success_count}/{total_checks} passed")

    if success_count == total_checks:
        print("🎉 All quality checks passed!")
        return 0
    else:
        print(f"⚠️  {total_checks - success_count} checks failed")
        print("\n💡 Tips:")
        print("  - Run with --fix to auto-fix formatting issues")
        print("  - Run with --skip-slow to skip integration tests")
        print("  - Check bandit-report.json for security issues")
        print("  - Check htmlcov/index.html for coverage details")
        return 1


if __name__ == "__main__":
    sys.exit(main())
