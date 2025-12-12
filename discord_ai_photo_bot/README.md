# Discord AI Photo Bot

A Discord bot for generating AI photo packs with Bitcoin payments.

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

```bash
cd discord_ai_photo_bot
source venv/bin/activate
python -m discord_ai_photo_bot.bot
```

## Server Management

Use the CLI tool to manage your Discord server:

```bash
# Show server info
python manage_server.py info

# List channels
python manage_server.py channels

# List roles
python manage_server.py roles

# Create a text channel
python manage_server.py create-channel announcements --category "📢 Information" --topic "Important updates"

# Create a voice channel
python manage_server.py create-voice "General Voice" --category "🔊 Voice"

# Create a category
python manage_server.py create-category "💬 Chat"

# Create a role
python manage_server.py create-role "VIP" --color "#FFD700" --hoist

# Send a message
python manage_server.py send general "Hello, world!"

# Set up standard server structure
python manage_server.py setup-standard

# Export server structure
python manage_server.py export --output my_server.json
```

### Available Commands

| Command | Description |
|---------|-------------|
| `info` | Show server information |
| `channels` | List all channels |
| `roles` | List all roles |
| `members [--limit N]` | List server members |
| `create-channel <name>` | Create text channel |
| `create-voice <name>` | Create voice channel |
| `create-category <name>` | Create category |
| `create-role <name>` | Create role |
| `delete-channel <name>` | Delete a channel |
| `delete-role <name>` | Delete a role |
| `send <channel> <msg>` | Send a message |
| `purge <channel>` | Delete messages |
| `export` | Export server structure |
| `setup-standard` | Create standard structure |

### Options for create-channel
- `--category, -c`: Category to place channel in
- `--topic, -t`: Channel topic/description
- `--slowmode, -s`: Slowmode delay in seconds

### Options for create-role
- `--color`: Hex color (e.g., `#ff0000`)
- `--hoist`: Display role separately in member list
- `--mentionable`: Allow @mentions of this role

## Bot Commands (for users)

Once running, users can interact with the bot via slash commands:

| Command | Description |
|---------|-------------|
| `/generate_pack` | Start a photo pack order (requires BTC payment) |
| `/upload_refs` | Upload reference photos after payment |

## File Structure

```
discord_ai_photo_bot/
├── .env                    # Your configuration (create from env.sample)
├── env.sample              # Example configuration
├── discord_config.json     # Server config (created by setup)
├── requirements.txt        # Python dependencies
├── setup_discord.py        # Interactive setup wizard
├── manage_server.py        # CLI server management
├── venv/                   # Python virtual environment
└── src/
    └── discord_ai_photo_bot/
        ├── bot.py              # Main bot entry point
        ├── config.py           # Configuration loader
        ├── database.py         # SQLite database
        ├── server_manager.py   # Server management utilities
        ├── ai/
        │   └── generator.py    # Replicate AI integration
        ├── commands/
        │   └── generate_pack.py # Slash commands
        ├── jobs/
        │   └── queue.py        # Job queue for generation
        ├── payments/
        │   └── bitcoin.py      # BTC payment handling
        └── storage/
            └── discord_storage.py # File delivery
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ | Your bot token |
| `DISCORD_APPLICATION_ID` | ✅ | Your application ID |
| `DISCORD_GUILD_ID` | ✅ | Your server ID |
| `REPLICATE_API_TOKEN` | ✅ | Replicate API key for AI |
| `BTC_RECEIVER_ADDRESS` | ✅ | Bitcoin address for payments |
| `PAYMENT_WEBHOOK_SECRET` | ❌ | Webhook secret for payments |
| `PACK_USD_PRICE` | ❌ | Price per pack (default: 25.0) |
| `PAYMENT_TIMEOUT_SECONDS` | ❌ | Payment timeout (default: 900) |
| `DISCORD_AI_BOT_DATA_DIR` | ❌ | Data directory (default: ./data) |

## Troubleshooting

### Bot not responding to commands
- Make sure the bot is online (green dot)
- Run `python manage_server.py info` to test connection
- Check that slash commands are synced (may take up to an hour)

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
DISCORD_LOG_LEVEL=DEBUG python -m discord_ai_photo_bot.bot
```

## License

MIT









