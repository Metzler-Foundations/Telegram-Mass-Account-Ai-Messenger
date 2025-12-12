#!/bin/bash
# Railway Deployment Script for Discord AI Photo Bot
# Run this script on your local machine

set -e

echo "🚀 Discord AI Photo Bot - Railway Deployment"
echo "=============================================="

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Installing..."
    curl -fsSL https://railway.app/install.sh | sh
    export PATH="$HOME/.railway/bin:$PATH"
fi

# Set Railway token
export RAILWAY_TOKEN="03a83adf-4343-431e-9387-d14936b68309"

echo "🔑 Logging into Railway..."
railway login --browserless

echo "📁 Navigating to bot directory..."
cd discord_ai_photo_bot

echo "🔗 Linking to Railway project..."
# This will prompt for project selection if multiple exist
railway link

echo "📝 Setting environment variables..."
railway variables set DISCORD_BOT_TOKEN="your_new_reset_token_here"
railway variables set DISCORD_GUILD_ID="1448262639707754536"
railway variables set REPLICATE_API_TOKEN="your_replicate_token"
railway variables set REPLICATE_DESTINATION_OWNER="your_replicate_username"

echo "🚀 Deploying bot..."
railway up

echo "⏳ Waiting for deployment..."
sleep 30

echo "📊 Checking deployment status..."
railway status

echo "📋 Getting logs..."
railway logs

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "1. Check Railway dashboard for deployment status"
echo "2. Test /studio command in Discord #photo-generation"
echo "3. Monitor logs with: railway logs"
echo ""
echo "🔧 If issues occur:"
echo "- Reset Discord bot token and update RAILWAY_TOKEN"
echo "- Check Railway logs for errors"
echo "- Verify all environment variables are set"