# Deployment Guide

Complete guide for deploying Telegram Automation Platform to production.

## Prerequisites

### System Requirements

**Minimum**
- CPU: 2 cores
- RAM: 4GB
- Disk: 10GB SSD
- OS: Linux (Ubuntu 20.04+ recommended)

**Recommended**
- CPU: 4+ cores
- RAM: 8GB+
- Disk: 50GB+ SSD
- OS: Ubuntu 22.04 LTS

### Software Requirements

- Python 3.9+
- pip 21.0+
- systemd (for service management)
- PostgreSQL 13+ or SQLite 3.35+ (WAL mode)

## Pre-Deployment Checklist

### Security

- [ ] All secrets migrated to environment variables or encrypted storage
- [ ] Database files have restrictive permissions (0600)
- [ ] Session files encrypted at rest
- [ ] TLS/SSL configured for external connections
- [ ] Rate limiting configured for all endpoints
- [ ] Authentication system enabled
- [ ] Audit logging active
- [ ] Input validation enabled
- [ ] Firewall rules configured
- [ ] Intrusion detection configured

### Stability

- [ ] Connection pooling configured
- [ ] Graceful shutdown handlers registered
- [ ] Memory limits set (via systemd or container)
- [ ] Error recovery tested
- [ ] Transaction rollback verified
- [ ] Circuit breakers configured
- [ ] Retry logic enabled

### Monitoring

- [ ] Health check endpoint active
- [ ] Metrics collection configured
- [ ] Alert thresholds set
- [ ] Log aggregation configured
- [ ] Backup schedule established
- [ ] Monitoring dashboard setup

## Installation

### 1. System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.9 python3-pip python3-venv git sqlite3

# Create application user
sudo useradd -r -s /bin/bash -m -d /opt/telegram-bot telegram-bot
```

### 2. Application Setup

```bash
# Switch to application user
sudo su - telegram-bot

# Clone repository
git clone <repository-url> /opt/telegram-bot/app
cd /opt/telegram-bot/app

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Create configuration directory
mkdir -p /opt/telegram-bot/config

# Set environment variables
cat > /opt/telegram-bot/config/environment << 'EOF'
# Secrets
export SECRET_TELEGRAM_API_ID="your_api_id"
export SECRET_TELEGRAM_API_HASH="your_api_hash"
export SECRET_GEMINI_API_KEY="your_gemini_key"
export SECRET_SMS_PROVIDER_API_KEY="your_sms_key"
export SECRET_MASTER_KEY="your_master_encryption_key"

# Application settings
export ENVIRONMENT="production"
export LOG_LEVEL="INFO"
export MAX_CONCURRENT_ACCOUNTS=50
export DATABASE_PATH="/opt/telegram-bot/data"
EOF

# Secure environment file
chmod 600 /opt/telegram-bot/config/environment
```

### 4. Database Setup

```bash
# Create data directory
mkdir -p /opt/telegram-bot/data
chmod 700 /opt/telegram-bot/data

# Initialize databases
cd /opt/telegram-bot/app
source /opt/telegram-bot/config/environment
python3 -c "
from database.connection_pool import get_pool
pool = get_pool('/opt/telegram-bot/data/main.db')
with pool.get_connection() as conn:
    print('Database initialized')
"
```

### 5. Systemd Service

Create `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Telegram Automation Platform
After=network.target

[Service]
Type=simple
User=telegram-bot
Group=telegram-bot
WorkingDirectory=/opt/telegram-bot/app
EnvironmentFile=/opt/telegram-bot/config/environment

# Start command
ExecStart=/opt/telegram-bot/app/venv/bin/python3 main.py

# Graceful shutdown
TimeoutStopSec=30
KillMode=mixed
KillSignal=SIGTERM

# Restart policy
Restart=on-failure
RestartSec=10

# Resource limits
LimitNOFILE=65536
MemoryLimit=2G
CPUQuota=200%

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/telegram-bot/data /opt/telegram-bot/app/logs

[Install]
WantedBy=multi-user.target
```

Enable and start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

## Post-Deployment

### Verification

```bash
# Check service status
sudo systemctl status telegram-bot

# View logs
sudo journalctl -u telegram-bot -f

# Check health endpoint (if enabled)
curl http://localhost:8080/health
```

### Monitoring Setup

```bash
# Install monitoring tools
sudo apt install -y prometheus-node-exporter

# Configure alerts (example with systemd)
cat > /etc/systemd/system/telegram-bot-monitor.service << 'EOF'
[Unit]
Description=Telegram Bot Monitor
After=telegram-bot.service

[Service]
Type=oneshot
ExecStart=/opt/telegram-bot/app/scripts/health_check.sh

