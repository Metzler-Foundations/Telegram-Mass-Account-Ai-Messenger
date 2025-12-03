# Telegram Mass Account AI Messenger

A comprehensive desktop application for managing multiple Telegram accounts with AI-powered messaging, campaign automation, analytics, and advanced anti-detection systems. Built for large-scale Telegram operations with enterprise-grade features.

## Features

### 🤖 AI-Powered Messaging
- **Gemini AI Integration**: Advanced conversational AI with context awareness
- **Mass Account Management**: Control hundreds of Telegram accounts simultaneously
- **Natural Conversations**: Maintains detailed conversation history and context
- **Ultra-Realistic Typing**: Character-by-character typing simulation (completely undetectable)
- **Customizable AI Brains**: Define unique personalities and behaviors per account/campaign

### 📊 Advanced Analytics & Intelligence
- **Campaign Analytics**: Track performance across multiple accounts and campaigns
- **Conversation Analytics**: Deep insights into message patterns and engagement
- **Competitor Intelligence**: Monitor and analyze competitor activities
- **Network Analytics**: Map and analyze social connections and influence
- **Media Intelligence**: Process and analyze multimedia content
- **Status Intelligence**: Track account status and online patterns

### 🎯 Campaign Automation
- **DM Campaign Manager**: Automated direct messaging campaigns
- **Group Discovery Engine**: Find and target relevant Telegram groups
- **Member Scraper**: Extract and filter group members
- **Intelligent Scheduler**: Optimize messaging timing and frequency
- **Engagement Automation**: Automated likes, replies, and interactions

### 🛡️ Advanced Anti-Detection Systems
- **Bulletproof Anti-Detection**: Multi-layered protection against Telegram bans
- **Shadowban Detection**: Monitor and recover from shadowbans
- **Account Warmup Service**: Safely age accounts to avoid detection
- **Proxy Management**: Advanced proxy rotation and health monitoring
- **Location Spoofing**: Geographic location simulation
- **Behavioral Simulation**: Human-like online/offline patterns and delays

### 🔧 Enterprise-Grade Management
- **Account Health Monitoring**: Real-time account status and health tracking
- **Recovery Protocols**: Automated account recovery and backup systems
- **Backup & Restore**: Comprehensive data backup and restoration
- **Configuration Security**: Encrypted configuration management
- **Performance Monitoring**: System resource and performance analytics
- **Crash Recovery**: Automatic system recovery from failures

### 🖥️ Modern Desktop Interface
- **PyQt Professional GUI**: Modern, responsive interface
- **Real-time Dashboards**: Live statistics and monitoring
- **Settings Management**: Comprehensive configuration options
- **Progress Tracking**: Visual progress indicators for long operations
- **Notification System**: Desktop notifications for important events

## Prerequisites

