# Setup Wizard - User Guide

## Welcome!

This guide will help you complete the initial setup of your Telegram Auto-Reply Bot. The setup wizard will guide you through configuring all essential settings.

## What You'll Need

Before starting, gather these items:

### 1. Telegram API Credentials
- **API ID** (7-8 digits)
- **API Hash** (32 characters)
- **Phone Number** (with country code)

**Where to get them:**
1. Visit https://my.telegram.org/apps
2. Log in with your phone number
3. Go to "API Development Tools"
4. Create a new application
5. Copy your API ID and API Hash

### 2. Google Gemini API Key
- **API Key** (starts with "AIza", 39+ characters)

**Where to get it:**
1. Visit https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated key

**Free Tier:** 60 requests/minute, 1,500 requests/day (more than enough for most users)

### 3. SMS Provider Account
You'll need an account with one of these SMS providers to receive verification codes:

**Recommended for Beginners: SMS-Activate**
- Website: https://sms-activate.org/
- Cost: ~$0.10-0.20 per phone number
- Easy to use, reliable

**Other Options:**
- DaisySMS (https://daisysms.com/)
- 5SIM (https://5sim.net/)
- SMS-Hub (https://smshub.org/)

**Setup:**
1. Create an account with your chosen provider
2. Add funds ($5-10 is enough to start)
3. Get your API key from the dashboard

## Step-by-Step Walkthrough

### Step 1: Telegram API Configuration

**What you'll see:**
- API ID field
- API Hash field  
- Phone Number field

**How to fill it out:**
1. Enter your API ID (e.g., `12345678`)
2. Enter your API Hash (click "Show API Hash" if you want to verify)
3. Enter your phone number with country code (e.g., `+1234567890`)

**Validation:**
- API ID: Must be 7-8 digits
- API Hash: Must be exactly 32 hexadecimal characters
- Phone: Must start with `+` and include country code

**Tips:**
- Use the "🔗 Open Setup Page" button to open the Telegram API portal
- Double-check your API Hash - it's easy to miss a character
- Include the `+` in your phone number

**Keyboard Shortcuts:**
- Press `Enter` to move to the next step (after filling all fields)
- Click "Previous" or press `Escape` to go back

### Step 2: Gemini AI Configuration

**What you'll see:**
- Gemini API Key field

**How to fill it out:**
1. Enter your Gemini API key (starts with "AIza")
2. Click "Show API Key" if you want to verify what you typed

**Validation:**
- Must start with "AIza"
- Must be at least 30 characters long

**Tips:**
- The free tier is perfect for getting started
- You can upgrade later if you need more API calls
- Use the "🔗 Open Setup Page" button to get your key

### Step 3: SMS Provider Configuration

**What you'll see:**
- Provider selection dropdown
- API Key field
- Test button

**How to fill it out:**
1. Choose your SMS provider from the dropdown (SMS-Activate is marked as recommended)
2. Enter your API key from the provider's dashboard
3. Click "🧪 Test API Key" to verify it works

**Tips:**
- Click "✨ Sign Up" if you haven't created an account yet
- Click "📋 Get API Key" to open the provider's API page
- Make sure you have funds in your account before creating accounts

### Step 4: Optional Settings (Safe to Skip)

**What you'll see:**
- Anti-detection settings (rate limiting, delays, etc.)

**Should you configure this?**
- **Beginners:** Skip this step! The defaults are great.
- **Advanced users:** Fine-tune if you have specific needs.

**What the defaults do:**
- 50 messages per hour limit (safe rate)
- 2-30 second delays between actions
- Automatic session recovery
- Human behavior simulation

**Tip:** You can always come back and adjust these in Settings later.

## Keyboard Shortcuts

While using the wizard, you can use these shortcuts:

- **Enter** - Move to next step
- **Shift+Enter** - Go back to previous step
- **Escape** - Go back to previous step
- **Ctrl+S** - Complete setup (on Step 4 only)

## Common Issues & Solutions

### "API ID should be a 7-8 digit number"
- Make sure you're entering only numbers, no spaces or letters
- Check that you copied the full API ID from my.telegram.org

### "API Hash should be 32 hexadecimal characters"
- API Hash should be exactly 32 characters
- It only contains letters a-f and numbers 0-9
- Make sure you didn't accidentally include spaces

### "Phone number must start with + and include country code"
- Format: `+[country code][number]`
- USA example: `+1234567890`
- UK example: `+441234567890`
- Don't include spaces or dashes

### "Gemini API key should start with 'AIza'"
- Make sure you copied the entire key
- The key should be 39+ characters long
- Double-check you got it from https://aistudio.google.com/app/apikey

### "SMS provider API key is required"
- Make sure you created an account with the SMS provider
- Log in to the provider's dashboard
- Find the "API" or "API Key" section
- Copy the key (usually starts with a long string of letters/numbers)

### "Failed to save configuration"
- Check that the application has write permissions
- Make sure your disk isn't full
- Close config.json if it's open in another program
- Try running the application as administrator (if on Windows)

## After Setup

Once you complete the wizard:

### Immediate Next Steps

1. **Verify your settings were saved**
   - The wizard will show a success message
   - Your settings are saved in `config.json`

2. **Create your first Telegram account**
   - Go to Settings → Account Factory tab
   - Click "Create Accounts"
   - Start with just 1 account to test

3. **Let your account warm up**
   - New accounts automatically enter a 3-7 day warmup period
   - This makes them look legitimate to Telegram
   - Don't skip this - it prevents bans!

4. **Configure your AI personality**
   - Go to Settings → Brain & Behavior tab
   - Write a prompt that defines how your bot should respond
   - Example: "You are a helpful assistant who sells web development services"

5. **Test with a friend**
   - Have a friend message your account
   - Verify the bot responds correctly
   - Adjust the brain prompt if needed

### Long-term Best Practices

- **Start small:** 1-2 accounts initially
- **Respect rate limits:** Don't exceed 50 messages/hour at first
- **Quality over quantity:** Good, relevant messages > spam
- **Monitor your accounts:** Check the dashboard regularly
- **Adjust gradually:** Make small changes and observe results

## Security & Privacy

### Important Reminders

✅ **DO:**
- Keep your API keys private
- Store config.json securely
- Use strong passwords for your accounts
- Regularly back up your configuration

❌ **DON'T:**
- Share your API keys with anyone
- Post screenshots showing credentials
- Commit config.json to public repositories
- Use the same API keys across multiple installations

### What's Stored Where

- **config.json** - All your settings (API keys, preferences, etc.)
- **accounts.db** - Information about your Telegram accounts
- **.wizard_complete** - Marker that setup is done
- **config.json.backup** - Automatic backup of your previous config

## Need Help?

### Troubleshooting Resources

1. **Check the logs:**
   - Look in the `logs/` folder
   - Most recent: `telegram_bot.log`

2. **Verify your credentials:**
   - Telegram API: https://my.telegram.org/apps
   - Gemini API: https://aistudio.google.com/app/apikey
   - SMS Provider: Check your provider's dashboard

3. **Test your configuration:**
   - Go to Settings
   - Click "Test Configuration"
   - This validates your API keys

### Still Stuck?

- Re-run the wizard: Delete `.wizard_complete` and restart
- Check the documentation in the `README.md`
- Review the implementation details in `GUIDED_SETUP_IMPLEMENTATION.md`

## Tips for Success

### For Best Results:

1. **Be patient** - Account warmup takes time but prevents bans
2. **Start conservative** - Use low rate limits initially  
3. **Test thoroughly** - Verify everything works before scaling up
4. **Monitor actively** - Check your dashboard daily at first
5. **Adjust gradually** - Make small changes, observe, repeat

### Common Beginner Mistakes to Avoid:

❌ Creating too many accounts at once
❌ Skipping the warmup period
❌ Using aggressive rate limits
❌ Sending generic/spammy messages
❌ Ignoring validation warnings

✅ Start with 1-2 accounts
✅ Let accounts warm up fully
✅ Use conservative rate limits
✅ Send personalized, valuable messages
✅ Pay attention to error messages

## Congratulations!

You've completed the setup wizard. Your bot is now configured and ready to create Telegram accounts. Take it slow, follow best practices, and you'll be successful!

Happy automating! 🚀



