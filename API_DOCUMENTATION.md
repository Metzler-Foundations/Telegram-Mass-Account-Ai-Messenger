# API Documentation

## Overview

REST API for Telegram Automation Platform.

**Base URL:** `http://localhost:8080/api/v1`  
**Authentication:** API Key (Header: `X-API-Key`)  
**Content-Type:** `application/json`

## Authentication

### Create API Key

```http
POST /auth/api-key
```

**Request:**
```json
{
  "user_id": "user123",
  "role": "admin"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "api_key": "ak_xxxxxxxxxxxxxxxxxx",
    "expires_at": "2026-12-04T00:00:00Z"
  }
}
```

## Accounts

### Create Account

```http
POST /accounts
```

**Request:**
```json
{
  "country_code": "US",
  "sms_provider": "smspool"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "account_id": "acc_123",
    "phone_number": "+1234567890",
    "status": "created"
  }
}
```

### List Accounts

```http
GET /accounts?page=1&page_size=50
```

**Response:**
```json
{
  "status": "success",
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_items": 150,
    "total_pages": 3
  }
}
```

## Campaigns

### Create Campaign

```http
POST /campaigns
```

**Request:**
```json
{
  "name": "Campaign 1",
  "template": "Hello {{name}}!",
  "account_ids": ["acc_1", "acc_2"],
  "target_user_ids": [123, 456]
}
```

### Get Campaign Status

```http
GET /campaigns/{campaign_id}/status
```

## Analytics

### Export Campaign Results

```http
GET /campaigns/{campaign_id}/export?format=csv
```

Returns CSV file download.

## Health

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "telegram_api": "ok"
  }
}
```

## Error Responses

All errors follow standard format:

```json
{
  "status": "error",
  "message": "Error description",
  "error_code": "ERROR_CODE",
  "details": {},
  "timestamp": "2025-12-04T12:00:00Z"
}
```

## Rate Limits

- **Global:** 1000 requests/hour
- **Per API Key:** 500 requests/hour
- **Account Creation:** 10/hour
- **Message Sending:** 60/hour per account

## Webhooks

### Configure Webhook

```http
POST /webhooks
```

**Request:**
```json
{
  "url": "https://yourserver.com/webhook",
  "events": ["message.delivered", "campaign.completed"],
  "secret": "webhook_secret_key"
}
```

Webhook payloads include HMAC signature in `X-Signature` header.

## SDK Examples

### Python

```python
from telegram_api_client import TelegramAPI

api = TelegramAPI(api_key="your_api_key")

# Create account
account = api.accounts.create(country_code="US")

# Start campaign
campaign = api.campaigns.create(
    name="Test Campaign",
    template="Hello!",
    accounts=[account.id]
)
```

### cURL

```bash
curl -X POST https://api.example.com/api/v1/accounts \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"country_code": "US"}'
```

