#!/usr/bin/env python3
"""
Centralized logging configuration with rotation.

This module provides a single function to configure logging with rotation for the entire application.
"""

import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_level=logging.INFO):
    """
    Set up logging with rotation for the application.
    
    Args:
        log_level: Logging level (default: INFO)
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Main application log with rotation
    app_log_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,  # Keep 5 backup files
        encoding='utf-8'
    )
    app_log_handler.setLevel(log_level)
    app_log_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    app_log_handler.setFormatter(app_log_formatter)
    root_logger.addHandler(app_log_handler)
    
    # Telegram bot log with rotation (for telegram-specific logs)
    telegram_logger = logging.getLogger('telegram')
    telegram_handler = logging.handlers.RotatingFileHandler(
        log_dir / "telegram_bot.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    telegram_handler.setLevel(log_level)
    telegram_handler.setFormatter(app_log_formatter)
    telegram_logger.addHandler(telegram_handler)
    
    # Error log with rotation (only errors and above)
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "telegram_bot_errors.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(app_log_formatter)
    root_logger.addHandler(error_handler)
    
    # Structured log for important events
    structured_logger = logging.getLogger('structured')
    structured_handler = logging.handlers.RotatingFileHandler(
        log_dir / "telegram_bot_structured.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    structured_handler.setLevel(logging.INFO)
    structured_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    structured_handler.setFormatter(structured_formatter)
    structured_logger.addHandler(structured_handler)
    
    # Reduce noise from some verbose libraries
    logging.getLogger('pyrogram').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    logging.info("Logging configured with rotation (10MB per file, 5 backups)")


if __name__ == "__main__":
    # Test the logging setup
    setup_logging()
    
    logger = logging.getLogger(__name__)
    logger.info("Testing logging setup")
    logger.warning("This is a warning")
    logger.error("This is an error")
    
    # Test structured logging
    structured_logger = logging.getLogger('structured')
    structured_logger.info("Structured log entry")
    
    print("✅ Logging setup complete - check logs/ directory")


