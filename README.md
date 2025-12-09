# Telegram Automation Platform

A comprehensive desktop application built with PyQt6 for automating Telegram account management, campaigns, and engagement. Features AI-powered responses via Google Gemini, intelligent warmup services, anti-detection systems, and comprehensive analytics.

## Overview

This platform provides a complete solution for managing multiple Telegram accounts, running automated campaigns, monitoring account health, and engaging with users intelligently. The application features a modern desktop UI with real-time dashboards, analytics, and comprehensive account management tools.

## Current Status

**Overall Maturity:** ~60% of planned functionality is fully wired and operational. Core UI and services are functional, with several advanced features requiring live configuration and testing.

### ✅ Working Features

- **Desktop Application:** Full PyQt6 UI with modern navigation and real-time updates
- **Dashboard:** Live metrics, counters, and statistics with 5-second refresh intervals
- **Account Management:** Start/stop/delete accounts, bulk creation with preflight checks
- **Campaign Management:** DM campaigns, template management, intelligent scheduling
- **Analytics:** Real-time charts and statistics (requires PyQt6-Charts)
- **Proxy Management:** Manual proxy entry/testing, auto mode with proxy pool manager
- **Warmup Service:** Account warmup with progress tracking and configurable settings
- **Health & Risk Monitoring:** Anti-detection integration, account health tracking
- **Welcome Wizard:** First-time setup guide for easy onboarding

### ⚠️ Requires Configuration/Testing

- Bulk account creation needs SMS provider configuration and live testing
- Telegram session management requires valid API credentials
- Delivery analytics depend on populated databases and optional services
- Background service shutdown coordination needs hardening
- Optional modules (PyQt6-Charts, proxy_pool_manager, engagement_automation) require manual enablement

## Requirements

### System Requirements
- **Python:** 3.9+ (developed on 3.11)
- **Display Server:** Required for PyQt6 desktop application
- **OS:** Linux, macOS, or Windows

### Required API Keys
- `TELEGRAM_API_ID` - Telegram API ID from [my.telegram.org](https://my.telegram.org)
- `TELEGRAM_API_HASH` - Telegram API Hash from [my.telegram.org](https://my.telegram.org)
- `GEMINI_API_KEY` - Google Gemini API key for AI-powered responses
- `SMS_PROVIDER_API_KEY` - For account creation (supports daisysms, smspool, textverified)

### Optional Dependencies
- PyQt6-Charts for enhanced analytics visualizations
- Proxy pool manager for automated proxy rotation
- Additional engagement automation modules

## Quick Start

### Installation

```bash
# Clone the repository
cd /home/metzlerdalton3/bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Set required environment variables:

```bash
export TELEGRAM_API_ID=your_api_id
export TELEGRAM_API_HASH=your_api_hash
export GEMINI_API_KEY=your_gemini_key
export SMS_PROVIDER_API_KEY=your_sms_provider_key
```

Alternatively, use the Settings UI in the application to configure API keys securely.

### Running the Application

```bash
python main.py
```

On first launch, the Welcome Wizard will guide you through initial setup.

## Features

### Account Management
- **Bulk Account Creation:** Automated account creation with SMS verification
- **Account Warmup:** Intelligent warmup service with progress tracking
- **Account Health Monitoring:** Real-time health metrics and risk assessment
- **Session Management:** Secure session storage and management

### Campaign Management
- **DM Campaigns:** Automated direct message campaigns with template support
- **Intelligent Scheduling:** AI-powered scheduling based on engagement patterns
- **A/B Testing:** Template variant testing with statistical analysis
- **Response Tracking:** Read receipts, delivery status, and engagement metrics

### Analytics & Monitoring
- **Real-time Dashboard:** Live metrics and statistics
- **Campaign Analytics:** Delivery rates, response rates, engagement metrics
- **Cost Tracking:** SMS and API usage cost monitoring
- **Risk Distribution:** Account risk level visualization

### Anti-Detection
- **Device Fingerprinting:** Randomized device fingerprints
- **User Agent Rotation:** Automatic user agent rotation
- **Location Spoofing:** Geographic location management
- **Timing Optimization:** Human-like timing patterns
- **Shadowban Detection:** Proactive shadowban monitoring

### Proxy Management
- **Manual Mode:** Test and validate individual proxies
- **Auto Mode:** Automated proxy rotation and management
- **Proxy Pool:** Centralized proxy pool with health monitoring

## Project Structure

```
bot/
├── accounts/          # Account management and warmup services
├── ai/                # Gemini AI integration and intelligence
├── analytics/         # Analytics and chart rendering
├── anti_detection/    # Anti-detection systems
├── campaigns/         # Campaign management and automation
├── core/              # Core services and configuration
├── database/          # Database management and migrations
├── integrations/      # Third-party integrations
├── monitoring/        # Performance and health monitoring
├── proxy/             # Proxy management
├── scraping/          # Member scraping and relationship mapping
├── telegram/          # Telegram client integration
├── ui/                # PyQt6 UI components
└── utils/             # Utility functions and helpers
```

## Configuration

### Settings UI
Access Settings from the main menu to configure:
- API keys and credentials
- SMS provider settings
- Proxy configuration
- Warmup parameters
- Performance and power settings

### Low-Power Mode
For resource-constrained systems (2-core, 4-8GB RAM):
1. Open Settings → Advanced Controls → Performance & Power
2. Enable "Low-Power Mode"
3. This reduces background polling and worker counts
4. Dashboard refresh intervals become longer
5. Auto-start features are disabled

## Data & Storage

### Databases
- `accounts.db` - Account information and sessions
- `campaigns.db` - Campaign data and analytics
- `members.db` - Scraped member data
- `proxy_pool.db` - Proxy pool management
- Additional specialized databases for analytics, intelligence, etc.

### Logs
- `telegram_bot.log` - General application logs
- `telegram_bot_errors.log` - Error logs

**Note:** If databases become locked or corrupted, remove `*.db-wal` and `*.db-shm` files (data loss risk) and restart.

## Troubleshooting

### Import Errors
```bash
./venv/bin/python3 scripts/test_all_imports.py
```

### Database Issues
- Remove `*.db-wal` and `*.db-shm` files if corruption occurs
- Restart the application

### Proxy Issues
- Use manual mode to test individual proxies
- Verify proxy format and credentials

### Missing Features
- Anti-detection: Ensure `anti_detection/anti_detection_system.py` is present
- Analytics charts: Install PyQt6-Charts
- Engagement automation: Verify `campaigns/engagement_automation.py` exists

## Development

### Testing
```bash
# Run import tests
python scripts/test_all_imports.py

# Run UI visual tests
python scripts/visual_test_all_tabs.py

# Run pre-flight checks
python scripts/pre_flight_check.py
```

### Code Quality
- Follow PEP 8 style guidelines
- Use type hints where applicable
- Document complex functions and classes

## Known Limitations

- Background service shutdown coordination needs improvement
- Better error handling for async tasks triggered from UI
- End-to-end testing of bulk account creation with live SMS providers
- Validation of delivery/risk analytics against real production data
- Optional module enablement requires manual configuration

## License

Proprietary. See `LICENSE` file for details.

## Support

For issues, questions, or contributions, please refer to the project documentation or contact the development team.

---

**Last Updated:** December 2025
