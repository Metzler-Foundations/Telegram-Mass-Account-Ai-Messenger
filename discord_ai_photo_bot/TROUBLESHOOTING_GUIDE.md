# Discord AI Photo Bot - Troubleshooting Guide

## Common Deployment Errors and Fixes

### Error 1: "DISCORD_BOT_TOKEN is required to run the bot"

**Cause:** Environment variable not set in Railway

**Fix:**
1. Go to Railway Dashboard: https://railway.app/project/18b65cb0-f64c-47cc-b5ac-72b63da59c3a
2. Click on "Discord-AI-Photo-Bot" service
3. Go to "Variables" tab
4. Add: `DISCORD_BOT_TOKEN` = `MTQ0OTAyOTc2NTM4MTA5OTUzMA.GELrBH.Vz4P-4f4vuvJrBL9pvbilmDWMhRaLsXzKTXuRs`
5. Click "Redeploy"

### Error 2: "ModuleNotFoundError: No module named 'discord_ai_photo_bot'"

**Cause:** PYTHONPATH not set correctly

**Fix:**
1. In Railway Variables tab, add:
   - `PYTHONPATH` = `/app/src`
2. Redeploy the service

### Error 3: "Invalid token" or "401 Unauthorized"

**Cause:** Discord bot token is invalid or expired

**Fix:**
1. Go to https://discord.com/developers/applications
2. Select your application
3. Go to "Bot" section
4. Click "Reset Token" to generate a new one
5. Copy the new token
6. Update `DISCORD_BOT_TOKEN` in Railway Variables
7. Redeploy

### Error 4: "Guild not found" or "Missing Access"

**Cause:** Bot not invited to server or wrong guild ID

**Fix:**
1. Verify guild ID is correct:
   - In Discord, enable Developer Mode (Settings → Advanced)
   - Right-click your server → Copy Server ID
   - Should be: `1449029765381099530`
2. Ensure bot is invited with admin permissions:
   - Use invite URL: `https://discord.com/api/oauth2/authorize?client_id=1449029765381099530&permissions=8&scope=bot%20applications.commands`
3. Update `DISCORD_GUILD_ID` in Railway if needed

### Error 5: "Replicate API error" or "401 Unauthorized"

**Cause:** Replicate API token invalid or missing

**Fix:**
1. Go to https://replicate.com/account/api-tokens
2. Generate a new API token
3. Update in Railway Variables:
   - `REPLICATE_API_TOKEN` = `r8_R6CZU9ZEfQ5KZyCgRW049GwKi3s0r9w2pmeYa`
   - `REPLICATE_DESTINATION_OWNER` = `oranolio956`
4. Redeploy

### Error 6: "Missing Privileged Gateway Intents"

**Cause:** Required intents not enabled in Discord Developer Portal

**Fix:**
1. Go to https://discord.com/developers/applications
2. Select your application → Bot section
3. Scroll to "Privileged Gateway Intents"
4. Enable ALL three:
   - ✅ PRESENCE INTENT
   - ✅ SERVER MEMBERS INTENT
   - ✅ MESSAGE CONTENT INTENT
5. Save changes
6. Redeploy bot (no Railway changes needed)

### Error 7: Build fails with "VOLUME keyword is banned"

**Cause:** Wrong Dockerfile being used

**Fix:**
1. In Railway service settings, verify:
   - Root Directory: `discord_ai_photo_bot`
   - Builder: DOCKERFILE (not Nixpacks)
2. The correct Dockerfile is in `discord_ai_photo_bot/Dockerfile`
3. Redeploy

### Error 8: "Trial expired" or "Cannot perform mutations"

**Cause:** Railway trial period ended

**Fix:**
1. Go to https://railway.app/account/billing
2. Upgrade to Hobby plan ($5/month)
3. Add payment method
4. Wait a few minutes for activation
5. Then you can set variables and deploy

## Quick Fix Checklist

Run through this checklist to fix most common issues:

