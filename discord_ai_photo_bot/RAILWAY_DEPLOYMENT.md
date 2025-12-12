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
1. A Railway account with an active plan (Hobby or Pro)
2. Your Discord Bot Token
3. Your Discord Guild ID (server ID)
4. Your Replicate API Token
5. Your Replicate username/org

## Required Environment Variables

Set these in Railway's service settings:

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ | Your Discord bot token from Discord Developer Portal |
| `DISCORD_GUILD_ID` | ✅ | Your Discord server ID |
| `REPLICATE_API_TOKEN` | ✅ | Your Replicate API token |
| `REPLICATE_DESTINATION_OWNER` | ✅ | Your Replicate username/org for LoRA storage |
| `PYTHONPATH` | ✅ | Set to `/app/src` for module resolution |
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

## Railway Project Details

- **Project ID:** `18b65cb0-f64c-47cc-b5ac-72b63da59c3a`
- **Environment ID:** `f49e76ed-6e7a-4dfb-80f4-032e27a97dfe`
- **Service ID:** `41225a11-f927-430f-9c78-54c377612321`
- **Dashboard URL:** https://railway.app/project/18b65cb0-f64c-47cc-b5ac-72b63da59c3a