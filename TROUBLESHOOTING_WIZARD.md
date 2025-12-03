# Setup Wizard Troubleshooting Guide

## Quick Diagnostic Checklist

If you're having issues with the setup wizard, work through this checklist:

- [ ] Do you have all required credentials ready?
- [ ] Is your internet connection working?
- [ ] Do you have write permissions in the bot directory?
- [ ] Is config.json not open in another program?
- [ ] Have you tried restarting the application?

## Common Errors

### Validation Errors

#### "API ID should be a 7-8 digit number"

**Cause:** API ID format is incorrect

**Solutions:**
1. Copy the API ID again from https://my.telegram.org/apps
2. Make sure there are no spaces or letters
3. Should be 7-8 digits only (e.g., `12345678`)

**Example - Correct:** `12345678`
**Example - Incorrect:** `123 456 78`, `id12345678`, `12345`

---

#### "API Hash should be 32 hexadecimal characters"

**Cause:** API Hash is wrong length or contains invalid characters

**Solutions:**
1. Copy the entire hash from my.telegram.org/apps
2. Should be exactly 32 characters
3. Only contains: a-f and 0-9

**Example - Correct:** `0123456789abcdef0123456789abcdef`
**Example - Incorrect:** `0123456789abcdef` (too short), `0123456789abcdefghij...` (invalid characters)

---

####"Phone number must start with + and include country code"

**Cause:** Phone format is incorrect

**Solutions:**
1. Always start with `+`
2. Include country code
3. No spaces or dashes

**Examples - Correct:**
- USA: `+12345678900`
- UK: `+441234567890`
- India: `+911234567890`

**Examples - Incorrect:**
- `2345678900` (missing + and country code)
- `+1 234 567 8900` (has spaces)
- `+1-234-567-8900` (has dashes)

---

#### "Gemini API key should start with 'AIza'"

**Cause:** Wrong API key or incomplete copy

**Solutions:**
1. Get key from https://aistudio.google.com/app/apikey
2. Copy the ENTIRE key
3. Should start with "AIza" or "AIza"
4. Should be 39+ characters

