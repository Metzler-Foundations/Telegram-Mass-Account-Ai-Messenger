#!/usr/bin/env python3
"""
Secure master key generation for secrets management system.
"""

import base64
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet


def generate_master_key():
    """Generate and save a new master encryption key."""
    # Generate new key
    key = Fernet.generate_key()
    
    # Create secure directory
    key_dir = Path.home() / ".telegram_bot"
    key_dir.mkdir(parents=True, exist_ok=True)
    
    # Save key file
    key_file = key_dir / "master.key"
    with open(key_file, "wb") as f:
        f.write(key)
    
    # Set secure permissions (owner read/write only)
    os.chmod(key_file, 0o600)
    
    # Display key for user
    encoded_key = base64.urlsafe_b64encode(key).decode()
    
    print("✅ Master key generated successfully!")
    print(f"🔑 Key file saved to: {key_file}")
    print(f"🔒 File permissions set to: 0600 (owner read/write only)")
    print()
    print("🚨 IMPORTANT: Save this master key for production!")
    print("📋 Copy this line for your production environment:")
    print(f"export SECRET_MASTER_KEY={encoded_key}")
    print()
    print("🔐 Key details:")
    print(f"   Algorithm: Fernet (AES-128-CBC with HMAC-SHA256)")
    print(f"   Key length: {len(key)} bytes")
    print(f"   Base64 encoded: {len(encoded_key)} characters")
    
    return key, encoded_key


if __name__ == "__main__":
    try:
        generate_master_key()
    except Exception as e:
        print(f"❌ Error generating master key: {e}")
        sys.exit(1)