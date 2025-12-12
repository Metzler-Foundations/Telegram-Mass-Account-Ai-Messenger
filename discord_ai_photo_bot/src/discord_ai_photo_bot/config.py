"""Configuration helpers for the Discord AI photo bot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use environment variables directly


@dataclass
class Settings:
    """Runtime configuration values."""

    discord_token: str
    replicate_token: str

    # Replicate LoRA workflow (premium studio)
    replicate_destination_owner: str
    replicate_training_model: str
    replicate_training_version: Optional[str]
    replicate_training_params_json: Optional[str]
    replicate_generation_params_json: Optional[str]
    replicate_trigger_word: Optional[str]

    openai_api_key: str
    sentry_dsn: Optional[str]
    discord_guild_id: str
    payment_webhook_secret: Optional[str]
    btc_receiver_address: Optional[str]
    btc_price_api: str
    usd_price: float
    payment_timeout_seconds: int
    data_dir: Path
    verification_channel_id: Optional[str]


def load_settings() -> Settings:
    """Load settings from environment variables with safe defaults."""

    data_dir = Path(
        os.environ.get("DISCORD_AI_BOT_DATA_DIR")
        or Path(__file__).resolve().parent.parent / "data"
    )
    data_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        discord_token=os.environ.get("DISCORD_BOT_TOKEN", ""),
        replicate_token=os.environ.get("REPLICATE_API_TOKEN", ""),
        replicate_destination_owner=os.environ.get("REPLICATE_DESTINATION_OWNER", ""),
        replicate_training_model=os.environ.get(
            "REPLICATE_TRAINING_MODEL",
            # Common community LoRA trainer; override in env for your preferred trainer.
            "ostris/flux-dev-lora-trainer",
        ),
        replicate_training_version=os.environ.get("REPLICATE_TRAINING_VERSION"),
        replicate_training_params_json=os.environ.get("REPLICATE_TRAINING_PARAMS_JSON"),
        replicate_generation_params_json=os.environ.get("REPLICATE_GENERATION_PARAMS_JSON"),
        replicate_trigger_word=os.environ.get("REPLICATE_TRIGGER_WORD", "TOK"),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        sentry_dsn=os.environ.get("SENTRY_DSN"),
        discord_guild_id=os.environ.get("DISCORD_GUILD_ID", ""),
        payment_webhook_secret=os.environ.get("PAYMENT_WEBHOOK_SECRET"),
        btc_receiver_address=os.environ.get("BTC_RECEIVER_ADDRESS"),
        btc_price_api=os.environ.get(
            "BTC_PRICE_API",
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
        ),
        usd_price=float(os.environ.get("PACK_USD_PRICE", "25.0")),
        payment_timeout_seconds=int(os.environ.get("PAYMENT_TIMEOUT_SECONDS", "900")),
        data_dir=data_dir,
        verification_channel_id=os.environ.get("DISCORD_VERIFICATION_CHANNEL_ID"),
    )

    missing = []
    if not settings.discord_token:
        missing.append("DISCORD_BOT_TOKEN")
    # REPLICATE_API_TOKEN and BTC_RECEIVER_ADDRESS are only needed for actual generation/payments
    # Allow bot to start without them for command syncing
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return settings





