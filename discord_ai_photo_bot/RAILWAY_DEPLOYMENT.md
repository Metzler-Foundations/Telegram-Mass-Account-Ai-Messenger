# Railway Deployment Guide for Discord AI Photo Bot

## Current Deployment Status

**Project:** stunning-learning  
**Service:** Discord-AI-Photo-Bot  
**Root Directory:** discord_ai_photo_bot  
**Repository:** Metzler-Foundations/Telegram-Mass-Account-Ai-Messenger  
**Branch:** main  

### ⚠️ Action Required: Trial Expired

Your Railway trial has expired. The API cannot perform mutations (set variables, trigger deployments) until you upgrade to a paid plan.

**To complete deployment:**

1. **Upgrade your Railway plan:**
   - Go to https://railway.app/account/billing
   - Select Hobby ($5/month) or Pro plan
   - Add payment method

2. **Set environment variables in Railway Dashboard:**
   - Go to https://railway.app/project/18b65cb0-f64c-47cc-b5ac-72b63da59c3a
   - Click on the "Discord-AI-Photo-Bot" service
   - Go to "Variables" tab
   - Add these variables:

   | Variable | Value |
   |----------|-------|
   | `DISCORD_BOT_TOKEN` | Your Discord bot token |
   | `DISCORD_GUILD_ID` | Your Discord server ID |
   | `REPLICATE_API_TOKEN` | Your Replicate API token |
   | `REPLICATE_DESTINATION_OWNER` | Your Replicate username |
   | `PYTHONPATH` | `/app/src` |

3. **Trigger a new deployment:**
   - Option A: Push any commit to the `main` branch
   - Option B: Click "Redeploy" in Railway dashboard
   - Option C: Use Railway CLI: `railway up`

---

## Prerequisites

Before deploying, you need:
1. **Railway account with active plan** (Hobby $5/month or Pro)
2. **Discord Bot Token** from https://discord.com/developers/applications
3. **Discord Guild ID** (right-click server → Copy Server ID)
4. **Replicate API Token** from https://replicate.com/account/api-tokens
5. **Replicate username/org** for LoRA storage
6. **Audit Key Passphrase** (generate a secure random string)

## Complete Setup Checklist

### ✅ Step 1: Railway Account Setup
- [ ] Upgrade to Hobby ($5/month) or Pro plan
- [ ] Verify billing information is complete
- [ ] Confirm project access: https://railway.app/project/18b65cb0-f64c-47cc-b5ac-72b63da59c3a

### ✅ Step 2: Discord Bot Configuration
- [ ] Create application at https://discord.com/developers/applications
- [ ] Enable Privileged Gateway Intents:
  - [ ] PRESENCE INTENT
  - [ ] SERVER MEMBERS INTENT
  - [ ] MESSAGE CONTENT INTENT
- [ ] Copy Bot Token
- [ ] Copy Application ID
- [ ] Generate invite URL with admin permissions

### ✅ Step 3: Replicate API Setup
- [ ] Sign up at https://replicate.com
- [ ] Generate API token at https://replicate.com/account/api-tokens
- [ ] Note your username/org for LoRA storage
- [ ] Ensure you have credits for training

### ✅ Step 4: Environment Variables
Set these in Railway service Variables tab:

```bash
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id_here
REPLICATE_API_TOKEN=your_replicate_token_here
REPLICATE_DESTINATION_OWNER=your_replicate_username
PYTHONPATH=/app/src
AUDIT_KEY_PASSPHRASE=your_secure_random_passphrase_here
```

### ✅ Step 5: Deploy and Verify
- [ ] Push latest code to GitHub main branch
- [ ] Wait for Railway auto-deployment
- [ ] Check Railway logs for successful startup
- [ ] Verify bot appears online in Discord
- [ ] Test `/studio` command in #photo-generation
- [ ] Confirm enhanced onboarding guide is posted

## Required Environment Variables

Set these in Railway's service settings:

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ | Your Discord bot token from Discord Developer Portal |
| `DISCORD_GUILD_ID` | ✅ | Your Discord server ID (right-click server → Copy Server ID) |
| `REPLICATE_API_TOKEN` | ✅ | Your Replicate API token from https://replicate.com/account/api-tokens |
| `REPLICATE_DESTINATION_OWNER` | ✅ | Your Replicate username/org for LoRA storage |
| `PYTHONPATH` | ✅ | Set to `/app/src` for module resolution |
| `AUDIT_KEY_PASSPHRASE` | ✅ | Random passphrase for audit log encryption (generate a secure one) |
| `REPLICATE_TRIGGER_WORD` | ❌ | Trigger word for prompts (default: TOK) |
| `REPLICATE_TRAINING_MODEL` | ❌ | Training model (default: ostris/flux-dev-lora-trainer) |
| `DISCORD_AI_BOT_DATA_DIR` | ❌ | Data directory (default: ./data) |
| `SENTRY_DSN` | ❌ | Sentry DSN for error tracking |

## Deployment Methods

### Method 1: Deploy via Railway Dashboard (Recommended)

1. Go to https://railway.app/project/18b65cb0-f64c-47cc-b5ac-72b63da59c3a
2. Click on the "Discord-AI-Photo-Bot" service
3. Go to "Variables" tab and add the required environment variables
4. Go to "Settings" tab and verify:
   - Root Directory: `discord_ai_photo_bot`
   - Build Command: (leave empty, uses Dockerfile)
   - Start Command: (leave empty, uses Dockerfile CMD)
