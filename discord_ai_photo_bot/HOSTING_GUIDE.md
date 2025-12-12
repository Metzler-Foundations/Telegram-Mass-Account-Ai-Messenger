# Free 24/7 Discord Bot Hosting Guide

This guide covers free hosting options for the Discord AI Photo Bot.

## Recommended: Railway.app (Best Free Option)

**Railway** offers:
- ✅ 500 hours/month free (enough for ~20 days 24/7)
- ✅ Easy GitHub deployment
- ✅ Environment variables support
- ✅ Auto-restart on failure
- ✅ Logs and monitoring

### One-Click Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/discord-bot?referralCode=)

### Manual Railway Setup

1. **Sign up at [railway.app](https://railway.app)** (use GitHub login)

2. **Create New Project** → "Deploy from GitHub repo"

3. **Select your repository**: `Metzler-Foundations/Telegram-Mass-Account-Ai-Messenger`

4. **Set Root Directory**: `discord_ai_photo_bot`

5. **Add Environment Variables** (in Railway dashboard):
   ```
   DISCORD_BOT_TOKEN=your_bot_token_here
   DISCORD_GUILD_ID=1448262639707754536
   REPLICATE_API_TOKEN=your_replicate_token
   REPLICATE_DESTINATION_OWNER=your_replicate_username
   ```

6. **Deploy** - Railway will auto-detect Python and start the bot

**Note:** Railway handles persistent storage through their volumes system, not Docker VOLUME instructions. The bot stores data in the container filesystem.

---

## Alternative: Render.com (Free Tier)

**Render** offers:
- ✅ Free tier for background workers
- ✅ Auto-deploy from GitHub
- ⚠️ Spins down after 15 min inactivity (not ideal for bots)

### Render Setup

1. Sign up at [render.com](https://render.com)
2. New → Background Worker
3. Connect GitHub repo
4. Set:
   - **Root Directory**: `discord_ai_photo_bot`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `PYTHONPATH=./src python -m discord_ai_photo_bot.bot`
5. Add environment variables
6. Deploy

---

## Alternative: Fly.io (Free Tier)

**Fly.io** offers:
- ✅ 3 shared-cpu VMs free
- ✅ 24/7 uptime
- ✅ Good for Discord bots

### Fly.io Setup

1. Install flyctl: `curl -L https://fly.io/install.sh | sh`
2. Login: `flyctl auth login`
3. Create app:
   ```bash
   cd discord_ai_photo_bot
   flyctl launch --no-deploy
   ```
4. Set secrets:
   ```bash
   flyctl secrets set DISCORD_BOT_TOKEN=your_token
   flyctl secrets set DISCORD_GUILD_ID=1448262639707754536
   flyctl secrets set REPLICATE_API_TOKEN=your_token
   flyctl secrets set REPLICATE_DESTINATION_OWNER=your_username
   ```
5. Deploy: `flyctl deploy`

---

## Alternative: Replit (Free with Limitations)

**Replit** offers:
- ✅ Free tier available
- ⚠️ Sleeps after inactivity
- ⚠️ Needs "Always On" (paid) for 24/7

### Replit Setup

1. Go to [replit.com](https://replit.com)
2. Import from GitHub
3. Set environment variables in Secrets tab
4. Run the bot

---

## Environment Variables Required

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ | Your Discord bot token |
| `DISCORD_GUILD_ID` | ✅ | Your server ID: `1448262639707754536` |
| `REPLICATE_API_TOKEN` | ✅ | For AI image generation |
| `REPLICATE_DESTINATION_OWNER` | ✅ | Your Replicate username |
| `REPLICATE_TRIGGER_WORD` | ❌ | Default: `TOK` |

---

## Troubleshooting

### Bot not starting
- Check logs in hosting dashboard
- Verify all required env vars are set
- Ensure bot token is valid (reset if needed)

### Commands not showing
- Bot syncs commands on startup
- Wait 1-2 minutes after deploy
- Restart Discord client

### Out of free hours (Railway)
- Upgrade to paid ($5/month) or
- Use multiple accounts (not recommended) or
- Switch to Fly.io

---

## Recommended Setup for 24/7 Free

**Best combination for truly free 24/7:**

1. **Primary**: Railway.app (500 hrs/month)
2. **Backup**: Fly.io (when Railway hours run out)

Or just use **Fly.io** alone - it's truly free 24/7 with their free tier.