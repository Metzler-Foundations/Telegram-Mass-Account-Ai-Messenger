#!/bin/bash

# 🚀 Discord AI Photo Bot - Complete Railway Deployment Script
# This script ensures FULL setup with no gaps

set -e

echo "🎨 Discord AI Photo Bot - Complete Railway Setup"
echo "================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${RED}❌ Railway CLI not found${NC}"
    echo "Install Railway CLI:"
    echo "npm install -g @railway/cli"
    echo "railway login"
    exit 1
fi

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo -e "${RED}❌ Not logged in to Railway${NC}"
    echo "Run: railway login"
    exit 1
fi

echo -e "${BLUE}🔍 Checking Railway project access...${NC}"

# Check project access
if ! railway link --project 18b65cb0-f64c-47cc-b5ac-72b63da59c3a &> /dev/null; then
    echo -e "${RED}❌ Cannot access Railway project${NC}"
    echo "Project ID: 18b65cb0-f64c-47cc-b5ac-72b63da59c3a"
    echo "Make sure you have access to this project"
    exit 1
fi

echo -e "${GREEN}✅ Railway project linked${NC}"

# Function to set environment variable
set_env_var() {
    local var_name=$1
    local var_value=$2
    local description=$3

    echo -e "${BLUE}🔧 Setting ${var_name}...${NC}"

    if [ -z "$var_value" ]; then
        echo -e "${YELLOW}⚠️  ${var_name} not provided - ${description}${NC}"
        read -p "Enter ${var_name}: " var_value
        if [ -z "$var_value" ]; then
            echo -e "${RED}❌ ${var_name} is required${NC}"
            exit 1
        fi
    fi

    if railway variables set "$var_name=$var_value" 2>/dev/null; then
        echo -e "${GREEN}✅ ${var_name} set successfully${NC}"
    else
        echo -e "${RED}❌ Failed to set ${var_name}${NC}"
        exit 1
    fi
}

echo -e "${BLUE}🔧 Setting up environment variables...${NC}"

# Required environment variables
set_env_var "DISCORD_BOT_TOKEN" "$DISCORD_BOT_TOKEN" "Get from https://discord.com/developers/applications"
set_env_var "DISCORD_GUILD_ID" "$DISCORD_GUILD_ID" "Right-click server → Copy Server ID"
set_env_var "REPLICATE_API_TOKEN" "$REPLICATE_API_TOKEN" "Get from https://replicate.com/account/api-tokens"
set_env_var "REPLICATE_DESTINATION_OWNER" "$REPLICATE_DESTINATION_OWNER" "Your Replicate username/org"

# Always-required variables
railway variables set "PYTHONPATH=/app/src"
echo -e "${GREEN}✅ PYTHONPATH set to /app/src${NC}"

# Optional variables with defaults
echo -e "${BLUE}🔧 Setting optional variables with defaults...${NC}"

railway variables set "REPLICATE_TRIGGER_WORD=TOK"
railway variables set "REPLICATE_TRAINING_MODEL=ostris/flux-dev-lora-trainer"
railway variables set "DISCORD_AI_BOT_DATA_DIR=./data"

echo -e "${GREEN}✅ Optional variables set${NC}"

# Verify service configuration
echo -e "${BLUE}🔍 Verifying service configuration...${NC}"

# Check if service exists and is properly configured
if railway status | grep -q "Discord-AI-Photo-Bot"; then
    echo -e "${GREEN}✅ Discord-AI-Photo-Bot service found${NC}"
else
    echo -e "${RED}❌ Discord-AI-Photo-Bot service not found${NC}"
    echo "Make sure the service name matches exactly"
    exit 1
fi

# Trigger deployment
echo -e "${BLUE}🚀 Triggering deployment...${NC}"

if railway up; then
    echo -e "${GREEN}✅ Deployment triggered successfully${NC}"
else
    echo -e "${RED}❌ Deployment failed${NC}"
    echo "Check Railway dashboard for error details"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 DEPLOYMENT COMPLETE!${NC}"
echo ""
echo -e "${BLUE}📋 Next Steps:${NC}"
echo "1. Wait for deployment to complete (check Railway dashboard)"
echo "2. Invite bot to Discord server:"
echo "   https://discord.com/api/oauth2/authorize?client_id=YOUR_APP_ID&permissions=8&scope=bot%20applications.commands"
echo "3. Test commands: /help, /studio"
echo ""
echo -e "${BLUE}📖 Full Setup Guide:${NC}"
echo "See COMPREHENSIVE_SETUP.md for detailed instructions"
echo ""
echo -e "${GREEN}🚀 Your Discord AI Photo Bot is now fully configured!${NC}"