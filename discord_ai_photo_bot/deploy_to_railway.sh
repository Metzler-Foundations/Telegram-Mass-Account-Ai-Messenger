#!/bin/bash
# Railway Deployment Script for Discord AI Photo Bot
# Usage: ./deploy_to_railway.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Discord AI Photo Bot - Railway Deployment ===${NC}"

# Check if RAILWAY_TOKEN is set
if [ -z "$RAILWAY_TOKEN" ]; then
    echo -e "${RED}Error: RAILWAY_TOKEN environment variable is not set${NC}"
    echo "Please set it with: export RAILWAY_TOKEN=your_token_here"
    exit 1
fi

# Configuration
PROJECT_ID="${RAILWAY_PROJECT_ID:-18b65cb0-f64c-47cc-b5ac-72b63da59c3a}"
ENVIRONMENT_ID="${RAILWAY_ENVIRONMENT_ID:-f49e76ed-6e7a-4dfb-80f4-032e27a97dfe}"
API_URL="https://backboard.railway.app/graphql/v2"

# Function to make GraphQL requests
graphql_request() {
    local query="$1"
    curl -s -H "Authorization: Bearer $RAILWAY_TOKEN" \
         -H "Content-Type: application/json" \
         -X POST "$API_URL" \
         -d "{\"query\": \"$query\"}"
}

echo -e "${YELLOW}Checking Railway API connection...${NC}"

# Test API connection
RESPONSE=$(graphql_request "query { projects { edges { node { id name } } } }")
if echo "$RESPONSE" | grep -q "error"; then
    echo -e "${RED}Error connecting to Railway API:${NC}"
    echo "$RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Connected to Railway API${NC}"

# Check if service exists
echo -e "${YELLOW}Checking for existing Discord bot service...${NC}"

SERVICE_CHECK=$(graphql_request "query { project(id: \\\"$PROJECT_ID\\\") { services { edges { node { id name } } } } }")
DISCORD_SERVICE_ID=$(echo "$SERVICE_CHECK" | grep -o '"id":"[^"]*","name":"Discord-AI-Photo-Bot"' | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

if [ -z "$DISCORD_SERVICE_ID" ]; then
    echo -e "${YELLOW}Creating new Discord bot service...${NC}"
    
    CREATE_RESPONSE=$(graphql_request "mutation { serviceCreate(input: { projectId: \\\"$PROJECT_ID\\\", name: \\\"Discord-AI-Photo-Bot\\\" }) { id name } }")
    
    if echo "$CREATE_RESPONSE" | grep -q "error"; then
        echo -e "${RED}Error creating service:${NC}"
        echo "$CREATE_RESPONSE"
        exit 1
    fi
    
    DISCORD_SERVICE_ID=$(echo "$CREATE_RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    echo -e "${GREEN}✓ Created service with ID: $DISCORD_SERVICE_ID${NC}"
else
    echo -e "${GREEN}✓ Found existing service: $DISCORD_SERVICE_ID${NC}"
fi

# Set environment variables
echo -e "${YELLOW}Setting environment variables...${NC}"

set_variable() {
    local name="$1"
    local value="$2"
    
    if [ -n "$value" ]; then
        graphql_request "mutation { variableUpsert(input: { projectId: \\\"$PROJECT_ID\\\", environmentId: \\\"$ENVIRONMENT_ID\\\", serviceId: \\\"$DISCORD_SERVICE_ID\\\", name: \\\"$name\\\", value: \\\"$value\\\" }) }" > /dev/null
        echo -e "  ${GREEN}✓${NC} Set $name"
    else
        echo -e "  ${YELLOW}⚠${NC} Skipped $name (not set)"
    fi
}

# Required variables
set_variable "DISCORD_BOT_TOKEN" "$DISCORD_BOT_TOKEN"
set_variable "DISCORD_GUILD_ID" "$DISCORD_GUILD_ID"
set_variable "REPLICATE_API_TOKEN" "$REPLICATE_API_TOKEN"
set_variable "REPLICATE_DESTINATION_OWNER" "$REPLICATE_DESTINATION_OWNER"

# Optional variables
set_variable "REPLICATE_TRIGGER_WORD" "${REPLICATE_TRIGGER_WORD:-TOK}"
set_variable "REPLICATE_TRAINING_MODEL" "${REPLICATE_TRAINING_MODEL:-ostris/flux-dev-lora-trainer}"
set_variable "SENTRY_DSN" "$SENTRY_DSN"

echo -e "${GREEN}✓ Environment variables configured${NC}"

# Trigger deployment
echo -e "${YELLOW}Triggering deployment...${NC}"

# Note: Railway typically auto-deploys when connected to a GitHub repo
# For manual deployment, you would need to use the Railway CLI or push to the connected repo

echo -e "${GREEN}=== Deployment Configuration Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Connect your GitHub repository to the service in Railway dashboard"
echo "2. Set the root directory to 'discord_ai_photo_bot'"
echo "3. Push changes to trigger a deployment"
echo ""
echo "Or use Railway CLI:"
echo "  cd discord_ai_photo_bot"
echo "  railway link"
echo "  railway up"