#!/usr/bin/env python3
"""
Deployment Diagnostics Script

Run this to diagnose common deployment issues before deploying to Railway.
"""

import sys
import os
from pathlib import Path

def check_python_version():
    """Check Python version compatibility."""
    print("\n🔍 Checking Python version...")
    version = sys.version_info
    print(f"  Python {version.major}.{version.minor}.{version.micro}")
    
    if version < (3, 10):
        print("  ❌ Python 3.10+ required")
        return False
    print("  ✅ Python version OK")
    return True

def check_required_packages():
    """Check if all required packages can be imported."""
    print("\n🔍 Checking required packages...")
    
    packages = {
        'discord': 'discord.py',
        'replicate': 'replicate',
        'httpx': 'httpx',
        'PIL': 'pillow',
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn',
        'dotenv': 'python-dotenv',
        'openai': 'openai',
        'cv2': 'opencv-python-headless',
        'sentry_sdk': 'sentry-sdk'
    }
    
    all_ok = True
    for module, package in packages.items():
        try:
            __import__(module)
            print(f"  ✅ {package}")
        except ImportError as e:
            print(f"  ❌ {package} - {e}")
            all_ok = False
    
    return all_ok

def check_environment_variables():
    """Check if required environment variables are set."""
    print("\n🔍 Checking environment variables...")
    
    required = [
        'DISCORD_BOT_TOKEN',
        'DISCORD_GUILD_ID',
        'REPLICATE_API_TOKEN'
    ]
    
    optional = [
        'DISCORD_APPLICATION_ID',
        'REPLICATE_DESTINATION_OWNER',
        'SENTRY_DSN'
    ]
    
    all_ok = True
    for var in required:
        value = os.environ.get(var)
        if value and value not in ['', 'your_token_here', 'your_guild_id_here']:
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"  ✅ {var}: {masked}")
        else:
            print(f"  ❌ {var}: NOT SET")
            all_ok = False
    
    for var in optional:
        value = os.environ.get(var)
        if value and value not in ['', 'your_token_here']:
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"  ℹ️  {var}: {masked}")
        else:
            print(f"  ⚠️  {var}: NOT SET (optional)")
    
    return all_ok

def check_file_structure():
    """Check if required files and directories exist."""
    print("\n🔍 Checking file structure...")
    
    required_files = [
        'src/discord_ai_photo_bot/__init__.py',
        'src/discord_ai_photo_bot/bot.py',
        'src/discord_ai_photo_bot/config.py',
        'src/discord_ai_photo_bot/database.py',
        'requirements.txt',
        'Dockerfile'
    ]
    
    all_ok = True
    for file_path in required_files:
        full_path = Path(file_path)
        if full_path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - NOT FOUND")
            all_ok = False
    
    return all_ok

def check_imports():
    """Check if bot modules can be imported."""
    print("\n🔍 Checking bot module imports...")
    
    # Add src to path
    src_path = Path(__file__).parent / 'src'
    if src_path.exists():
        sys.path.insert(0, str(src_path))
    
    modules_to_test = [
        'discord_ai_photo_bot',
        'discord_ai_photo_bot.config',
        'discord_ai_photo_bot.database',
        'discord_ai_photo_bot.bot'
    ]
    
    all_ok = True
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except Exception as e:
            print(f"  ❌ {module} - {e}")
            all_ok = False
    
    return all_ok

def main():
    """Run all diagnostic checks."""
    print("=" * 70)
    print("  Discord AI Photo Bot - Deployment Diagnostics")
    print("=" * 70)
    
    results = []
    
    results.append(("Python Version", check_python_version()))
    results.append(("Required Packages", check_required_packages()))
    results.append(("Environment Variables", check_environment_variables()))
    results.append(("File Structure", check_file_structure()))
    results.append(("Module Imports", check_imports()))
    
    print("\n" + "=" * 70)
    print("  DIAGNOSTIC SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    
    if all_passed:
        print("🎉 All checks passed! Ready for deployment.")
        return 0
    else:
        print("❌ Some checks failed. Fix the issues above before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())