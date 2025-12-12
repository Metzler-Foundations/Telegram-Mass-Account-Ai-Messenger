# 🚀 Complete Discord AI Photo Bot Setup Guide

## ✅ **Pre-Deployment Checklist**

### **1. Railway Account Setup**
- [ ] Upgrade to Hobby ($5/month) or Pro plan
- [ ] Verify project access: https://railway.app/project/18b65cb0-f64c-47cc-b5ac-72b63da59c3a

### **2. Discord Bot Configuration**
- [ ] Create Discord application at https://discord.com/developers/applications
- [ ] Enable these bot permissions:
  - `PRESENCE INTENT`
  - `SERVER MEMBERS INTENT`
  - `MESSAGE CONTENT INTENT`
- [ ] Generate bot token
- [ ] Get server (guild) ID by right-clicking server → "Copy Server ID"

### **3. Replicate AI Setup**
- [ ] Create account at https://replicate.com
- [ ] Generate API token at https://replicate.com/account/api-tokens
- [ ] Add credits to account (minimum $10 recommended)
- [ ] Note your Replicate username/org name

### **4. Environment Variables for Railway**
Set these in Railway dashboard under "Discord-AI-Photo-Bot" → "Variables":

```bash
# Required
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_GUILD_ID=your_discord_server_id_here
REPLICATE_API_TOKEN=your_replicate_api_token_here
REPLICATE_DESTINATION_OWNER=your_replicate_username
PYTHONPATH=/app/src

# Optional (with defaults)
REPLICATE_TRIGGER_WORD=TOK
REPLICATE_TRAINING_MODEL=ostris/flux-dev-lora-trainer
DISCORD_AI_BOT_DATA_DIR=./data
SENTRY_DSN=your_sentry_dsn_here
```

## 🔧 **Deployment Steps**

### **🚀 Option A: Automated Deployment (Recommended)**

1. **Verify your local setup:**
   ```bash
   cd discord_ai_photo_bot
   python verify_deployment.py
   ```

2. **Set your API keys as environment variables:**
   ```bash
   export DISCORD_BOT_TOKEN="your_discord_bot_token_here"
   export DISCORD_GUILD_ID="your_discord_server_id_here"
   export REPLICATE_API_TOKEN="your_replicate_api_token_here"
   export REPLICATE_DESTINATION_OWNER="your_replicate_username"
   ```

3. **Run automated deployment:**
   ```bash
   ./deploy_to_railway.sh
   ```

### **🔧 Option B: Manual Deployment**

1. **Verify local setup:**
   ```bash
   cd discord_ai_photo_bot
   python verify_deployment.py
   ```

2. **Set Environment Variables Manually:**
   - Go to Railway dashboard
   - Select "Discord-AI-Photo-Bot" service
   - Go to "Variables" tab
   - Add all required variables listed above

3. **Verify Service Configuration:**
   In Railway service settings:
   - **Root Directory:** `discord_ai_photo_bot`
   - **Build Command:** (leave empty - uses Dockerfile)
   - **Start Command:** (leave empty - uses Dockerfile CMD)

4. **Deploy:**
   - Push any commit to trigger deployment, or
   - Click "Redeploy" in Railway dashboard

### **Step 4: Verify Bot Startup**
Check Railway logs for:
```
INFO: Slash commands synced to guild XXXXXXXX
INFO: Slash commands synced globally
```

### **Step 5: Test Bot Functionality**
1. **Invite bot to server** using this URL (replace YOUR_APP_ID):
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_APP_ID&permissions=8&scope=bot%20applications.commands
   ```

2. **Test commands:**
   - `/help` - Should show enhanced help
   - `/studio` - Should create session in #photo-generation

## 📋 **Complete Environment Variables Reference**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ | - | Discord bot token |
| `DISCORD_GUILD_ID` | ✅ | - | Discord server ID |
| `REPLICATE_API_TOKEN` | ✅ | - | Replicate API token |
| `REPLICATE_DESTINATION_OWNER` | ✅ | - | Your Replicate username/org |
| `PYTHONPATH` | ✅ | - | Set to `/app/src` |
| `REPLICATE_TRIGGER_WORD` | ❌ | `TOK` | Trigger word for prompts |
| `REPLICATE_TRAINING_MODEL` | ❌ | `ostris/flux-dev-lora-trainer` | Training model |
| `DISCORD_AI_BOT_DATA_DIR` | ❌ | `./data` | Data directory |
| `SENTRY_DSN` | ❌ | - | Error tracking |

## 🐛 **Troubleshooting**

### **Bot Not Starting**
```bash
# Check Railway logs
railway logs

# Common issues:
- Missing DISCORD_BOT_TOKEN
- Invalid bot token
- Missing PYTHONPATH=/app/src
- Bot lacks required Discord permissions
```

### **Commands Not Appearing**
- Guild commands sync immediately
- Global commands take up to 1 hour
- Check bot has `applications.commands` scope

### **Training/Generation Failing**
```bash
# Check Replicate setup:
- Valid API token
- Sufficient credits
- Correct destination owner
- Training model accessible
```

### **Database Issues**
- SQLite database creates automatically
- Session recovery requires database persistence
- Check Railway volume mounting if needed

## 🎯 **Post-Deployment Verification**

### **Immediate Checks:**
- [ ] Bot appears online in Discord
- [ ] `/help` command works
- [ ] `/studio` creates session thread
- [ ] Photo upload works
- [ ] Training starts (check Replicate dashboard)

### **Full Flow Test:**
1. [ ] Run `/studio` in #photo-generation
2. [ ] Upload 5-15 photos
3. [ ] Click "Finish uploads & start training"
4. [ ] See progress updates (0%, 25%, 50%, 75%, 100%)
5. [ ] Training completes successfully
6. [ ] Click "Generate pack (40)"
7. [ ] Receive ZIP via DM

### **UX Features to Verify:**
- [ ] Enhanced onboarding guide pinned
- [ ] Progress tracking during training
- [ ] Contextual help buttons
- [ ] Session recovery after restart
- [ ] Better error messages
- [ ] Usage statistics display

## 🚀 **Production Optimization**

### **Monitoring:**
- Set up Sentry DSN for error tracking
- Monitor Railway logs regularly
- Check Replicate usage/credits

### **Performance:**
- Training typically takes 6-10 minutes
- Generation takes 30-60 seconds per image
- Monitor Railway resource usage

### **Backup:**
- Database persists in Railway volume
- Session data recovers automatically
- Consider periodic database exports

## 📞 **Support**

If issues persist:
1. Check Railway deployment logs
2. Verify all environment variables
3. Test Replicate API access
4. Check Discord bot permissions
5. Review this setup guide completely

**All components are now fully configured for production deployment!** 🎉