**Example - Correct:** `AIzaSyABC123XYZ789...` (39+ chars)
**Example - Incorrect:** `ABC123XYZ` (doesn't start with AIza)

---

#### "SMS provider API key is required"

**Cause:** API key field is empty or too short

**Solutions:**
1. Log in to your SMS provider dashboard
2. Find the "API" or "API Key" section
3. Copy the full API key
4. Should be at least 10 characters

**Where to find it:**
- SMS-Activate: Profile → API Access
- DaisySMS: Dashboard → API
- 5SIM: Profile → API Key
- SMS-Hub: Profile → API

---

### Save Errors

#### "Failed to save configuration: Permission denied"

**Cause:** No write permissions

**Solutions:**
1. **Windows:** Run as administrator
2. **Linux/Mac:** Check folder permissions (`chmod 755`)
3. Make sure the folder isn't read-only
4. Close any programs that might have config.json open

**Check permissions:**
```bash
# Linux/Mac
ls -la config.json
chmod 644 config.json

# Windows - Right-click config.json → Properties → Uncheck "Read-only"
```

---

#### "Failed to save configuration: No space left on device"

**Cause:** Disk is full

**Solutions:**
1. Free up disk space
2. Delete old logs from `logs/` folder
3. Remove old backups
4. Check disk usage

**Check disk space:**
```bash
# Linux/Mac
df -h

# Windows - Check in File Explorer
```

---

#### "Failed to save configuration: File is being used by another process"

**Cause:** config.json is open elsewhere

**Solutions:**
1. Close any text editors with config.json open
2. Close other instances of the bot
3. Restart your computer if persists

---

### Wizard Not Showing

#### "Wizard doesn't appear on first launch"

**Possible Causes:**
1. `.wizard_complete` file already exists
2. config.json has all required settings
3. Application was previously configured

**Solutions:**

**To force wizard to show:**
```bash
# Delete the wizard completion marker
rm .wizard_complete

# Then restart the application
```

**Or manually trigger wizard:**
1. Open Settings
2. The wizard should detect missing settings
3. If not, delete config.json and restart

---

#### "Wizard shows again after I completed it"

**Cause:** Wizard completion marker wasn't saved or critical settings are missing

**Solutions:**
1. Check if `.wizard_complete` file exists
2. Verify all required settings in config.json:
   - telegram.api_id
   - telegram.api_hash
   - telegram.phone_number
   - gemini.api_key
   - sms_providers.provider
   - sms_providers.api_key

**Manually verify:**
```bash
# Check if wizard complete file exists
ls -la .wizard_complete

# Check config.json contents
cat config.json | grep -E "api_id|api_hash|phone_number|api_key|provider"
```

---

### Progress/State Issues

#### "Wizard lost my progress after I closed it"

**Expected Behavior:** As of the latest version, progress IS saved

**Solutions:**
1. Check for `.wizard_progress.json` file
2. If it exists, progress should resume
3. If not, you may need to fill in steps again

**To check saved progress:**
```bash
cat .wizard_progress.json
```

---

#### "I can't go back to previous step"

**Cause:** You're on Step 1 (first step)

**Solution:** "Previous" button is disabled on Step 1 - this is normal

---

#### "Skip button doesn't appear"

**Expected:** Skip button only appears on Step 4 (Optional Settings)

**Solution:** This is intentional - you cannot skip required steps

---

### Connection/API Errors

#### "Could not verify Gemini API key"

**Cause:** Key might be invalid or network issue

**Solutions:**
1. Verify key at https://aistudio.google.com/app/apikey
2. Check your internet connection
3. Try clicking "Test Configuration" in Settings
4. Generate a new API key if needed

**Test manually:**
```bash
# Test Gemini API
curl -H "Content-Type: application/json" \
     -d '{"contents":[{"parts":[{"text":"Hello"}]}]}' \
     "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=YOUR_API_KEY"
```

---

#### "Could not verify Telegram API credentials"

**Cause:** Credentials might be wrong or revoked

**Solutions:**
1. Double-check at https://my.telegram.org/apps
2. Make sure app wasn't deleted
3. Regenerate credentials if needed
4. Check for typos

---

#### "SMS provider API key invalid"

**Cause:** Wrong key or expired

**Solutions:**
1. Log in to SMS provider dashboard
2. Regenerate API key
3. Check account balance
4. Verify service is active

---

### UI/Display Issues

#### "Buttons are grayed out / disabled"

**Step-specific explanations:**
- **Previous button grayed:** You're on Step 1 (normal)
- **Next button grayed:** Fill in all fields first
- **Skip button missing:** Only appears on Step 4

**Solution:** Fill in required fields and validation will enable buttons

---

#### "I see duplicate fields"

**This was a bug in early versions and should be fixed**

**If you still see it:**
1. Update to latest version
2. Delete `.wizard_complete` and restart
3. Report the issue

---

#### "Progress bar doesn't update"

**Cause:** Validation failed

**Solution:** Make sure current step is valid before proceeding

**Check:**
1. All fields filled?
2. Green borders on fields (valid)?
3. No red borders (invalid)?

---

## Advanced Troubleshooting

### Reset Everything

If nothing works, start fresh:

```bash
# Backup your current config
cp config.json config.json.backup

# Delete wizard files
rm .wizard_complete
rm .wizard_progress.json

# Restart application
```

### Check Logs

Logs are your friend:

```bash
# View most recent log
tail -f logs/telegram_bot.log

# Search for errors
grep -i error logs/telegram_bot.log

# Search for wizard-related issues
grep -i wizard logs/telegram_bot.log
```

### Manually Edit config.json

**⚠️ Advanced users only! Make a backup first!**

```bash
# Backup
cp config.json config.json.manual_backup

# Edit
nano config.json  # or your preferred editor
```

Required structure:
```json
{
  "telegram": {
    "api_id": "12345678",
    "api_hash": "0123456789abcdef0123456789abcdef",
    "phone_number": "+1234567890"
  },
  "gemini": {
    "api_key": "AIzaSyABC123..."
  },
  "sms_providers": {
    "provider": "sms-activate",
    "api_key": "your_sms_api_key"
  }
}
```

### Force Skip Wizard (Emergency Only)

**Only if you know what you're doing:**

```bash
# Create wizard complete marker manually
echo '{"completed": true, "timestamp": "2024-01-01T00:00:00", "version": "1.0"}' > .wizard_complete
```

## Prevention Tips

### Before Starting Wizard

✅ Have all credentials ready
✅ Test your internet connection
✅ Close other programs
✅ Have sufficient disk space
✅ Know where to get each credential

### During Wizard

✅ Read instructions carefully
✅ Double-check each field before proceeding
✅ Use "Test" buttons when available
✅ Don't rush through steps
✅ Save your credentials in a password manager

### After Wizard

✅ Verify settings were saved
✅ Test with "Test Configuration" button
✅ Keep backup of config.json
✅ Document any custom changes

## Still Having Issues?

### Self-Help Resources

1. Read `USER_GUIDE_SETUP_WIZARD.md`
2. Check `GUIDED_SETUP_IMPLEMENTATION.md` for technical details
3. Review `README.md` for general setup

### Report a Bug

If you found a genuine bug:

1. Check logs: `logs/telegram_bot.log`
2. Note exact error message
3. Document steps to reproduce
4. Include your environment (OS, Python version)
5. **Don't include** your actual API keys!

### Get Help

When asking for help, provide:
- Exact error message
- What step you're on
- What you tried
- Relevant log excerpts (without API keys!)
- Your OS and Python version

## Quick Reference

### File Locations

- **Config:** `config.json`
- **Wizard complete marker:** `.wizard_complete`
- **Progress save:** `.wizard_progress.json`
- **Backup:** `config.json.backup`
- **Logs:** `logs/telegram_bot.log`

### Important URLs

- **Telegram API:** https://my.telegram.org/apps
- **Gemini API:** https://aistudio.google.com/app/apikey
- **SMS-Activate:** https://sms-activate.org/
- **DaisySMS:** https://daisysms.com/
- **5SIM:** https://5sim.net/
- **SMS-Hub:** https://smshub.org/

### Keyboard Shortcuts

- **Enter:** Next step
- **Shift+Enter:** Previous step
- **Escape:** Go back
- **Ctrl+S:** Complete (Step 4 only)

---

**Remember:** Most issues are simple - double-check your credentials and make sure you've followed the format examples exactly!



