# Discord AI Photo Bot - Manual Railway Deployment Steps

Since the Railway API is still showing trial expiration (billing changes can take a few minutes to propagate), here are the manual steps to complete the deployment:

## Step 1: Access Your Railway Project

1. Go to https://railway.app
2. Log in to your account
3. Click on the project **"stunning-learning"**
4. You should see the service **"Discord-AI-Photo-Bot"**

## Step 2: Configure the Service Source

The service needs to be connected to your GitHub repository:

1. Click on the **"Discord-AI-Photo-Bot"** service
2. Click **"Settings"** tab
3. Under **"Source"**, click **"Connect Repo"**
4. Select your GitHub repository containing the Discord bot code
5. Set **Root Directory** to: `discord_ai_photo_bot`
6. Set **Branch** to: `main` (or your default branch)

## Step 3: Add Environment Variables

1. Click on the **"Variables"** tab
2. Add the following variables by clicking **"+ New Variable"** for each:

### Required Variables:
| Variable | Value |
|----------|-------|
| `DISCORD_BOT_TOKEN` | Your Discord bot token |
| `DISCORD_GUILD_ID` | Your Discord server ID |
| `REPLICATE_API_TOKEN` | Your Replicate API token |
| `REPLICATE_DESTINATION_OWNER` | Your Replicate username |

### Optional Variables (with defaults):
| Variable | Value |
|----------|-------|
| `REPLICATE_TRIGGER_WORD` | `TOK` |
| `REPLICATE_TRAINING_MODEL` | `ostris/flux-dev-lora-trainer` |
| `PYTHONPATH` | `/app/src` |
| `DISCORD_AI_BOT_DATA_DIR` | `/app/data` |

## Step 4: Configure Build Settings

1. Click on the **"Settings"** tab
2. Under **"Build"**:
   - Builder: **Dockerfile** (should auto-detect)
   - Dockerfile Path: `Dockerfile`
3. Under **"Deploy"**:
   - Start Command: Leave empty (Dockerfile handles this)
   - Restart Policy: **On Failure**

## Step 5: Deploy

1. Click **"Deploy"** button (or it may auto-deploy after connecting repo)
2. Watch the build logs for any errors
3. Once deployed, check the **"Logs"** tab to verify the bot is running

## Step 6: Verify Bot is Online

1. Go to your Discord server
2. Check if the bot appears online
3. Try the `/studio` command in the `#photo-generation` channel
4. The bot should respond and create a private thread

## Troubleshooting

### Build Fails
- Check that `requirements.txt` exists in `discord_ai_photo_bot/`
- Verify `Dockerfile` is correct
- Check build logs for specific errors

### Bot Not Connecting
- Verify `DISCORD_BOT_TOKEN` is correct
- Ensure bot has proper intents enabled in Discord Developer Portal:
  - ✅ MESSAGE CONTENT INTENT
  - ✅ SERVER MEMBERS INTENT
  - ✅ PRESENCE INTENT

### Commands Not Showing
- Commands sync to your guild on startup
- May take up to 1 hour for global sync
- Check logs for "Slash commands synced" message

### "Missing Access" Errors
- Re-invite bot with Administrator permissions:
  ```
  https://discord.com/api/oauth2/authorize?client_id=YOUR_APP_ID&permissions=8&scope=bot%20applications.commands
  ```

## Quick Reference

- **Railway Project URL**: https://railway.app/project/18b65cb0-f64c-47cc-b5ac-72b63da59c3a
- **Service ID**: 41225a11-f927-430f-9c78-54c377612321
- **Environment**: production

## Files Created for Railway

The following files have been created in `discord_ai_photo_bot/`:

1. `railway.json` - Railway configuration
2. `Procfile` - Process declaration
3. `nixpacks.toml` - Nixpacks build config
4. `Dockerfile` - Docker build instructions
5. `deploy_to_railway.sh` - Deployment script
6. `RAILWAY_DEPLOYMENT.md` - Full deployment guide
