# Telegram Automation Platform - Production Docker Image

FROM python:3.11-slim

# Metadata
LABEL maintainer="ops@example.com"
LABEL version="1.0.0-alpha"
LABEL description="Telegram Automation Platform"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN useradd -r -s /bin/bash -m -d /app telegram-bot

# Set working directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=telegram-bot:telegram-bot . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/backups && \
    chown -R telegram-bot:telegram-bot /app && \
    chmod 700 /app/data /app/logs /app/backups

# Switch to application user
USER telegram-bot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# Expose ports (if needed)
# EXPOSE 8080

# Volume for persistent data
VOLUME ["/app/data", "/app/logs", "/app/backups"]

# Entry point
ENTRYPOINT ["python3"]
CMD ["main.py"]