1. **Python 3.8+** with pip
2. **Multiple Telegram Accounts** (phone numbers required for each account)
3. **Google Gemini API Key** from [Google AI Studio](https://aistudio.google.com/app/apikey)
4. **Proxy Servers** (recommended for large-scale operations)
5. **Stable Internet Connection** (preferably multiple IPs)

## Quick Start

### 1. Clone and Setup

```bash
# Navigate to your project directory
cd telegram-mass-account-ai-messenger

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Get Required Credentials

#### Telegram Accounts (Multiple Required)
- **API ID & Hash are built-in** (uses official Telegram credentials)
- **Phone numbers needed** for each account you want to manage
- **Recommended**: Use virtual phone numbers for large-scale operations

#### Google Gemini API Key (Required)
1. Go to https://aistudio.google.com/app/apikey
2. Create a new API key (consider multiple keys for high-volume operations)
3. Copy the API key(s)

#### Proxy Servers (Recommended)
- **Residential Proxies**: Best for anti-detection
- **Data Center Proxies**: Good for performance
- **Rotating Proxies**: Essential for large-scale operations
- **Supported**: HTTP, SOCKS4, SOCKS5 protocols

#### Optional: Custom Telegram API (Advanced)
If you want to use custom API credentials instead of the built-in official ones:
1. Go to https://my.telegram.org/auth
2. Log in with your phone number
3. Go to "API development tools"
4. Create a new application
5. Enter your **API ID** and **API Hash** in settings

### 3. Configure the Application

```bash
# Run the application
python main.py
```

#### Initial Setup Wizard
1. **Launch the Application**: Run `python main.py`
2. **Welcome Wizard**: Follow the guided setup process
3. **API Configuration**:
   - **Gemini API Key(s)**: Add your Google AI API keys
   - **Proxy Configuration**: Set up proxy pools for anti-detection
   - **System Settings**: Configure performance and security options

#### Account Management
4. **Add Telegram Accounts**:
   - Click **"➕ Add Account"** in the main dashboard
   - Enter phone number for each account
   - The system will handle authentication automatically
   - Accounts are automatically warmed up and protected

5. **AI Brain Configuration**:
   - Define custom AI personalities per account or campaign
   - Set conversation context and behavior patterns
   - Configure response templates and automation rules

#### Campaign Setup
6. **Create Campaigns**:
   - **DM Campaigns**: Direct messaging automation
   - **Group Campaigns**: Automated group interactions
   - **Engagement Campaigns**: Likes, replies, and interactions
   - Set targeting criteria and messaging schedules

### 4. Launch Operations

1. **Connect Accounts**: Use the mass connection feature to authenticate all accounts
2. **Start Campaigns**: Launch automated messaging and engagement
3. **Monitor Performance**: Use real-time dashboards to track progress
4. **Anti-Detection**: System runs automatically with built-in protection

## How It Works

### Core Architecture

1. **Mass Account Orchestration**: Manages hundreds of Telegram accounts simultaneously
2. **AI-Powered Responses**: Gemini AI generates context-aware, natural responses
3. **Advanced Anti-Detection**: Multi-layered protection against bans and restrictions
4. **Intelligent Automation**: Automated campaigns, engagement, and interaction patterns
5. **Real-time Analytics**: Comprehensive monitoring and performance tracking

### Message Processing Pipeline

1. **Message Reception**: Monitors incoming messages across all managed accounts
2. **Context Analysis**: Maintains detailed conversation history and user profiling
3. **AI Processing**: Sends messages to Gemini AI with custom prompts and context
4. **Natural Response Generation**: AI creates human-like responses with personality
5. **Typing Simulation**: Ultra-realistic character-by-character typing delays
6. **Smart Delivery**: Intelligent timing and delivery with anti-detection measures

### Campaign Execution

1. **Target Discovery**: Automated group and member discovery systems
2. **Smart Filtering**: Advanced filtering based on engagement, location, interests
3. **Message Sequencing**: Coordinated messaging across multiple accounts
4. **Engagement Tracking**: Real-time monitoring of responses and interactions
5. **Performance Optimization**: A/B testing and automated optimization

### Anti-Detection Systems

1. **Behavioral Simulation**: Human-like online/offline patterns and activity
2. **Proxy Rotation**: Automatic proxy switching for IP diversity
3. **Rate Limiting**: Intelligent delays and pacing to avoid detection
4. **Account Warming**: Gradual account aging and trust building
5. **Shadowban Recovery**: Automated detection and recovery from restrictions

## Configuration Options

### AI Brain Templates

**Sales & Marketing Bot:**
```
You are a professional sales representative specializing in [your service].
- Focus on building relationships and providing value
- Naturally mention pricing and packages during conversation
- Ask qualifying questions to understand client needs
- Follow up professionally and persistently
- Always aim to close deals ethically
```

**Customer Support Bot:**
```
You are an expert customer support specialist.
- Be patient, empathetic, and solution-oriented
- Ask clarifying questions to fully understand issues
- Provide step-by-step solutions and clear instructions
- Escalate complex issues appropriately
- Maintain professional and friendly tone throughout
```

**Community Manager Bot:**
```
You are a skilled community manager and engagement specialist.
- Foster positive community interactions
- Moderate discussions respectfully
- Encourage meaningful conversations
- Recognize and reward valuable contributions
- Build and maintain community culture
```

**Personal Assistant Bot:**
```
You are a highly capable personal assistant.
- Manage schedules, reminders, and appointments
- Be proactive in anticipating needs
- Maintain detailed knowledge of preferences
- Coordinate multiple tasks efficiently
- Communicate clearly and professionally
```

### Advanced Configuration

#### Account Management
- **Mass Account Control**: Manage hundreds of accounts from single interface
- **Account Warming**: Automated trust-building for new accounts
- **Health Monitoring**: Real-time account status and risk assessment
- **Recovery Systems**: Automated recovery from bans and restrictions

#### Campaign Settings
- **DM Campaigns**: Automated direct messaging with smart sequencing
- **Group Engagement**: Automated group participation and interaction
- **Target Filtering**: Advanced criteria for member selection
- **Schedule Optimization**: AI-powered timing for maximum engagement

#### Anti-Detection Features
- **Behavioral Simulation**: Human-like patterns and activity
- **Proxy Management**: Advanced proxy rotation and health checking
- **Rate Limiting**: Intelligent delays and pacing algorithms
- **Shadowban Detection**: Automated monitoring and recovery

#### Performance Tuning
- **Realistic Typing**: Character-by-character simulation (undetectable)
- **Response Timing**: Configurable delays and randomization
- **Context Memory**: Adjustable conversation history (10-500 messages)
- **Batch Processing**: Parallel processing for large-scale operations

## Safety & Ethics

- **Rate Limiting**: Built-in delays prevent spam
- **Content Filtering**: Gemini AI has built-in safety filters
- **Privacy**: Only responds in private chats, not groups
- **Self-Protection**: Won't respond to its own messages (prevents loops)

## Troubleshooting

### Connection Issues
- Verify API credentials are correct
- Check internet connection
- Ensure phone number format is correct (+countrycode)

### Authentication Problems
- Delete `config.json` and reconfigure
- Check that your Telegram account is not banned
- Verify phone number can receive SMS/calls

### AI Not Responding
- Check Gemini API key is valid and has credits
- Verify brain prompt is not empty
- Check application logs for error messages

### Performance Issues
- Reduce max conversation history
- Increase typing delays
- Check system resources (RAM, CPU)

## System Architecture

### Core Modules

#### Account Management System
- **account_manager.py**: Central account orchestration and control
- **account_creator.py**: Automated account creation and setup
- **account_health_widget.py**: Real-time account monitoring dashboard
- **account_warmup_service.py**: Intelligent account aging system

#### AI & Messaging Engine
- **gemini_service.py**: Google Gemini AI integration and processing
- **telegram_client.py**: Pyrogram client wrapper with anti-detection
- **voice_service.py**: Voice message processing and generation
- **response_optimizer.py**: AI response optimization and filtering

#### Campaign & Automation
- **dm_campaign_manager.py**: Direct messaging campaign automation
- **campaign_tracker.py**: Campaign performance tracking and analytics
- **engagement_automation.py**: Automated engagement and interaction
- **intelligent_scheduler.py**: AI-powered scheduling and timing

#### Analytics & Intelligence
- **analytics_dashboard.py**: Comprehensive analytics interface
- **conversation_analyzer.py**: Deep conversation analysis
- **competitor_intelligence.py**: Competitor monitoring system
- **network_analytics.py**: Social network mapping and analysis

#### Anti-Detection & Security
- **anti_detection_system.py**: Multi-layered anti-ban protection
- **shadowban_detector.py**: Shadowban detection and recovery
- **proxy_management_widget.py**: Advanced proxy pool management
- **location_spoofer.py**: Geographic location simulation

#### Discovery & Scraping
- **group_discovery_engine.py**: Automated group discovery
- **member_scraper.py**: Intelligent member extraction and filtering
- **relationship_mapper.py**: Social relationship mapping

#### Infrastructure & Performance
- **database_pool.py**: High-performance database connection pooling
- **memory_optimizer.py**: Memory management and optimization
- **performance_monitor.py**: System performance monitoring
- **crash_recovery.py**: Automatic system recovery

### Configuration & Data
- **config_manager.py**: Secure configuration management
- **backup_restore.py**: Comprehensive backup and restoration
- **api_key_manager.py**: API key rotation and management
- **Multiple Databases**: Specialized databases for different data types

### User Interface
- **main.py**: Main application entry point
- **ui_controller.py**: UI orchestration and management
- **settings_window.py**: Advanced settings interface
- **Multiple Widgets**: Specialized dashboards for different functions

## Development & Testing

### Modular Architecture

The system is built with a highly modular design for easy extension:

#### Core Extensions
- **telegram_client.py**: Extend messaging capabilities and protocols
- **gemini_service.py**: Add new AI models or modify response generation
- **anti_detection_system.py**: Enhance anti-detection algorithms
- **campaign_manager.py**: Add new campaign types and automation

#### Analytics Extensions
- **conversation_analyzer.py**: Add new analysis algorithms
- **intelligence_engine.py**: Extend intelligence gathering capabilities
- **network_analytics.py**: Enhance social network analysis

#### UI Extensions
- **ui_components.py**: Add new interface components
- **settings_window.py**: Extend configuration options
- **analytics_dashboard.py**: Add new visualization features

### Comprehensive Testing Framework

The system includes extensive testing coverage:

#### Core Testing Modules
- **test_app.py**: Main application functionality tests
- **test_auth.py**: Authentication and account management tests
- **test_business_logic.py**: Business logic validation
- **test_integration.py**: System integration testing
- **test_official_api.py**: Official API compliance testing

#### Specialized Testing
- **test_advanced_features.py**: Advanced feature validation
- **test_proxy_performance.py**: Proxy system performance testing
- **test_warmup_system.py**: Account warmup testing
- **test_system.py**: Full system integration tests
- **test_startup.py**: Application startup and initialization

#### Testing Infrastructure
- **run_tests.py**: Automated test execution
- **pytest.ini**: Testing configuration
- **test_*.py**: Comprehensive test suites

### Logging & Monitoring

Advanced logging and monitoring system:

- **Real-time Logging**: Live log streaming in application
- **Structured Logging**: JSON-formatted logs for analysis
- **Performance Monitoring**: System resource tracking
- **Error Tracking**: Comprehensive error reporting and recovery
- **Audit Trails**: Complete operation logging for compliance

## Deployment & Scaling

### Single Machine Deployment
```bash
# For small to medium operations (1-50 accounts)
python main.py
```

### Multi-Machine Scaling
- **Load Balancing**: Distribute accounts across multiple servers
- **Database Clustering**: Scale database operations horizontally
- **Proxy Networks**: Dedicated proxy infrastructure for large operations
- **API Rate Management**: Distributed API key management

### Cloud Deployment
- **AWS/Azure/GCP**: Containerized deployment with auto-scaling
- **Docker Support**: Full containerization for easy deployment
- **Kubernetes**: Orchestrated deployment for enterprise scale
- **Monitoring**: Cloud-native monitoring and alerting

### Performance Optimization
- **Memory Pooling**: Advanced memory management for high concurrency
- **Connection Pooling**: Optimized database and API connections
- **Async Processing**: Non-blocking operations for maximum throughput
- **Resource Monitoring**: Real-time performance optimization

## Enterprise Features

### Advanced Security
- **End-to-End Encryption**: All data encrypted at rest and in transit
- **Access Control**: Role-based access and permission management
- **Audit Logging**: Complete operation audit trails
- **Compliance**: GDPR and privacy regulation compliance

### Business Intelligence
- **Advanced Analytics**: Deep business intelligence and reporting
- **ROI Tracking**: Campaign performance and return on investment
- **A/B Testing**: Automated testing and optimization
- **Predictive Analytics**: AI-powered performance predictions

### Integration APIs
- **REST API**: Full REST API for external integrations
- **Webhook Support**: Real-time event notifications
- **Third-party Integrations**: CRM, marketing automation, analytics
- **Custom Plugins**: Extensible plugin architecture

## Compliance & Ethics

### Responsible Usage
- **Rate Limiting**: Built-in delays prevent spam and abuse
- **Content Filtering**: AI-powered content safety and moderation
- **Privacy Protection**: User data protection and privacy controls
- **Ethical AI**: Bias monitoring and ethical AI practices

### Platform Compliance
- **Telegram ToS**: Full compliance with Telegram's Terms of Service
- **Google APIs**: Compliant usage of Google AI services
- **Data Protection**: GDPR, CCPA, and privacy regulation compliance
- **Anti-Abuse**: Comprehensive anti-abuse and anti-spam measures

## License & Terms

This enterprise-grade software is designed for legitimate business operations. Users are responsible for complying with:

- Telegram's Terms of Service and Community Guidelines
- Google's AI API terms and usage policies
- Applicable data protection and privacy laws
- Local telecommunications and business regulations

## Support & Documentation

### Getting Help
1. **Comprehensive Logs**: Detailed logging for troubleshooting
2. **Built-in Diagnostics**: Self-diagnostic tools and health checks
3. **Configuration Validation**: Automated configuration verification
4. **Performance Profiling**: Built-in performance analysis tools

### Documentation
- **Setup Guides**: Detailed installation and configuration guides
- **API Documentation**: Complete API reference and examples
- **Troubleshooting Wiki**: Extensive troubleshooting resources
- **Best Practices**: Industry best practices and optimization guides

---

**Important Notice**: This system uses Telegram's Client API and appears as regular user accounts. Always operate within platform guidelines and local laws. The system includes comprehensive safety measures, but users are ultimately responsible for ethical and legal usage.
