# Discord AI Photo Bot

A Discord bot for photorealistic identity training + photo generation in Discord.

Primary user flow: [`/studio`](discord_ai_photo_bot/src/discord_ai_photo_bot/commands/studio.py:184) (upload reference photos → train LoRA → generate pack → receive ZIP via DM).

This repo is currently **studio-only**:
- Legacy BTC/payment commands are not exposed
- Payments/webhooks are not started

## Quick Setup

### Option 1: Guided Setup (Recommended)

Run the interactive setup wizard:

```bash
cd discord_ai_photo_bot
source venv/bin/activate
python setup_discord.py
```

This will guide you through:
1. Creating a Discord Application
2. Setting up your bot
3. Inviting it to your server
4. Configuring API keys

### Option 2: Manual Setup

1. **Create Discord Application**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" and name it
   - Note your **Application ID**

2. **Create Bot**
   - Go to "Bot" section
   - Click "Add Bot"
   - Enable these Privileged Gateway Intents:
     - ✅ PRESENCE INTENT
     - ✅ SERVER MEMBERS INTENT
     - ✅ MESSAGE CONTENT INTENT
   - Click "Reset Token" and copy your **Bot Token**

3. **Invite Bot to Server**
   
   Use this URL (replace `YOUR_APP_ID`):
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_APP_ID&permissions=8&scope=bot%20applications.commands
   ```

4. **Get Server ID**
   - Enable Developer Mode in Discord (User Settings → Advanced)
   - Right-click your server → "Copy Server ID"

5. **Configure Environment**
   
   Copy `env.sample` to `.env` and fill in your values:
   ```bash
   cp env.sample .env
   nano .env  # or use any editor
   ```

## Running the Bot

From the repo root (recommended `src/` layout invocation):

```bash
cd discord_ai_photo_bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run with src/ on PYTHONPATH
PYTHONPATH=./src python -m discord_ai_photo_bot.bot
```

## Server Management (optional)

A separate CLI exists in [`discord_ai_photo_bot/manage_server.py`](discord_ai_photo_bot/manage_server.py) for server administration.
It’s optional and not required for the `/studio` workflow.

## Bot Commands (for users)

Once running, users can interact with the bot via slash commands:

| Command | Description |
|---------|-------------|
| `/studio` | Premium guided studio session: upload refs → train → generate → DM ZIP |
| `/help` | Show the `/studio` quickstart |

### `/studio` workflow (premium)
1. Run `/studio` inside `#photo-generation`
2. The bot creates a private thread for your session
3. Upload **8–20** photos of the same person (best: 10–20)
4. Click **Finish uploads & start training**
5. When training completes, click **Generate pack (40)**
6. Receive a ZIP via DM

The bot will also auto-post and pin a “How it works” guide in `#photo-generation` on startup (best-effort).

## File Structure

```
discord_ai_photo_bot/
├── .env                      # Your configuration (create from env.sample)
├── env.sample                # Example configuration
├── requirements.txt          # Python dependencies
└── src/
    └── discord_ai_photo_bot/
        ├── bot.py                # Main bot entry point (studio-only)
        ├── config.py             # Configuration loader
        ├── database.py           # SQLite database (training_jobs table)
        ├── ai/
        │   └── generator.py      # Replicate LoRA training + generation
        ├── commands/
        │   ├── studio.py         # Premium /studio flow
        │   └── help.py           # /help quickstart
        └── storage/
            └── discord_storage.py # File delivery (DM ZIP)
```

> Legacy code (payments, server manager, legacy commands) remains in the repo but is not used by the studio-only bot entrypoint.

## Environment Variables

### Required (Studio)
| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ | Your bot token |
| `DISCORD_APPLICATION_ID` | ✅ | Your application ID |
| `DISCORD_GUILD_ID` | ✅ | Your server ID |
| `REPLICATE_API_TOKEN` | ✅ | Replicate API key |
| `REPLICATE_DESTINATION_OWNER` | ✅ | Your Replicate username/org to store trained LoRAs under |

### Optional (Studio)
| Variable | Required | Description |
|----------|----------|-------------|
| `REPLICATE_TRIGGER_WORD` | ❌ | Trigger token used in prompts (default: `TOK`) |
| `REPLICATE_TRAINING_MODEL` | ❌ | Trainer model (default: `ostris/flux-dev-lora-trainer`) |
| `REPLICATE_TRAINING_VERSION` | ❌ | Pin trainer version to avoid upstream breaking changes |
| `REPLICATE_TRAINING_PARAMS_JSON` | ❌ | JSON overrides for training payload |
| `REPLICATE_GENERATION_PARAMS_JSON` | ❌ | JSON overrides for generation payload |
| `DISCORD_AI_BOT_DATA_DIR` | ❌ | Data directory (default: ./data) |

### Deprecated (legacy payments/webhook)
Present in [`discord_ai_photo_bot/env.sample`](discord_ai_photo_bot/env.sample:1) but not used by the studio-only bot:
- `BTC_RECEIVER_ADDRESS`
- `PAYMENT_WEBHOOK_SECRET`
- `PACK_USD_PRICE`
- `PAYMENT_TIMEOUT_SECONDS`
- `ENABLE_WEBHOOK_SERVER`
- `WEBHOOK_PORT`

## Troubleshooting

### Bot not responding to commands
- Make sure the bot is online (green dot)
- Ensure you start it with `PYTHONPATH=./src` (see “Running the Bot”)
- Commands are synced to your guild at startup; Discord clients can cache — try restarting Discord

### `/studio` says to use `#photo-generation`
- Create a text channel named `photo-generation` (exact name) or rename your intended channel.

### OpenCV error: `libGL.so.1`
- On Linux, install: `sudo apt-get update && sudo apt-get install -y libgl1 libglib2.0-0`

### "Missing Access" errors
- Re-invite the bot with Administrator permissions
- Check channel-specific permission overwrites

### "Intents" errors
- Enable all Privileged Gateway Intents in the Developer Portal

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run bot with debug logging
DISCORD_LOG_LEVEL=DEBUG PYTHONPATH=./src python -m discord_ai_photo_bot.bot
```

## License

MIT









