# Bug Report: Startup to Account Creation Flow

## Overview
This document identifies bugs found in the codebase from application startup through account creation.

---

## 🔴 Critical Bugs

### 1. Missing API Credentials in Account Creation Dialog
**File:** `ui/account_creation_dialog.py`  
**Lines:** 223-231  
**Severity:** Critical  
**Issue:** The account creation dialog prepares a config dictionary but does NOT include `api_id` and `api_hash`, which are required by `AccountCreator.create_new_account()` (line 1727 in `account_creator.py`).

**Current Code:**
```python
config = {
    'account_name': self.name_edit.text().strip(),
    'phone_number': self.phone_edit.text().strip() or None,
    'country': self.country_combo.currentText().split(" - ")[0],
    'sms_provider': self.provider_combo.currentText(),
    'api_key': self.api_key_edit.text().strip(),
    'use_proxy': self.use_proxy_checkbox.isChecked(),
    'start_warmup': self.warmup_checkbox.isChecked()
}
```

**Impact:** Account creation will always fail with error: "Telegram API credentials (api_id and api_hash) are required."

**Fix:** Load credentials from secrets_manager and add to config:
```python
from core.secrets_manager import get_secrets_manager
secrets = get_secrets_manager()
config['api_id'] = secrets.get_secret('telegram_api_id', required=True)
config['api_hash'] = secrets.get_secret('telegram_api_hash', required=True)
```

---

### 2. Wrong Config Key Names in Account Creation Dialog
**File:** `ui/account_creation_dialog.py`  
**Lines:** 227-228  
**Severity:** Critical  
**Issue:** The dialog uses `sms_provider` and `api_key`, but `AccountCreator` expects `phone_provider` and `provider_api_key`.

**Current Code:**
```python
'sms_provider': self.provider_combo.currentText(),
'api_key': self.api_key_edit.text().strip(),
```

**Expected by AccountCreator (line 1747-1748):**
```python
provider = config.get('phone_provider', 'sms-activate')
api_key = config.get('provider_api_key')
```

**Impact:** Account creation will fail because the provider and API key won't be found in the config.

**Fix:** Change keys to match:
```python
'phone_provider': self.provider_combo.currentText(),
'provider_api_key': self.api_key_edit.text().strip(),
```

---

### 3. AccountCreator Missing API Credentials Fallback
**File:** `accounts/account_creator.py`  
**Lines:** 1727-1731, 2007-2012  
**Severity:** High  
**Issue:** `create_new_account()` requires `api_id` and `api_hash` in the config dict, but doesn't fall back to loading from secrets_manager or environment variables like `_create_client_without_start()` does.

**Current Code (line 1727):**
```python
if not config.get('api_id') or not config.get('api_hash'):
    return {
        'success': False,
        'error': 'Telegram API credentials (api_id and api_hash) are required...'
    }
```

**Better Approach (like line 2007-2012):**
```python
api_id = config.get('api_id') or os.getenv("TELEGRAM_API_ID", "")
api_hash = config.get('api_hash') or os.getenv("TELEGRAM_API_HASH", "")

# Also try secrets_manager as fallback
if not api_id or not api_hash:
    try:
        from core.secrets_manager import get_secrets_manager
        secrets = get_secrets_manager()
        api_id = api_id or secrets.get_secret('telegram_api_id', required=False)
        api_hash = api_hash or secrets.get_secret('telegram_api_hash', required=False)
    except Exception:
        pass

if not api_id or not api_hash:
    return {
        'success': False,
        'error': 'Telegram API credentials (api_id and api_hash) are required...'
    }
```

**Impact:** Even if credentials are properly stored in secrets_manager, account creation will fail if they're not explicitly passed in the config dict.

---

## 🟡 Medium Severity Bugs

### 4. KeyError Risk in Welcome Wizard SMS Provider Handling
**File:** `ui/welcome_wizard.py`  
**Lines:** 234, 254  
**Severity:** Medium  
**Issue:** Code accesses `config["sms_providers"]["api_key"]` and `config["sms_providers"]["provider"]` without checking if the keys exist first.

**Current Code (line 234):**
```python
if config["sms_providers"]["api_key"]:
    secrets_manager.set_secret('sms_provider_api_key', config["sms_providers"]["api_key"])
```

**Current Code (line 254):**
```python
provider_name = config["sms_providers"]["provider"].lower().replace(' ', '_')
```

**Impact:** If user skips SMS provider setup or the config structure is different, this will raise KeyError.

**Fix:** Use `.get()` with defaults:
```python
sms_api_key = config.get("sms_providers", {}).get("api_key")
if sms_api_key:
    secrets_manager.set_secret('sms_provider_api_key', sms_api_key)

provider_name = config.get("sms_providers", {}).get("provider", "unknown").lower().replace(' ', '_')
```

---

