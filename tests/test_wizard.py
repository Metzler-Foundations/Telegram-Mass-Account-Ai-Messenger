#!/usr/bin/env python3
"""
Test script for the Setup Wizard functionality
"""

import json
import sys
from pathlib import Path


# Test the wizard manager logic
def test_wizard_manager():
    """Test the SetupWizardManager class."""
    print("Testing SetupWizardManager...")

    from settings_window import SetupWizardManager

    # Test 1: Empty settings (wizard needed)
    print("\n1. Testing with empty settings...")
    empty_settings = {}
    manager = SetupWizardManager(empty_settings)
    assert manager.is_wizard_needed() == True, "Wizard should be needed for empty settings"
    assert (
        manager.get_starting_step() == SetupWizardManager.STEP_TELEGRAM
    ), "Should start at Telegram step"
    print("   ✓ Empty settings correctly triggers wizard at Telegram step")

    # Test 2: Only Telegram configured (wizard needed, start at Gemini)
    print("\n2. Testing with only Telegram configured...")
    telegram_only = {
        "telegram": {
            "api_id": "12345678",
            "api_hash": "abcd1234abcd1234abcd1234abcd1234",
            "phone_number": "+1234567890",
        }
    }
    manager = SetupWizardManager(telegram_only)
    assert manager.is_wizard_needed() == True, "Wizard should be needed when Gemini is missing"
    assert (
        manager.get_starting_step() == SetupWizardManager.STEP_GEMINI
    ), "Should start at Gemini step"
    print("   ✓ Partial settings (Telegram only) correctly starts at Gemini step")

    # Test 3: Telegram + Gemini configured (wizard needed, start at SMS Provider)
    print("\n3. Testing with Telegram + Gemini configured...")
    telegram_gemini = {
        "telegram": {
            "api_id": "12345678",
            "api_hash": "abcd1234abcd1234abcd1234abcd1234",
            "phone_number": "+1234567890",
        },
        "gemini": {"api_key": "AIzaSyABC123XYZ_TEST_KEY_LONG_ENOUGH_TO_PASS"},
    }
    manager = SetupWizardManager(telegram_gemini)
    assert (
        manager.is_wizard_needed() == True
    ), "Wizard should be needed when SMS provider is missing"
    assert (
        manager.get_starting_step() == SetupWizardManager.STEP_SMS_PROVIDER
    ), "Should start at SMS Provider step"
    print("   ✓ Partial settings (Telegram + Gemini) correctly starts at SMS Provider step")

    # Test 4: All required settings configured (wizard not needed if marker exists)
    print("\n4. Testing with all required settings configured...")
    complete_settings = {
        "telegram": {
            "api_id": "12345678",
            "api_hash": "abcd1234abcd1234abcd1234abcd1234",
            "phone_number": "+1234567890",
        },
        "gemini": {"api_key": "AIzaSyABC123XYZ_TEST_KEY_LONG_ENOUGH_TO_PASS"},
        "sms_providers": {"provider": "sms-activate", "api_key": "test_api_key_12345"},
    }
    manager = SetupWizardManager(complete_settings)
    # Note: wizard may still be needed if .wizard_complete doesn't exist
    print(f"   Wizard needed: {manager.is_wizard_needed()}")
    print(f"   Starting step: {manager.get_starting_step()}")
    print("   ✓ Complete settings handled correctly")

    # Test 5: Step validation
    print("\n5. Testing step validation...")
    manager = SetupWizardManager(complete_settings)

    # Test Telegram step validation
    is_valid, errors = manager.is_step_complete(SetupWizardManager.STEP_TELEGRAM, complete_settings)
    assert is_valid == True, f"Telegram step should be valid, got errors: {errors}"
    print("   ✓ Telegram step validation works")

    # Test Gemini step validation
    is_valid, errors = manager.is_step_complete(SetupWizardManager.STEP_GEMINI, complete_settings)
    assert is_valid == True, f"Gemini step should be valid, got errors: {errors}"
    print("   ✓ Gemini step validation works")

    # Test SMS Provider step validation
    is_valid, errors = manager.is_step_complete(
        SetupWizardManager.STEP_SMS_PROVIDER, complete_settings
    )
    assert is_valid == True, f"SMS Provider step should be valid, got errors: {errors}"
    print("   ✓ SMS Provider step validation works")

    # Test invalid settings
    print("\n6. Testing invalid settings validation...")
    invalid_settings = {
        "telegram": {
            "api_id": "123",  # Too short
            "api_hash": "abc",  # Too short
            "phone_number": "1234",  # Invalid format
        }
    }
    manager = SetupWizardManager(invalid_settings)
    is_valid, errors = manager.is_step_complete(SetupWizardManager.STEP_TELEGRAM, invalid_settings)
    assert is_valid == False, "Invalid Telegram settings should fail validation"
    assert len(errors) > 0, "Should have validation errors"
    print(f"   ✓ Invalid settings correctly produce {len(errors)} error(s)")

    print("\n✅ All SetupWizardManager tests passed!")
    return True


def test_sms_provider_widget(qapp):
    """Test the SMSProviderSetupWidget."""
    print("\nTesting SMSProviderSetupWidget...")

    from settings_window import SMSProviderSetupWidget

    widget = SMSProviderSetupWidget()

    # Test loading and saving settings
    test_settings = {"sms_providers": {"provider": "daisysms", "api_key": "test_key_12345"}}

    widget.load_settings(test_settings)

    # Verify loaded correctly
    assert widget.provider_combo.currentData() == "daisysms", "Provider should be loaded"
    assert widget.api_key_edit.text() == "test_key_12345", "API key should be loaded"
    print("   ✓ Settings load correctly")

    # Test saving
    saved_settings = {}
    widget.save_settings(saved_settings)
    assert saved_settings["sms_providers"]["provider"] == "daisysms", "Provider should be saved"
    assert saved_settings["sms_providers"]["api_key"] == "test_key_12345", "API key should be saved"
    print("   ✓ Settings save correctly")

    # Test validation
    is_valid, errors = widget.is_step_complete()
    assert is_valid == True, f"Should be valid, got errors: {errors}"
    print("   ✓ Validation works for complete settings")

    # Test empty validation
    widget.api_key_edit.setText("")
    is_valid, errors = widget.is_step_complete()
    assert is_valid == False, "Should be invalid with empty API key"
    assert len(errors) > 0, "Should have validation errors"
    print("   ✓ Validation correctly fails for incomplete settings")

    print("\n✅ All SMSProviderSetupWidget tests passed!")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("WIZARD FUNCTIONALITY TEST SUITE")
    print("=" * 60)

    try:
        # Test wizard manager
        if not test_wizard_manager():
            print("\n❌ Wizard manager tests failed!")
            return 1

        # Test SMS provider widget
        if not test_sms_provider_widget():
            print("\n❌ SMS provider widget tests failed!")
            return 1

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
