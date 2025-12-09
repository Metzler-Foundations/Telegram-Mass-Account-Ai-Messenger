#!/usr/bin/env python3
"""
Setup Validation Script - Verify all requirements are met for MVP.

This script checks:
- API keys configured
- Dependencies installed
- Databases initialized
- Core modules importable
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


def print_check(name, status, details=""):
    """Print a check result."""
    symbol = "✅" if status else "❌"
    print(f"{symbol} {name}")
    if details:
        print(f"   {details}")


def check_dependencies():
    """Check if all required dependencies are installed."""
    print_section("Dependency Check")
    
    deps = {
        'pyrogram': 'Telegram client library',
        'google.generativeai': 'Google Gemini AI',
        'PyQt6': 'Desktop UI framework',
        'cryptography': 'Encryption library',
        'aiohttp': 'Async HTTP client',
        'psutil': 'System utilities',
        'requests': 'HTTP library',
        'openpyxl': 'Excel export support',
    }
    
    optional_deps = {
        'networkx': 'Graph analysis (optional)',
        'elevenlabs': 'Voice messages (optional)',
        'redis': 'Rate limiting (optional)',
    }
    
    all_good = True
    
    for module, description in deps.items():
        try:
            __import__(module)
            print_check(f"{module}", True, description)
        except ImportError:
            print_check(f"{module}", False, f"{description} - MISSING!")
            all_good = False
    
    print("\nOptional dependencies:")
    for module, description in optional_deps.items():
        try:
            __import__(module)
            print_check(f"{module}", True, description)
        except ImportError:
            print_check(f"{module}", False, f"{description} - Not installed")
    
    return all_good


def check_api_keys():
    """Check if API keys are configured."""
    print_section("API Key Configuration")
    
    try:
        from core.secrets_manager import get_secrets_manager
        secrets = get_secrets_manager()
        
        keys = {
            'telegram_api_id': 'Telegram API ID',
            'telegram_api_hash': 'Telegram API Hash',
            'gemini_api_key': 'Google Gemini API Key',
            'sms_provider_api_key': 'SMS Provider API Key (optional)',
        }
        
        all_set = True
        optional_set = True
        
        for key, name in keys.items():
            try:
                value = secrets.get_secret(key)
                is_optional = '(optional)' in name
                
                if value:
                    print_check(name, True, "Configured")
                else:
                    print_check(name, False, "Not set")
                    if not is_optional:
                        all_set = False
                    else:
                        optional_set = False
            except Exception as e:
                print_check(name, False, f"Error: {e}")
                if not is_optional:
                    all_set = False
        
        return all_set, optional_set
        
    except Exception as e:
        print_check("Secrets Manager", False, f"Error: {e}")
        return False, False


def check_core_imports():
    """Check if core modules can be imported."""
    print_section("Core Module Imports")
    
    modules = {
        'core.config_manager': 'Configuration Manager',
        'core.secrets_manager': 'Secrets Manager',
        'database.connection_pool': 'Database Connection Pool',
        'accounts.account_creator': 'Account Creator',
        'accounts.account_manager': 'Account Manager',
        'campaigns.dm_campaign_manager': 'DM Campaign Manager',
        'scraping.member_scraper': 'Member Scraper',
        'proxy.proxy_pool_manager': 'Proxy Pool Manager',
        'ai.gemini_service': 'Gemini AI Service',
        'telegram.telegram_client': 'Telegram Client',
    }
    
    all_good = True
    
    for module, name in modules.items():
        try:
            __import__(module)
            print_check(name, True)
        except Exception as e:
            print_check(name, False, f"Import error: {e}")
            all_good = False
    
    return all_good


def check_databases():
    """Check if databases exist."""
    print_section("Database Files")
    
    project_root = Path(__file__).parent.parent
    
    expected_dbs = [
        'accounts.db',
        'members.db',
        'campaigns.db',
        'proxy_pool.db',
        'anti_detection.db',
    ]
    
    all_exist = True
    
    for db_name in expected_dbs:
        db_path = project_root / db_name
        exists = db_path.exists()
        
        if exists:
            size = db_path.stat().st_size
            print_check(db_name, True, f"Size: {size:,} bytes")
        else:
            print_check(db_name, False, "Not created yet")
            all_exist = False
    
    return all_exist


def check_config_file():
    """Check if config.json exists and is valid."""
    print_section("Configuration File")
    
    project_root = Path(__file__).parent.parent
    config_path = project_root / 'config.json'
    
    if not config_path.exists():
        print_check("config.json", False, "File not found")
        return False
    
    try:
        import json
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        print_check("config.json", True, "Valid JSON")
        
        # Check key sections
        sections = ['telegram', 'gemini', 'sms_providers', 'brain', 'anti_detection']
        for section in sections:
            has_section = section in config
            print_check(f"  [{section}] section", has_section)
        
        return True
        
    except Exception as e:
        print_check("config.json", False, f"Error: {e}")
        return False


def main():
    """Run all validation checks."""
    print("\n" + "="*70)
    print("  MVP Setup Validation")
    print("="*70)
    
    results = {}
    
    # Run all checks
    results['dependencies'] = check_dependencies()
    results['api_keys'], results['api_keys_optional'] = check_api_keys()
    results['core_imports'] = check_core_imports()
    results['databases'] = check_databases()
    results['config'] = check_config_file()
    
    # Summary
    print_section("Summary")
    
    print("Core Requirements:")
    print_check("Dependencies installed", results['dependencies'])
    print_check("Required API keys configured", results['api_keys'])
    print_check("Core modules importable", results['core_imports'])
    print_check("Configuration file valid", results['config'])
    
    print("\nOptional:")
    print_check("Optional API keys configured", results['api_keys_optional'])
    print_check("Databases initialized", results['databases'])
    
    # Overall status
    print("\n" + "="*70)
    
    core_ready = all([
        results['dependencies'],
        results['api_keys'],
        results['core_imports'],
        results['config']
    ])
    
    if core_ready:
        print("✅ CORE SYSTEM READY!")
        print("   You can proceed with testing.")
        if not results['databases']:
            print("   ⚠️  Run database migrations first: python database/migration_system.py")
        return 0
    else:
        print("❌ SYSTEM NOT READY")
        print("   Fix the issues above before proceeding.")
        print("\nQuick fixes:")
        if not results['dependencies']:
            print("   - Install dependencies: pip install -r requirements.txt")
        if not results['api_keys']:
            print("   - Configure API keys: python scripts/setup_api_keys.py")
        if not results['core_imports']:
            print("   - Check Python path and module structure")
        if not results['config']:
            print("   - Ensure config.json exists and is valid")
        return 1


if __name__ == '__main__':
    sys.exit(main())
















