### 5. Duplicate Phone Number Field in Welcome Wizard
**File:** `ui/welcome_wizard.py`  
**Lines:** 707, 794  
**Severity:** Medium  
**Issue:** Phone number is collected on both page 1 (TelegramSetupPage) and page 2 (PhoneSetupPage), but only page 2's value is used (line 127).

**Impact:** User confusion - they might enter phone number on page 1, but it gets ignored. The field on page 1 should either be removed or the logic should use page 1's value.

**Fix:** Either:
1. Remove phone field from TelegramSetupPage (page 1), OR
2. Use page 1's phone value if page 2's is empty

---

### 6. AccountCreator Missing Dependencies
**File:** `accounts/account_manager.py`  
**Line:** 1619  
**Severity:** Medium  
**Issue:** Creates `AccountCreator` without passing `gemini_service` and `account_manager` references, even though they're available.

**Current Code:**
```python
creator = AccountCreator(self.db)
```

**Better:**
```python
creator = AccountCreator(
    self.db,
    gemini_service=self.gemini_service if hasattr(self, 'gemini_service') else None,
    account_manager=self
)
```

**Impact:** AccountCreator won't have access to gemini_service for advanced cloning features, and won't be able to notify account_manager directly.

---

### 7. Proxy Release Race Condition
**File:** `accounts/account_manager.py`  
**Lines:** 1644-1646  
**Severity:** Medium  
**Issue:** Releases proxy for `temp_phone` after account creation, but the proxy may have already been transferred/released in `AccountCreator.create_new_account()` (lines 1806-1808).

**Current Code:**
```python
if proxy_pool and config.get('proxy_key'):
    await proxy_pool.release_proxy(temp_phone)
    await proxy_pool.get_proxy_for_account(phone_number)
```

**Impact:** Potential double-release or attempting to release a proxy that's already been transferred, causing errors.

**Fix:** Check if proxy was already transferred before releasing:
```python
if proxy_pool and config.get('proxy_key'):
    # Only release temp_phone if it still exists (wasn't transferred)
    # AccountCreator should have already transferred it
    try:
        await proxy_pool.release_proxy(temp_phone)
    except Exception as e:
        logger.debug(f"Proxy already released/transferred: {e}")
    await proxy_pool.get_proxy_for_account(phone_number)
```

---

### 8. Incomplete Account Creation Dialog Implementation
**File:** `ui/account_creation_dialog.py`  
**Lines:** 241-257  
**Severity:** Medium  
**Issue:** `_do_async_creation()` method is a stub that simulates account creation instead of actually calling the real account creation flow.

**Current Code:**
```python
def _do_async_creation(self, config: Dict[str, Any]):
    # ...
    # Simulate progress (replace with real async calls)
    QTimer.singleShot(2000, lambda: self._complete_creation({
        'phone_number': '+1234567890',
        'account_name': config['account_name'],
        'status': 'created'
    }))
```

**Impact:** Account creation dialog doesn't actually create accounts - it just simulates success.

**Fix:** Implement proper async account creation using the account_manager:
```python
async def _do_async_creation(self, config: Dict[str, Any]):
    try:
        main_window = self.parent()
        if not main_window or not hasattr(main_window, 'account_manager'):
            raise Exception("Account manager not available")
        
        result = await main_window.account_manager.create_account(config)
        if result.get('success'):
            self._complete_creation(result['account'])
        else:
            self._show_error(result.get('error', 'Account creation failed'))
    except Exception as e:
        logger.error(f"Async creation failed: {e}")
        self._show_error(f"Account creation failed: {e}")
```

---

## 🟢 Low Severity / Code Quality Issues

### 9. Inconsistent Error Handling in Welcome Wizard
**File:** `ui/welcome_wizard.py`  
**Line:** 260  
**Severity:** Low  
**Issue:** If secrets_manager fails, the error is logged but the wizard continues anyway. This might lead to credentials not being saved securely.

**Impact:** User might think credentials are saved securely when they're not.

---

### 10. Missing Validation for Optional SMS Provider
**File:** `ui/welcome_wizard.py`  
**Line:** 199-212  
**Severity:** Low  
**Issue:** SMS provider validation is attempted even when API key is empty, but the validation might not handle empty keys gracefully.

**Impact:** Unclear error messages if validation fails on empty input.

---

## Summary

**Total Bugs Found:** 10
- **Critical:** 3
- **Medium:** 5  
- **Low:** 2

**Most Critical Issues:**
1. Account creation dialog missing API credentials (Bug #1)
2. Wrong config key names (Bug #2)
3. AccountCreator not loading credentials from secrets_manager (Bug #3)

**Recommended Fix Priority:**
1. Fix Bugs #1, #2, #3 immediately (account creation is broken)
2. Fix Bug #8 (incomplete implementation)
3. Fix Bugs #4, #5, #6, #7 (improve robustness)
4. Address Bugs #9, #10 (code quality)

