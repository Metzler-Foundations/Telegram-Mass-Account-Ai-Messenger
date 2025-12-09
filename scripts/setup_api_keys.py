#!/usr/bin/env python3
"""
API Key Setup Helper - Interactive script to configure all required credentials.

This script helps you set up all required API keys for the Telegram automation platform.
It will guide you through setting each credential and validate they're configured correctly.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.secrets_manager import SecretsManager, get_secrets_manager


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_success(text):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text):
    """Print error message."""
    print(f"❌ {text}")


def print_warning(text):
    """Print warning message."""
    print(f"⚠️  {text}")


def print_info(text):
    """Print info message."""
    print(f"ℹ️  {text}")


def check_api_keys_status():
    """Check which API keys are configured."""
    print_header("Checking API Key Configuration Status")
    
    secrets = get_secrets_manager()
    
    keys_to_check = {
        'telegram_api_id': 'Telegram API ID',
        'telegram_api_hash': 'Telegram API Hash',
        'gemini_api_key': 'Google Gemini API Key',
        'sms_provider_api_key': 'SMS Provider API Key'
    }
    
    status = {}
    all_set = True
    
    for key_name, display_name in keys_to_check.items():
        try:
            value = secrets.get_secret(key_name)
            if value:
                print_success(f"{display_name}: CONFIGURED")
                status[key_name] = True
            else:
                print_error(f"{display_name}: NOT SET")
                status[key_name] = False
                all_set = False
        except Exception as e:
            print_error(f"{display_name}: ERROR - {e}")
            status[key_name] = False
            all_set = False
    
    print()
    return status, all_set


def get_api_key_instructions():
    """Return instructions for getting each API key."""
    return {
        'telegram_api_id': {
            'name': 'Telegram API ID',
            'url': 'https://my.telegram.org/apps',
            'instructions': [
                '1. Go to https://my.telegram.org/apps',
                '2. Log in with your phone number',
                '3. Click "API development tools"',
                '4. Create a new application (if you haven\'t already)',
                '5. Copy the "api_id" value (it\'s a number like 12345678)',
            ],
            'example': '12345678',
            'env_var': 'SECRET_TELEGRAM_API_ID'
        },
        'telegram_api_hash': {
            'name': 'Telegram API Hash',
            'url': 'https://my.telegram.org/apps',
            'instructions': [
                '1. From the same page as API ID',
                '2. Copy the "api_hash" value',
                '3. It looks like: 0123456789abcdef0123456789abcdef',
            ],
            'example': '0123456789abcdef0123456789abcdef',
            'env_var': 'SECRET_TELEGRAM_API_HASH'
        },
        'gemini_api_key': {
            'name': 'Google Gemini API Key',
            'url': 'https://ai.google.dev',
            'instructions': [
                '1. Go to https://ai.google.dev',
                '2. Click "Get API key in Google AI Studio"',
                '3. Sign in with your Google account',
                '4. Click "Create API key"',
                '5. Copy the generated key',
            ],
            'example': 'AIzaSyABC123...',
            'env_var': 'SECRET_GEMINI_API_KEY'
        },
        'sms_provider_api_key': {
            'name': 'SMS Provider API Key',
            'url': 'https://daisysms.com (or your chosen provider)',
            'instructions': [
                '1. Choose an SMS provider (SMSPool, DaisySMS, TextVerified, etc.)',
                '2. Create an account',
                '3. Add funds ($5-10 is enough for testing)',
                '4. Generate or copy your API key',
                '5. Note: Each phone number costs $0.08-$0.15',
            ],
            'example': 'your-sms-api-key-here',
            'env_var': 'SECRET_SMS_PROVIDER_API_KEY',
            'optional': True
        }
    }


def interactive_setup():
    """Interactive setup wizard."""
    print_header("Interactive API Key Setup Wizard")
    
    print("This wizard will help you configure all required API keys.")
    print("You can set them via environment variables or store them securely.")
    print()
    
    instructions = get_api_key_instructions()
    
    for key_name, info in instructions.items():
        print_header(f"Configure: {info['name']}")
        
        if info.get('optional'):
            print_warning("This key is OPTIONAL for basic testing")
        
        print(f"📍 Get it here: {info['url']}")
        print()
        print("Instructions:")
        for instruction in info['instructions']:
            print(f"  {instruction}")
        print()
        print(f"Example format: {info['example']}")
        print()
        print(f"To set this key, run:")
        print(f"  export {info['env_var']}=\"your-key-here\"")
        print()
        
        input("Press Enter when you've set this key (or to skip)...")
        print()
    
    # Re-check status
    print_header("Verifying Configuration")
    status, all_set = check_api_keys_status()
    
    if all_set:
        print_success("All required API keys are configured! 🎉")
        return True
    else:
        print_warning("Some keys are still missing. The application may not work fully.")
        print()
        print("To configure missing keys, set these environment variables:")
        for key_name, is_set in status.items():
            if not is_set:
                info = instructions.get(key_name, {})
                env_var = info.get('env_var', f'SECRET_{key_name.upper()}')
                print(f"  export {env_var}=\"your-key-here\"")
        return False


def generate_env_file():
    """Generate a template .env file."""
    print_header("Generate .env Template File")
    
    env_template = """# Telegram Bot API Credentials Configuration
# Copy this file to .env and fill in your actual values
# DO NOT commit .env to version control!

# Telegram API Credentials
# Get from: https://my.telegram.org/apps
SECRET_TELEGRAM_API_ID="your_api_id_here"
SECRET_TELEGRAM_API_HASH="your_api_hash_here"

# Google Gemini API Key
# Get from: https://ai.google.dev
SECRET_GEMINI_API_KEY="your_gemini_key_here"

# SMS Provider API Key (Optional for testing)
# Get from your chosen SMS provider (SMSPool, DaisySMS, etc.)
SECRET_SMS_PROVIDER_API_KEY="your_sms_key_here"

# Master Encryption Key (auto-generated if not set)
# Only needed if you want to share encrypted data across systems
# SECRET_MASTER_KEY="your_master_key_here"

# Application Environment
APP_ENV="development"

# Load this file with: source .env
"""
    
    env_file = Path(__file__).parent.parent / '.env.template'
    
    with open(env_file, 'w') as f:
        f.write(env_template)
    
    print_success(f"Created template file: {env_file}")
    print()
    print("To use this template:")
    print("  1. Copy it: cp .env.template .env")
    print("  2. Edit .env and add your real API keys")
    print("  3. Load it: source .env")
    print("  4. Run the application")
    print()


def main():
    """Main entry point."""
    print_header("Telegram Automation Platform - API Key Setup")
    
    print("This script will help you configure all required API credentials.")
    print()
    
    while True:
        print("What would you like to do?")
        print()
        print("  1. Check current API key status")
        print("  2. Interactive setup wizard")
        print("  3. Generate .env template file")
        print("  4. Show environment variable commands")
        print("  5. Exit")
        print()
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            check_api_keys_status()
            
        elif choice == '2':
            interactive_setup()
            
        elif choice == '3':
            generate_env_file()
            
        elif choice == '4':
            print_header("Environment Variable Commands")
            instructions = get_api_key_instructions()
            print("Copy and run these commands (with your actual values):")
            print()
            for key_name, info in instructions.items():
                print(f"export {info['env_var']}=\"your-actual-key-here\"")
            print()
            
        elif choice == '5':
            print()
            print("Exiting setup. Remember to configure your API keys!")
            break
            
        else:
            print_error("Invalid choice. Please enter 1-5.")
        
        print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)
    except Exception as e:
        print_error(f"Setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


















































