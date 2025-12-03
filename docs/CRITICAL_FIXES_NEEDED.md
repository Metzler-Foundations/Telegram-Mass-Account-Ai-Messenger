# CRITICAL WIZARD FIXES - IMPLEMENTATION PLAN

## Issue #1 & #2: Duplicate Widget Display + Widget Reuse

**Problem**: Steps 0 and 1 both use the same `api_widget` instance, which:
- Shows ALL fields (Telegram + Gemini + Advanced) on both steps
- Violates Qt's single-parent rule
- Confuses users with duplicate content

**Solution**: Create step-specific wrapper widgets that show only relevant fields

### Implementation:
1. Create `TelegramStepWidget` - shows only Telegram fields from API widget
2. Create `GeminiStepWidget` - shows only Gemini field from API widget
3. Both read from/write to the same underlying `api_widget` data
4. Each step has its own widget instance

## Issue #3: No Field Auto-Focus

**Problem**: When step loads, cursor isn't in any field

**Solution**: Add auto-focus logic to `_show_wizard_step()`

### Implementation:
1. After showing step, find first empty required field
2. Call `.setFocus()` on that field
3. For Step 1 (Telegram): Focus api_id_edit if empty
4. For Step 2 (Gemini): Focus gemini_key_edit if empty
5. For Step 3 (SMS): Focus api_key_edit if empty

## Issue #4 & #5: Validation Uses Wrong Data

**Problem**: Validates entire collected settings, not current step fields

**Solution**: Create step-specific validation that checks UI directly

### Implementation:
1. For Step 0 (Telegram): Call `api_widget.is_telegram_step_complete()`
2. For Step 1 (Gemini): Call `api_widget.is_gemini_step_complete()`
3. For Step 2 (SMS): Call `sms_provider_widget.is_step_complete()`
4. Don't use `collect_ui_settings()` for validation, use it only for saving

This ensures we're validating what user can see, not the entire form.