- [ ] **Railway Plan Active?** Upgrade if trial expired
- [ ] **Environment Variables Set?** All 6 required variables in Railway
- [ ] **Bot Token Valid?** Test with `python3 test_connections.py`
- [ ] **Bot Invited to Server?** Use the invite URL with admin permissions
- [ ] **Intents Enabled?** All 3 privileged intents in Discord Developer Portal
- [ ] **PYTHONPATH Set?** Must be `/app/src` in Railway
- [ ] **Root Directory Correct?** Must be `discord_ai_photo_bot` in Railway settings

## Complete Environment Variable Setup

Copy these to Railway Variables tab (replace with your actual values):

```bash
# Required
DISCORD_BOT_TOKEN=MTQ0OTAyOTc2NTM4MTA5OTUzMA.GELrBH.Vz4P-4f4vuvJrBL9pvbilmDWMhRaLsXzKTXuRs
DISCORD_GUILD_ID=1449029765381099530
DISCORD_APPLICATION_ID=1449029765381099530
REPLICATE_API_TOKEN=r8_R6CZU9ZEfQ5KZyCgRW049GwKi3s0r9w2pmeYa
REPLICATE_DESTINATION_OWNER=oranolio956
PYTHONPATH=/app/src

# Generate a secure random passphrase for audit logs
AUDIT_KEY_PASSPHRASE=<generate with: openssl rand -hex 32>

# Optional
SENTRY_DSN=<your_sentry_dsn_if_you_have_one>
REPLICATE_TRIGGER_WORD=TOK
```

## Testing Locally Before Deployment

Run these commands to test locally:

```bash
# Set environment variables
export DISCORD_BOT_TOKEN="your_token"
export DISCORD_GUILD_ID="your_guild_id"
export REPLICATE_API_TOKEN="your_replicate_token"
export REPLICATE_DESTINATION_OWNER="your_username"

# Test connections
cd discord_ai_photo_bot
python3 test_connections.py

# Run diagnostics
python3 diagnose_deployment.py

# Test bot locally
python3 -m discord_ai_photo_bot.bot
```

## Viewing Railway Logs

To see what's happening during deployment:

1. Go to Railway Dashboard
2. Click on your service
3. Click "Deployments" tab
4. Click on the latest deployment
5. View "Build Logs" and "Deploy Logs"

Common log patterns to look for:
- ✅ `"Slash commands synced to guild"` - Bot started successfully
- ❌ `"DISCORD_BOT_TOKEN is required"` - Missing environment variable
- ❌ `"ModuleNotFoundError"` - PYTHONPATH issue
- ❌ `"401 Unauthorized"` - Invalid token

## Getting Help

If you're still stuck:

1. **Check Railway Logs:** Look for specific error messages
2. **Run Diagnostics:** `python3 diagnose_deployment.py`
3. **Test Connections:** `python3 test_connections.py`
4. **Verify Variables:** Double-check all environment variables in Railway
5. **Check Discord Developer Portal:** Ensure intents are enabled

## Railway Service Configuration

Verify these settings in Railway:

**Settings Tab:**
- Root Directory: `discord_ai_photo_bot`
- Build Command: (empty - uses Dockerfile)
- Start Command: (empty - uses Dockerfile CMD)
- Builder: DOCKERFILE

**Variables Tab:**
- All 6+ required environment variables set
- No placeholder values like "your_token_here"

**Deployments Tab:**
- Latest deployment should show "Success" status
- Build logs should show successful pip install
- Deploy logs should show bot connecting to Discord

## Next Steps After Fixing

Once the bot is deployed successfully:

1. **Verify Bot Online:** Check Discord server - bot should appear online
2. **Test Commands:** Run `/studio` in #photo-generation channel
3. **Check Guide:** Verify the onboarding guide is posted and pinned
4. **Monitor Logs:** Watch Railway logs for any runtime errors
5. **Test Full Flow:** Try uploading photos and generating a pack

## Support Resources

- Railway Documentation: https://docs.railway.app
- Discord.py Documentation: https://discordpy.readthedocs.io
- Replicate Documentation: https://replicate.com/docs
- Project Repository: https://github.com/Metzler-Foundations/Telegram-Mass-Account-Ai-Messenger