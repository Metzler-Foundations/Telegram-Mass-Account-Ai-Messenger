# Persistent Connection & Proxy Assignment Guide

## Overview

This system ensures that:
1. **Each account gets a PERMANENT proxy** from your app's proxy list
2. **Accounts ALWAYS stay logged in** - critical for one-time phone numbers
3. **Automatic reconnection** if connection is lost
4. **Accounts are always ready** when you need to control them

## Why This Is Critical

**One-time phone numbers** cannot be reused. If an account disconnects and you can't reconnect, **the account is LOST FOREVER**. This system prevents that.

## How It Works

### 1. Proxy Assignment (During Account Creation)

When you create an account:
1. System gets proxy list from your app settings
2. Assigns ONE proxy to the account permanently
3. Stores proxy in account data
4. Account will ALWAYS use this proxy

**Round-Robin Distribution:**
- Proxies are distributed evenly across accounts
- Account 1 → Proxy 1
- Account 2 → Proxy 2
- Account 3 → Proxy 3
- Account 4 → Proxy 1 (wraps around)
- etc.

### 2. Persistent Connection Management

**Automatic Monitoring:**
- Checks connection status every 30 seconds
- Detects disconnections immediately
- Automatically attempts reconnection

**Reconnection Strategy:**
- Exponential backoff: 5s, 10s, 15s, 30s, 60s, 2min, 5min, 10min, 15min, 30min
- Up to 10 reconnection attempts
- Uses the same permanent proxy
- Preserves session (no re-authentication needed)

### 3. Account Status

Each account is marked with:
- `always_online: true` - Must stay connected
- `one_time_phone: true` - Phone number cannot be reused
- `proxy: {...}` - Permanent proxy assignment

## Usage

### Adding Proxies to App

1. Go to Settings → Proxy Settings
2. Click "Add Proxy"
3. Enter proxy in format: `ip:port` or `ip:port:username:password`
4. Proxy is added to list
5. All new accounts will use proxies from this list

### Creating Accounts

When you create accounts:
- System automatically assigns proxies from your list
- Each account gets ONE permanent proxy
- Proxy is saved with account data
- Account will always use this proxy

### Starting Accounts

When accounts start:
- They automatically use their assigned proxy
- Connection monitoring starts automatically
- If disconnected, auto-reconnect begins immediately

### Checking Connection Status

```python
# Get status for one account
status = account_manager.connection_manager.get_connection_status(phone_number)

# Get status for all accounts
all_statuses = account_manager.connection_manager.get_all_statuses()
```

## Safety Features

### 1. Connection Monitoring
- Continuous monitoring (every 30 seconds)
- Immediate detection of disconnections
- Automatic reconnection attempts

### 2. Reconnection Logic
- Exponential backoff prevents spam
- Maximum 10 attempts
- Uses same proxy (no proxy rotation)
- Preserves session

### 3. Protection Against Accidental Stops
- `stop_client()` warns if account uses one-time phone
- Requires `force=True` to stop one-time phone accounts
- Prevents accidental account loss

## Important Notes

### ⚠️ CRITICAL WARNINGS

1. **Never stop accounts with one-time phones** unless absolutely necessary
2. **If connection is lost**, system will auto-reconnect
3. **If auto-reconnect fails**, account may be lost forever
4. **Always monitor connection status** for important accounts

### ✅ Best Practices

1. **Add multiple proxies** to distribute load
2. **Monitor connection status** regularly
3. **Use quality proxies** (residential recommended)
4. **Keep app running** to maintain connections
5. **Check logs** for reconnection attempts

## Troubleshooting

### Account Disconnected

**Symptoms:**
- Account shows as disconnected
- Reconnection attempts in logs

**Actions:**
1. Check proxy status (may be down)
2. Check network connectivity
3. Wait for auto-reconnect (up to 30 minutes)
4. If fails, account may be lost (one-time phone)

### Proxy Issues

**Symptoms:**
- Multiple accounts using same proxy fail
- Proxy validation errors

**Actions:**
1. Remove bad proxy from list
2. Add new proxy
3. New accounts will use new proxy
4. Existing accounts keep their assigned proxy

### Connection Monitoring Not Working

**Symptoms:**
- Accounts disconnect and don't reconnect
- No monitoring logs

**Actions:**
1. Check if monitoring is started: `connection_manager.is_monitoring`
2. Restart app to restart monitoring
3. Check logs for errors

## Technical Details

### Proxy Storage Format

```json
{
  "proxy": {
    "ip": "1.2.3.4",
    "port": 8080,
    "scheme": "http",
    "username": "user",  // Optional
    "password": "pass",  // Optional
    "assigned_at": "2024-01-01T00:00:00",
    "is_permanent": true
  }
}
```

### Connection Manager

- Monitors all registered clients
- Checks every 30 seconds
- Reconnects immediately on disconnect
- Exponential backoff for retries
- Maximum 10 attempts

### Account Data

```json
{
  "phone_number": "+1234567890",
  "always_online": true,
  "one_time_phone": true,
  "proxy": {...},
  "status": "active"
}
```

## Summary

✅ **Permanent Proxy Assignment**: Each account gets one proxy forever
✅ **Always-On Connection**: Accounts never disconnect
✅ **Auto-Reconnect**: Automatic recovery from disconnections
✅ **Ready to Use**: Accounts always available when needed
✅ **Safety First**: Protection against accidental account loss

This system ensures your accounts are always ready to use, even with one-time phone numbers!