5. Click "Redeploy" or push to GitHub to trigger deployment

### Method 2: Deploy via Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Link to your project
railway link

# Set environment variables
railway variables set DISCORD_BOT_TOKEN=your_token_here
railway variables set DISCORD_GUILD_ID=your_guild_id_here
railway variables set REPLICATE_API_TOKEN=your_replicate_token_here
railway variables set REPLICATE_DESTINATION_OWNER=your_replicate_username
railway variables set PYTHONPATH=/app/src

# Deploy
railway up
```

### Method 3: Deploy via Git Push

Since the service is connected to GitHub, any push to the `main` branch will trigger a deployment:

```bash
git add .
git commit -m "Trigger Railway deployment"
git push origin main
```

## Build Configuration

The bot uses these configuration files:
- `railway.json` - Railway-specific settings
- `Procfile` - Process definition
- `nixpacks.toml` - Build configuration
- `Dockerfile` - Container definition (primary)

Railway will automatically detect and use the Dockerfile in the `discord_ai_photo_bot` directory.

## Troubleshooting

### Build fails with "VOLUME keyword is banned"
- The root Dockerfile has been updated to remove VOLUME
- Make sure the service root directory is set to `discord_ai_photo_bot`

### Bot not starting
- Check that `DISCORD_BOT_TOKEN` is set correctly
- Verify the token has the required permissions
- Check Railway logs for error messages
- Ensure `PYTHONPATH` is set to `/app/src`

### Module not found errors
- Set `PYTHONPATH=/app/src` in environment variables
- The bot module is at `src/discord_ai_photo_bot/bot.py`

### Commands not appearing
- The bot syncs commands on startup
- Wait up to 1 hour for global command sync
- Guild-specific commands should appear immediately

### Training/Generation not working
- Verify `REPLICATE_API_TOKEN` is valid
- Check `REPLICATE_DESTINATION_OWNER` matches your Replicate account
- Ensure you have credits in your Replicate account

## Discord Bot Setup

1. Go to https://discord.com/developers/applications
2. Create a new application
3. Go to "Bot" section and create a bot
4. Enable these Privileged Gateway Intents:
   - PRESENCE INTENT
   - SERVER MEMBERS INTENT
   - MESSAGE CONTENT INTENT
5. Copy the bot token
6. Use this invite URL (replace YOUR_APP_ID):
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_APP_ID&permissions=8&scope=bot%20applications.commands
   ```

## File Structure

```
discord_ai_photo_bot/
├── railway.json          # Railway configuration
├── Procfile              # Process definition
├── nixpacks.toml         # Build settings
├── Dockerfile            # Container definition
├── requirements.txt      # Python dependencies
└── src/
    └── discord_ai_photo_bot/
        ├── bot.py        # Main entry point
        ├── config.py     # Configuration loader
        └── ...
```

## Automated Setup Script

Run this script to set up Railway deployment automatically:

```bash
#!/bin/bash
# Railway Deployment Setup Script

echo "🚀 Setting up Discord AI Photo Bot on Railway..."

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Installing Railway CLI..."
    npm install -g @railway/cli
fi

# Login to Railway
echo "Logging into Railway..."
railway login

# Link to project
echo "Linking to project..."
railway link --project 18b65cb0-f64c-47cc-b5ac-72b63da59c3a

# Set environment variables
echo "Setting environment variables..."
railway variables set DISCORD_BOT_TOKEN=$DISCORD_BOT_TOKEN
railway variables set DISCORD_GUILD_ID=$DISCORD_GUILD_ID
railway variables set REPLICATE_API_TOKEN=$REPLICATE_API_TOKEN
railway variables set REPLICATE_DESTINATION_OWNER=$REPLICATE_DESTINATION_OWNER
railway variables set PYTHONPATH=/app/src
railway variables set AUDIT_KEY_PASSPHRASE=$(openssl rand -hex 32)

echo "✅ Setup complete! Run 'railway up' to deploy."
```

## Environment Variables Reference

### Required Variables
| Variable | Example | Description |
|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | `MTE4...` | Bot token from Discord Developer Portal |
| `DISCORD_GUILD_ID` | `1448262639707754536` | Server ID (right-click server → Copy ID) |
| `REPLICATE_API_TOKEN` | `r8_...` | API token from Replicate |
| `REPLICATE_DESTINATION_OWNER` | `yourusername` | Your Replicate username |
| `PYTHONPATH` | `/app/src` | Module resolution path |
| `AUDIT_KEY_PASSPHRASE` | `a1b2c3...` | Secure random string for encryption |

### Optional Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `REPLICATE_TRIGGER_WORD` | `TOK` | Word to trigger AI generation |
| `REPLICATE_TRAINING_MODEL` | `ostris/flux-dev-lora-trainer` | Training model |
| `DISCORD_AI_BOT_DATA_DIR` | `./data` | SQLite database location |
| `SENTRY_DSN` | `null` | Error tracking DSN |

## Railway Project Details

- **Project ID:** `18b65cb0-f64c-47cc-b5ac-72b63da59c3a`
- **Environment ID:** `f49e76ed-6e7a-4dfb-80f4-032e27a97dfe`
- **Service ID:** `41225a11-f927-430f-9c78-54c377612321`
- **Dashboard URL:** https://railway.app/project/18b65cb0-f64c-47cc-b5ac-72b63da59c3a