[Install]
WantedBy=multi-user.target
EOF

# Setup timer for periodic checks
cat > /etc/systemd/system/telegram-bot-monitor.timer << 'EOF'
[Unit]
Description=Run Telegram Bot Monitor every 5 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF

sudo systemctl enable telegram-bot-monitor.timer
sudo systemctl start telegram-bot-monitor.timer
```

## Backup & Recovery

### Automated Backups

```bash
# Create backup script
cat > /opt/telegram-bot/scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/telegram-bot/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup databases
cp -r /opt/telegram-bot/data/*.db "$BACKUP_DIR/data_$DATE/"

# Backup configuration
cp /opt/telegram-bot/config/environment "$BACKUP_DIR/config_$DATE.env"

# Compress
tar -czf "$BACKUP_DIR/backup_$DATE.tar.gz" "$BACKUP_DIR/data_$DATE" "$BACKUP_DIR/config_$DATE.env"

# Cleanup
rm -rf "$BACKUP_DIR/data_$DATE" "$BACKUP_DIR/config_$DATE.env"

# Keep only last 7 days
find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete

echo "Backup completed: backup_$DATE.tar.gz"
EOF

chmod +x /opt/telegram-bot/scripts/backup.sh

# Schedule daily backups
echo "0 2 * * * /opt/telegram-bot/scripts/backup.sh" | sudo crontab -u telegram-bot -
```

### Restore Procedure

```bash
# Stop service
sudo systemctl stop telegram-bot

# Restore from backup
cd /opt/telegram-bot/backups
tar -xzf backup_YYYYMMDD_HHMMSS.tar.gz

# Copy databases
cp -r data_YYYYMMDD_HHMMSS/*.db /opt/telegram-bot/data/

# Restore configuration
cp config_YYYYMMDD_HHMMSS.env /opt/telegram-bot/config/environment

# Start service
sudo systemctl start telegram-bot
```

## Scaling

### Horizontal Scaling

For multiple instances:

1. **Setup load balancer** (nginx, HAProxy)
2. **Use shared database** (PostgreSQL instead of SQLite)
3. **Configure session storage** (Redis)
4. **Setup distributed rate limiting** (Redis)

### Vertical Scaling

Increase resources in systemd service:

```ini
[Service]
MemoryLimit=4G
CPUQuota=400%
```

## Troubleshooting

### Common Issues

**Service won't start**
```bash
# Check logs
sudo journalctl -u telegram-bot -n 100

# Verify configuration
source /opt/telegram-bot/config/environment
python3 -c "import os; print(os.environ.get('SECRET_TELEGRAM_API_ID'))"
```

**High memory usage**
```bash
# Check process memory
ps aux | grep python3

# Review memory monitor logs
grep "Memory" /opt/telegram-bot/app/logs/app.log
```

**Database locked errors**
```bash
# Check database connections
lsof /opt/telegram-bot/data/*.db

# Enable WAL mode
sqlite3 /opt/telegram-bot/data/main.db "PRAGMA journal_mode=WAL;"
```

## Security Hardening

### File Permissions

```bash
# Set restrictive permissions
chmod 700 /opt/telegram-bot/data
chmod 600 /opt/telegram-bot/data/*.db
chmod 600 /opt/telegram-bot/config/environment
chmod 600 ~/.telegram_bot/master.key
```

### Firewall

```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8080/tcp  # Health check endpoint (if public)
sudo ufw enable
```

### SELinux/AppArmor

Configure mandatory access control as appropriate for your distribution.

## Rollback Procedure

```bash
# Stop service
sudo systemctl stop telegram-bot

# Checkout previous version
cd /opt/telegram-bot/app
git checkout <previous-commit-hash>

# Restore database from backup
# (See Restore Procedure above)

# Start service
sudo systemctl start telegram-bot
```

## Performance Tuning

### Database Optimization

```sql
-- Enable WAL mode
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

-- Optimize cache
PRAGMA cache_size=-64000;  -- 64MB cache

-- Analyze query performance
PRAGMA optimize;
```

### Python Optimization

```bash
# Use optimized Python
export PYTHONOPTIMIZE=2

# Pre-compile bytecode
python3 -m compileall /opt/telegram-bot/app
```

## Maintenance Windows

Recommended schedule:
- **Daily:** Log rotation (automated)
- **Weekly:** Database optimization, backup verification
- **Monthly:** Security updates, performance review
- **Quarterly:** Full system audit

---

For additional support, see:
- `README.md` - Quick start guide
- `ENGINEERING_REVIEW_REPORT.md` - Security assessment
- Email: ops@example.com


