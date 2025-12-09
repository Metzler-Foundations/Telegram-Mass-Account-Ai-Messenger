#!/usr/bin/env python3
"""
Pre-Flight Check - Complete system validation without API calls.

This script performs all validations that can be done without API keys:
- Dependency check
- Import verification
- Database validation
- Configuration file check
- File permissions
- Disk space
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_section(text):
    """Print section header."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")


def print_status(item, status, details=""):
    """Print a status line."""
    symbol = "✅" if status else "❌"
    print(f"{symbol} {item}")
    if details:
        print(f"   {details}")


def check_python_version():
    """Check Python version."""
    print_section("Python Version Check")

    version = sys.version_info
    required = (3, 9)

    current = f"{version.major}.{version.minor}.{version.micro}"
    required_str = f"{required[0]}.{required[1]}+"

    is_ok = (version.major, version.minor) >= required

    print_status(f"Python {current}", is_ok, f"Required: {required_str}")

    return is_ok


def check_dependencies():
    """Check critical dependencies."""
    print_section("Dependency Check")

    deps = {
        "pyrogram": "Telegram client",
        "google.generativeai": "Gemini AI",
        "PyQt6": "Desktop UI",
        "cryptography": "Encryption",
        "aiohttp": "Async HTTP",
        "openpyxl": "Excel export",
        "networkx": "Graph analysis",
    }

    all_ok = True
    for module, desc in deps.items():
        try:
            __import__(module)
            print_status(f"{module}", True, desc)
        except ImportError:
            print_status(f"{module}", False, f"MISSING - {desc}")
            all_ok = False

    return all_ok


def check_core_imports():
    """Check core module imports."""
    print_section("Core Module Import Check")

    modules = [
        "core.config_manager",
        "core.secrets_manager",
        "database.connection_pool",
        "accounts.account_manager",
        "campaigns.dm_campaign_manager",
        "scraping.member_scraper",
        "ai.gemini_service",
    ]

    all_ok = True
    for module in modules:
        try:
            __import__(module)
            print_status(module, True)
        except Exception as e:
            print_status(module, False, str(e)[:60])
            all_ok = False

    return all_ok


def check_databases():
    """Check database files exist."""
    print_section("Database Files Check")

    project_root = Path(__file__).parent.parent

    databases = [
        "accounts.db",
        "members.db",
        "campaigns.db",
        "proxy_pool.db",
        "anti_detection.db",
    ]

    all_ok = True
    for db in databases:
        db_path = project_root / db
        exists = db_path.exists()

        if exists:
            size = db_path.stat().st_size
            print_status(db, True, f"{size:,} bytes")
        else:
            print_status(db, False, "Not found")
            all_ok = False

    return all_ok


def check_config_file():
    """Check configuration file."""
    print_section("Configuration File Check")

    project_root = Path(__file__).parent.parent
    config_path = project_root / "config.json"

    if not config_path.exists():
        print_status("config.json", False, "Not found")
        return False

    try:
        import json

        with open(config_path) as f:
            config = json.load(f)

        print_status("config.json", True, "Valid JSON")

        # Check sections
        sections = ["telegram", "gemini", "sms_providers", "brain"]
        for section in sections:
            has_section = section in config
            print_status(f"  [{section}]", has_section)

        return True

    except Exception as e:
        print_status("config.json", False, str(e))
        return False


def check_disk_space():
    """Check available disk space."""
    print_section("Disk Space Check")

    try:
        import shutil

        total, used, free = shutil.disk_usage("/")

        free_gb = free // (2**30)
        total_gb = total // (2**30)
        percent_free = (free / total) * 100

        # Warn if less than 1GB free
        is_ok = free_gb >= 1

        print_status(f"Free space: {free_gb}GB / {total_gb}GB", is_ok, f"{percent_free:.1f}% free")

        if not is_ok:
            print("   ⚠️  Low disk space may cause issues")

        return is_ok

    except Exception as e:
        print_status("Disk space check", False, str(e))
        return True  # Don't fail on this


def check_file_permissions():
    """Check file permissions."""
    print_section("File Permissions Check")

    project_root = Path(__file__).parent.parent

    files_to_check = [
        "config.json",
        "main.py",
        "accounts.db",
    ]

    all_ok = True
    for filename in files_to_check:
        filepath = project_root / filename

        if not filepath.exists():
            continue

        try:
            # Check if readable
            is_readable = os.access(filepath, os.R_OK)
            # Check if writable (for databases)
            is_writable = os.access(filepath, os.W_OK)

            status = is_readable and (is_writable if filename.endswith(".db") else True)

            permissions = []
            if is_readable:
                permissions.append("R")
            if is_writable:
                permissions.append("W")

            print_status(filename, status, f"{''.join(permissions)}")

            if not status:
                all_ok = False

        except Exception as e:
            print_status(filename, False, str(e))
            all_ok = False

    return all_ok


def check_virtual_env():
    """Check if running in virtual environment."""
    print_section("Virtual Environment Check")

    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )

    print_status("Virtual environment active", in_venv)

    if not in_venv:
        print("   ⚠️  Recommended: Use virtual environment")
        print("   python3 -m venv venv && source venv/bin/activate")

    return True  # Not critical


def main():
    """Run all pre-flight checks."""
    print("\n" + "=" * 70)
    print("  MVP Pre-Flight Check")
    print("  System Validation Without API Keys")
    print("=" * 70)

    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Core Imports", check_core_imports),
        ("Databases", check_databases),
        ("Configuration", check_config_file),
        ("Disk Space", check_disk_space),
        ("File Permissions", check_file_permissions),
        ("Virtual Environment", check_virtual_env),
    ]

    results = {}
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"\n❌ {check_name} check failed with exception: {e}")
            results[check_name] = False

    # Summary
    print_section("Pre-Flight Check Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for check_name, result in results.items():
        symbol = "✅" if result else "❌"
        print(f"{symbol} {check_name}")

    print(f"\nPassed: {passed}/{total}")

    # Overall status
    print("\n" + "=" * 70)

    critical_checks = [
        "Python Version",
        "Dependencies",
        "Core Imports",
        "Databases",
        "Configuration",
    ]

    critical_passed = all(results.get(check, False) for check in critical_checks)

    if critical_passed:
        print("✅ SYSTEM READY FOR MVP TESTING")
        print("\nNext steps:")
        print("  1. Set API keys: export SECRET_TELEGRAM_API_ID=...")
        print("  2. Validate: ./venv/bin/python3 scripts/validate_setup.py")
        print("  3. Launch: ./venv/bin/python3 main.py")
        return 0
    else:
        print("❌ SYSTEM NOT READY")
        print("\nFix the failed checks above before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
