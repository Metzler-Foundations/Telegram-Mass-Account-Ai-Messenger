# 🚨 CRITICAL BUGS FOUND IN ACCOUNT CREATION FLOW

## Bug #1: API Credentials Not Accessible (SHOW-STOPPER)

**Location**: `settings_window.py` lines 2768-2770

**Problem**:
```python
if hasattr(main_window, 'api_widget'):
    api_id = getattr(main_window.api_widget, 'api_id_edit', lambda: '').text().strip()
    api_hash = getattr(main_window.api_widget, 'api_hash_edit', lambda: '').text().strip()
```

**Issue**: Tries to access `main_window.api_widget` but `api_widget` is an attribute of `SettingsWindow` (self), NOT `main_window`!

**Impact**: Account creation will ALWAYS fail to get API credentials after wizard completion.

**Fix Required**: Change to `self.api_widget`

---

## Bug #2: Wizard SMS Provider Settings Ignored (SHOW-STOPPER)

**Location**: `settings_window.py` lines 2742-2743

**Problem**:
```python
provider = self.phone_provider_combo.currentText()
api_key = self.provider_api_edit.text().strip()
```

**Issue**: Gets SMS provider from Account Factory tab UI fields, NOT from wizard-saved config or sms_provider_widget!

**Impact**: If user completes wizard and immediately tries to create account, the SMS provider from wizard won't be used. User must RE-ENTER it in Account Factory tab.

**Fix Required**: 
1. Load from config.json first
2. Fall back to UI fields if present
3. Or load sms_provider_widget settings

---

## Bug #3: ElevenLabs Key Not Accessible

**Location**: `settings_window.py` line 2814

**Problem**:
```python
if hasattr(main_window, 'api_widget') and hasattr(main_window.api_widget, 'elevenlabs_key_edit'):
    elevenlabs_key = main_window.api_widget.elevenlabs_key_edit.text().strip()
```

**Issue**: Same as Bug #1 - wrong object reference.

**Impact**: Voice features won't work.

**Fix Required**: Change to `self.api_widget`

---

## Bug #4: Inconsistent Data Source

**Problem**: Account creation mixes data sources:
- Tries to get API credentials from `main_window.api_widget` (wrong)
- Gets SMS provider from Account Factory tab UI (ignores wizard)
- Should use config.json as single source of truth

**Impact**: Wizard completion doesn't actually enable account creation!

**Fix Required**: Load all settings from config.json OR use self.api_widget

---

## Severity: CRITICAL

These bugs mean:
- ❌ Account creation WILL NOT WORK after wizard completion
- ❌ User must manually re-enter ALL settings in Account Factory tab
- ❌ Wizard is effectively useless for account creation
- ❌ End-to-end flow is BROKEN

## Status: MUST FIX IMMEDIATELY

