#!/usr/bin/env python3
"""Device fingerprint randomization to prevent collision."""

import logging
import random
import hashlib
from typing import Dict

logger = logging.getLogger(__name__)


class DeviceFingerprintRandomizer:
    """Randomizes device fingerprints to prevent collisions."""
    
    DEVICE_MODELS = [
        "SM-G991B", "SM-G998B", "SM-A525F", "SM-A326B",  # Samsung
        "iPhone14,2", "iPhone14,3", "iPhone13,2", "iPhone13,4",  # iPhone
        "Pixel 7", "Pixel 7 Pro", "Pixel 6", "Pixel 6a",  # Google Pixel
        "ONEPLUS A6013", "ONEPLUS KB2003", "ONEPLUS LE2123",  # OnePlus
        "M2012K11AG", "M2102J20SG", "2201117TG",  # Xiaomi
    ]
    
    APP_VERSIONS = [
        "10.2.4", "10.2.3", "10.2.2", "10.2.1",
        "10.1.5", "10.1.4", "10.1.3",
    ]
    
    SYSTEM_VERSIONS = [
        "13.0", "12.0", "11.0", "14.0"
    ]
    
    @staticmethod
    def generate_fingerprint(account_id: str) -> Dict[str, str]:
        """Generate unique device fingerprint."""
        # Use account ID to seed for consistency across sessions
        seed = int(hashlib.sha256(account_id.encode()).hexdigest(), 16)
        random.seed(seed)
        
        fingerprint = {
            'device_model': random.choice(DeviceFingerprintRandomizer.DEVICE_MODELS),
            'app_version': random.choice(DeviceFingerprintRandomizer.APP_VERSIONS),
            'system_version': random.choice(DeviceFingerprintRandomizer.SYSTEM_VERSIONS),
            'lang_code': random.choice(['en', 'en-US', 'en-GB']),
            'system_lang_code': random.choice(['en-US', 'en-GB', 'en']),
        }
        
        random.seed()  # Reset seed
        
        logger.debug(f"Generated fingerprint for {account_id}: {fingerprint['device_model']}")
        return fingerprint
    
    @staticmethod
    def verify_uniqueness(fingerprints: list) -> bool:
        """Verify fingerprints are unique."""
        fingerprint_hashes = set()
        
        for fp in fingerprints:
            fp_str = f"{fp['device_model']}|{fp['app_version']}|{fp['system_version']}"
            fp_hash = hashlib.sha256(fp_str.encode()).hexdigest()
            
            if fp_hash in fingerprint_hashes:
                logger.warning("Duplicate fingerprint detected!")
                return False
            
            fingerprint_hashes.add(fp_hash)
        
        return True


def generate_device_fingerprint(account_id: str) -> Dict[str, str]:
    """Generate device fingerprint."""
    return DeviceFingerprintRandomizer.generate_fingerprint(account_id)


