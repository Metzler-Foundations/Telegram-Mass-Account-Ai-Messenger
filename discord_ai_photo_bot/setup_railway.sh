#!/bin/bash
# Railway Deployment Setup Script for Discord AI Photo Bot
# This script helps set up the Railway deployment with all required environment variables

set -e

echo "🚀 Discord AI Photo Bot - Railway Setup Script"
echo "=============================================="

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Installing..."
    npm install -g @railway/cli
    echo "✅ Railway CLI installed"
fi

# Login to Railway
echo "🔐 Logging into Railway..."
railway login

# Link to project
echo "🔗 Linking to project..."
railway link --project 18b65cb0-f64c-47cc-b5ac-72b63da59c3a

# Function to set environment variable
set_var() {
    local var_name=$1
    local prompt_text=$2
    local current_value=$(railway variables get $var_name 2>/dev/null || echo "")

    if [ -n "$current_value" ]; then
        echo "ℹ️  $var_name is already set"
    else
        echo "📝 $prompt_text"
        read -p "Enter $var_name: " var_value
        if [ -n "$var_value" ]; then
            railway variables set $var_name="$var_value"
            echo "✅ Set $var_name"
        else
            echo "⚠️  Skipped $var_name"
        fi
    fi
}

echo ""
echo "🔧 Setting up environment variables..."
echo "====================================="

# Required variables
set_var "DISCORD_BOT_TOKEN" "Get this from https://discord.com/developers/applications"
set_var "DISCORD_GUILD_ID" "Right-click your Discord server → Copy Server ID"
set_var "REPLICATE_API_TOKEN" "Get this from https://replicate.com/account/api-tokens"
set_var "REPLICATE_DESTINATION_OWNER" "Your Replicate username/org"

# Auto-set variables
echo "🔧 Setting automatic variables..."
railway variables set PYTHONPATH=/app/src
railway variables set AUDIT_KEY_PASSPHRASE=$(openssl rand -hex 32)
echo "✅ Set PYTHONPATH and AUDIT_KEY_PASSPHRASE"

echo ""
echo "🎉 Setup complete!"
echo "=================="
echo "Next steps:"
echo "1. Push your code changes to GitHub main branch"
echo "2. Railway will auto-deploy the updated bot"
echo "3. Check Railway logs to ensure successful startup"
echo "4. Test the /studio command in your Discord server"
echo ""
echo "📚 Useful links:"
echo "- Railway Dashboard: https://railway.app/project/18b65cb0-f64c-47cc-b5ac-72b63da59c3a"
echo "- Discord Developer Portal: https://discord.com/developers/applications"
echo "- Replicate API Tokens: https://replicate.com/account/api-tokens"