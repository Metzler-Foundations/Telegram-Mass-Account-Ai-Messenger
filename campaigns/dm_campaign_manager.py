"""
DM Campaign Manager - Enterprise-grade bulk messaging system with anti-detection.

Features:
- Message template system with personalization
- Account rotation and load balancing
- Enhanced rate limiting and anti-detection integration
- Campaign tracking and analytics
- Error recovery and retry logic
- Integration with EnhancedAntiDetectionSystem
- Message diversity analysis
- Account risk monitoring
"""

import asyncio
import json
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Import connection pool for database operations
try:
    from database.connection_pool import get_pool

    CONNECTION_POOL_AVAILABLE = True
except ImportError:
    CONNECTION_POOL_AVAILABLE = False
    logger.warning("Connection pool not available, using direct sqlite3 connections")

# Timezone handling
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python < 3.9  # noqa: E402

from pyrogram import Client  # noqa: E402
from pyrogram.errors import (  # noqa: E402
    FloodWait,
    PeerIdInvalid,
    UserBannedInChannel,
    UserBlocked,
    UserDeactivated,
    UserPrivacyRestricted,
)

logger = logging.getLogger(__name__)

# Import enhanced anti-detection if available
try:
    from anti_detection.anti_detection_system import (
        EnhancedAntiDetectionSystem,
    )

    ENHANCED_ANTI_DETECTION_AVAILABLE = True
except ImportError:
    ENHANCED_ANTI_DETECTION_AVAILABLE = False
    logger.warning("Enhanced anti-detection not available for campaigns")

# Import delivery analytics
try:
    from campaigns.delivery_analytics import get_delivery_analytics

    DELIVERY_ANALYTICS_AVAILABLE = True
except ImportError:
    DELIVERY_ANALYTICS_AVAILABLE = False
    logger.warning("Delivery analytics not available")

# Import risk monitor
try:
    from monitoring.account_risk_monitor import get_risk_monitor

    RISK_MONITOR_AVAILABLE = True
except ImportError:
    RISK_MONITOR_AVAILABLE = False
    logger.warning("Risk monitor not available")


class CampaignStatus(Enum):
    """Campaign status enumeration."""

    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class MessageStatus(Enum):
    """Individual message status."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BLOCKED = "blocked"
    PRIVACY_RESTRICTED = "privacy_restricted"
    INVALID_USER = "invalid_user"
    RATE_LIMITED = "rate_limited"


@dataclass
class Campaign:
    """Campaign data structure."""

    id: Optional[int]
    name: str
    template: str
    status: CampaignStatus
    target_channel_id: Optional[str]
    target_member_ids: List[int]
    account_ids: List[str]  # Phone numbers of accounts to use
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_targets: int
    sent_count: int
    failed_count: int
    blocked_count: int
    rate_limit_delay: int  # Seconds between messages
    max_messages_per_hour: int
    max_messages_per_account: int
    config: Dict  # Additional configuration
    # Scheduling fields
    scheduled_start: Optional[datetime] = None  # When to start the campaign
    scheduled_end: Optional[datetime] = None  # When to stop (optional)
    active_hours_start: Optional[int] = None  # Hour to start daily (0-23)
    active_hours_end: Optional[int] = None  # Hour to end daily (0-23)
    active_days: Optional[List[int]] = None  # Days of week (0=Mon, 6=Sun)
    timezone: str = "UTC"  # Timezone for scheduling
    recurring: bool = False  # Is this a recurring campaign?
    recurrence_interval: Optional[int] = None  # Days between recurrences


@dataclass
class MessageRecord:
    """Individual message record."""

    id: Optional[int]
    campaign_id: int
    user_id: int
    account_phone: str
    message_text: str
    status: MessageStatus
    sent_at: Optional[datetime]
    error_message: Optional[str]
    retry_count: int


class MessageTemplateEngine:
    """Message template engine with variable substitution."""

    # Available variables for personalization
    VARIABLES = {
        "{first_name}": "first_name",
        "{last_name}": "last_name",
        "{username}": "username",
        "{name}": "name",  # First name or username
        "{user_id}": "user_id",
    }

    @staticmethod
    def render(template: str, member: Dict) -> str:
        """Render template with member data.

        Args:
            template: Message template with variables
            member: Member data dictionary

        Returns:
            Rendered message text
        """
        # Import InputValidator for sanitization
        try:
            from utils.utils import InputValidator

            def sanitize(text):
                return InputValidator.sanitize_text(str(text), max_length=100)

        except (ImportError, AttributeError):
            # Fallback sanitization that preserves apostrophes
            import re

            def sanitize(text):
                return re.sub(r"[^\w\s@._\'-]", "", str(text))[:100]

        message = template

        # Sanitize member data before replacement
        first_name = sanitize(member.get("first_name", ""))
        last_name = sanitize(member.get("last_name", ""))
        username = sanitize(member.get("username", ""))
        user_id = str(member.get("user_id", ""))

        # Build name (first name or username)
        name = first_name if first_name else (username if username else f"User_{user_id}")

        replacements = {
            "{first_name}": first_name or "",
            "{last_name}": last_name or "",
            "{username}": username or "",
            "{name}": name,
            "{user_id}": str(user_id),
        }

        for var, value in replacements.items():
            message = message.replace(var, value)

        return message.strip()

    @staticmethod
    def validate_template(template: str) -> Tuple[bool, Optional[str]]:
        """Validate template syntax.

        Returns:
            (is_valid, error_message)
        """
        if not template or not template.strip():
            return False, "Template cannot be empty"

        # Check for unmatched braces
        open_braces = template.count("{")
        close_braces = template.count("}")
        if open_braces != close_braces:
            return False, "Unmatched braces in template"

        # Check for unknown variables
        valid_vars = set(MessageTemplateEngine.VARIABLES.keys())
        found_vars = re.findall(r"\{[^}]+\}", template)
        for var in found_vars:
            if var not in valid_vars:
                return False, f"Unknown variable: {var}"

        return True, None


class CampaignScheduler:
    """Scheduler for managing scheduled campaigns."""

    def __init__(self, campaign_manager: "DMCampaignManager"):
        """Initialize scheduler.

        Args:
            campaign_manager: DMCampaignManager instance
        """
        self.campaign_manager = campaign_manager
        self._running = False
        self._check_interval = 60  # Check every minute
        self._scheduler_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Campaign scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Campaign scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_scheduled_campaigns()
                await self._check_active_hours()
                await self._check_recurring_campaigns()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            await asyncio.sleep(self._check_interval)

    async def _check_scheduled_campaigns(self):
        """Check and start scheduled campaigns."""
        queued_campaigns = self.campaign_manager.get_campaigns_by_status(CampaignStatus.QUEUED)
        now = datetime.now()

        for campaign in queued_campaigns:
            if campaign.scheduled_start and campaign.scheduled_start <= now:
                # Check if within active hours
                if self._is_within_active_hours(campaign, now):
                    logger.info(f"Starting scheduled campaign: {campaign.name} (ID: {campaign.id})")
                    asyncio.create_task(self.campaign_manager.start_campaign(campaign.id))

    async def _check_active_hours(self):
        """Pause/resume campaigns based on active hours."""
        running_campaigns = self.campaign_manager.get_campaigns_by_status(CampaignStatus.RUNNING)
        now = datetime.now()

        for campaign in running_campaigns:
            if not self._is_within_active_hours(campaign, now):
                logger.info(f"Pausing campaign outside active hours: {campaign.name}")
                await self.campaign_manager.pause_campaign(campaign.id)

        # Resume paused campaigns that are within active hours
        paused_campaigns = self.campaign_manager.get_campaigns_by_status(CampaignStatus.PAUSED)
        for campaign in paused_campaigns:
            # Only resume if it was auto-paused for active hours (check config)
            if campaign.config.get("auto_paused_for_hours") and self._is_within_active_hours(
                campaign, now
            ):
                logger.info(f"Resuming campaign within active hours: {campaign.name}")
                await self.campaign_manager.resume_campaign(campaign.id)

    async def _check_recurring_campaigns(self):
        """Check and reschedule recurring campaigns."""
        completed_campaigns = self.campaign_manager.get_campaigns_by_status(
            CampaignStatus.COMPLETED
        )
        now = datetime.now()

        for campaign in completed_campaigns:
            if campaign.recurring and campaign.recurrence_interval:
                # Check if it's time for next recurrence
                if campaign.completed_at:
                    next_run = campaign.completed_at + timedelta(days=campaign.recurrence_interval)
                    if next_run <= now:
                        logger.info(f"Recreating recurring campaign: {campaign.name}")
                        await self._recreate_recurring_campaign(campaign)

    def _is_within_active_hours(self, campaign: Campaign, now: datetime) -> bool:
        """Check if current time is within campaign's active hours.

        Args:
            campaign: Campaign to check
            now: Current datetime

        Returns:
            True if within active hours or no hours restriction
        """
        # Convert to campaign timezone
        try:
            tz = ZoneInfo(campaign.timezone)
            local_now = (
                now.astimezone(tz)
                if now.tzinfo
                else now.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
            )
        except Exception:
            local_now = now

        # Check day of week (0=Monday in Python)
        if campaign.active_days is not None:
            if local_now.weekday() not in campaign.active_days:
                return False

        # Check active hours
        if campaign.active_hours_start is not None and campaign.active_hours_end is not None:
            current_hour = local_now.hour

            # Handle overnight schedules (e.g., 22-06)
            if campaign.active_hours_start <= campaign.active_hours_end:
                # Normal schedule (e.g., 9-17)
                if not (campaign.active_hours_start <= current_hour < campaign.active_hours_end):
                    return False
            else:
                # Overnight schedule (e.g., 22-06)
                if not (
                    current_hour >= campaign.active_hours_start
                    or current_hour < campaign.active_hours_end
                ):
                    return False

        # Check scheduled end
        if campaign.scheduled_end and now >= campaign.scheduled_end:
            return False

        return True

    async def _recreate_recurring_campaign(self, campaign: Campaign):
        """Recreate a recurring campaign for the next cycle.

        Args:
            campaign: Original completed campaign
        """
        # Calculate next scheduled start
        next_start = datetime.now() + timedelta(days=campaign.recurrence_interval)

        schedule = {
            "scheduled_start": next_start,
            "scheduled_end": campaign.scheduled_end,
            "active_hours_start": campaign.active_hours_start,
            "active_hours_end": campaign.active_hours_end,
            "active_days": campaign.active_days,
            "timezone": campaign.timezone,
            "recurring": True,
            "recurrence_interval": campaign.recurrence_interval,
        }

        # Create new campaign
        new_campaign = self.campaign_manager.create_campaign(
            name=f"{campaign.name} (Recurring)",
            template=campaign.template,
            target_member_ids=campaign.target_member_ids,
            account_ids=campaign.account_ids,
            config=campaign.config,
            schedule=schedule,
        )

        logger.info(f"Created recurring campaign: {new_campaign.name} (ID: {new_campaign.id})")

    def get_next_run_time(self, campaign: Campaign) -> Optional[datetime]:
        """Get the next time a campaign will run.

        Args:
            campaign: Campaign to check

        Returns:
            Next run datetime or None
        """
        now = datetime.now()

        if campaign.status == CampaignStatus.QUEUED and campaign.scheduled_start:
            return campaign.scheduled_start

        if campaign.status == CampaignStatus.PAUSED:
            # Find next active window
            if campaign.active_hours_start is not None:
                try:
                    tz = ZoneInfo(campaign.timezone)
                    local_now = (
                        now.astimezone(tz)
                        if now.tzinfo
                        else now.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
                    )
                except Exception:
                    local_now = now

                # Find next valid day/hour
                for days_ahead in range(8):  # Check up to 7 days ahead
                    check_date = local_now + timedelta(days=days_ahead)

                    # Check day of week
                    if campaign.active_days and check_date.weekday() not in campaign.active_days:
                        continue

                    # Return start time for this day
                    next_run = check_date.replace(
                        hour=campaign.active_hours_start, minute=0, second=0, microsecond=0
                    )

                    if next_run > local_now:
                        return next_run

        return None


class DMCampaignManager:
    """Manages DM campaigns with enhanced rate limiting and anti-detection."""

    def __init__(self, db_path: str = "campaigns.db", account_manager=None):
        """Initialize campaign manager.

        Args:
            db_path: Path to campaigns database
            account_manager: AccountManager instance for account access
        """
        self.db_path = db_path
        self.account_manager = account_manager
        self.active_campaigns: Dict[int, Campaign] = {}
        self.running_campaigns: Set[int] = set()
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.rate_limiters: Dict[str, Dict] = {}  # account_phone -> rate limiter data

        # Enhanced anti-detection integration
        self._anti_detection_system = None
        if ENHANCED_ANTI_DETECTION_AVAILABLE:
            try:
                self._anti_detection_system = EnhancedAntiDetectionSystem()
                logger.info("Enhanced anti-detection enabled for campaigns")
            except Exception as e:
                logger.warning(f"Failed to initialize anti-detection: {e}")

        # Delivery analytics integration
        self._delivery_analytics = None
        if DELIVERY_ANALYTICS_AVAILABLE:
            try:
                self._delivery_analytics = get_delivery_analytics()
                logger.info("✓ Delivery analytics enabled for campaigns")
            except Exception as e:
                logger.warning(f"Failed to initialize delivery analytics: {e}")

        # Risk monitoring integration
        self._risk_monitor = None
        if RISK_MONITOR_AVAILABLE:
            try:
                self._risk_monitor = get_risk_monitor()
                logger.info("✓ Risk monitoring enabled for campaigns")
            except Exception as e:
                logger.warning(f"Failed to initialize risk monitor: {e}")

        # Message tracking for diversity analysis
        self.messages_sent_today: Dict[str, List[str]] = {}  # account -> messages
        self.account_risk_alerts: Dict[str, List[str]] = {}  # account -> alerts
        self._messages_have_variant = False

        # Campaign scheduler
        self.scheduler = CampaignScheduler(self)

        # Initialize connection pool if available
        self._connection_pool = None
        if CONNECTION_POOL_AVAILABLE:
            try:
                self._connection_pool = get_pool(self.db_path)
                logger.info("Using connection pool for campaign database")
            except Exception as e:
                logger.warning(f"Failed to initialize connection pool: {e}")

        self.init_database()

    def _get_connection(self):
        """Get a database connection (using pool if available).

        Returns:
            Context manager for database connection
        """
        if self._connection_pool:
            return self._connection_pool.get_connection()
        else:
            # Fallback to direct connection
            return self._get_connection()

    def init_database(self):
        """Initialize campaign database schema."""
        with self._get_connection() as conn:
            # Campaigns table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    template TEXT NOT NULL,
                    status TEXT NOT NULL,
                    target_channel_id TEXT,
                    target_member_ids TEXT,  -- JSON array
                    account_ids TEXT,  -- JSON array of phone numbers
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    total_targets INTEGER DEFAULT 0,
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    blocked_count INTEGER DEFAULT 0,
                    rate_limit_delay INTEGER DEFAULT 5,
                    max_messages_per_hour INTEGER DEFAULT 20,
                    max_messages_per_account INTEGER DEFAULT 100,
                    config TEXT,  -- JSON
                    scheduled_start TIMESTAMP,
                    scheduled_end TIMESTAMP,
                    active_hours_start INTEGER,
                    active_hours_end INTEGER,
                    active_days TEXT,  -- JSON array of weekday numbers
                    timezone TEXT DEFAULT 'UTC',
                    recurring INTEGER DEFAULT 0,
                    recurrence_interval INTEGER
                )
            """
            )

            # Add scheduling columns to existing tables (migration) with explicit checks
            try:
                col_rows = conn.execute("PRAGMA table_info(campaigns)").fetchall()
                existing_cols = {row[1] for row in col_rows}
            except Exception:
                existing_cols = set()

            def add_column(col_def: str, name: str):
                if name in existing_cols:
                    return
                try:
                    conn.execute(f"ALTER TABLE campaigns ADD COLUMN {col_def}")
                except sqlite3.OperationalError:
                    pass

            add_column("scheduled_start TIMESTAMP", "scheduled_start")
            add_column("scheduled_end TIMESTAMP", "scheduled_end")
            add_column("active_hours_start INTEGER", "active_hours_start")
            add_column("active_hours_end INTEGER", "active_hours_end")
            add_column("active_days TEXT", "active_days")
            add_column("timezone TEXT DEFAULT 'UTC'", "timezone")
            add_column("recurring INTEGER DEFAULT 0", "recurring")
            add_column("recurrence_interval INTEGER", "recurrence_interval")

            # Messages table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS campaign_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER,
                    user_id INTEGER,
                    account_phone TEXT,
                    message_text TEXT,
                    status TEXT NOT NULL,
                    sent_at TIMESTAMP,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    template_variant TEXT,
                    FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                    UNIQUE(campaign_id, user_id)
                )
            """
            )

            # Indexes
            # Optimized indexes for campaign performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_campaign_status ON campaigns(status)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_campaign_created_at ON campaigns(created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_campaign_scheduled_start ON "
                "campaigns(scheduled_start)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_campaign_account ON campaigns(account_ids)"
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_campaign ON campaign_messages(campaign_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_status ON campaign_messages(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_user ON campaign_messages(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON campaign_messages(sent_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_account ON "
                "campaign_messages(account_phone)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_variant ON "
                "campaign_messages(template_variant)"
            )

            self._ensure_message_schema(conn)

    def _ensure_message_schema(self, conn: sqlite3.Connection):
        """Backfill missing columns for message analytics."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(campaign_messages)")
        columns = {row[1] for row in cursor.fetchall()}

        if "template_variant" not in columns:
            try:
                cursor.execute("ALTER TABLE campaign_messages ADD COLUMN template_variant TEXT")
                conn.commit()
                columns.add("template_variant")
            except sqlite3.OperationalError as exc:
                logger.warning(f"Failed to add template_variant column: {exc}")

        self._messages_have_variant = "template_variant" in columns

        # Composite indexes for complex queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_campaign_status ON "
            "campaign_messages(campaign_id, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_campaign_status_created ON "
            "campaigns(status, created_at DESC)"
        )

        conn.commit()

    def create_campaign(
        self,
        name: str,
        template: str,
        target_member_ids: List[int],
        account_ids: List[str],
        config: Dict = None,
        schedule: Dict = None,
    ) -> Campaign:
        """Create a new campaign with optional scheduling.

        Args:
            name: Campaign name
            template: Message template
            target_member_ids: List of user IDs to message
            account_ids: List of account phone numbers to use
            config: Additional configuration
            schedule: Scheduling configuration:
                - scheduled_start: datetime - When to start
                - scheduled_end: datetime - When to stop (optional)
                - active_hours_start: int (0-23) - Hour to start daily
                - active_hours_end: int (0-23) - Hour to end daily
                - active_days: List[int] - Days of week (0=Mon, 6=Sun)
                - timezone: str - Timezone name (default UTC)
                - recurring: bool - Is recurring campaign
                - recurrence_interval: int - Days between recurrences

        Returns:
            Created Campaign object
        """
        # Comprehensive input validation
        try:
            from user_helpers import ValidationHelper

            # Validate campaign name
            if not name or not isinstance(name, str):
                raise ValueError("Campaign name is required and must be a string")
            name = name.strip()
            if len(name) < 3 or len(name) > 100:
                raise ValueError("Campaign name must be between 3 and 100 characters")
            if not name.replace(" ", "").replace("-", "").replace("_", "").isalnum():
                raise ValueError(
                    "Campaign name can only contain letters, numbers, spaces, "
                    "hyphens, and underscores"
                )

            # Validate template
            if not template or not isinstance(template, str):
                raise ValueError("Message template is required and must be a string")
            template = template.strip()
            if len(template) < 10:
                raise ValueError("Message template must be at least 10 characters long")

            is_valid, error = MessageTemplateEngine.validate_template(template)
            if not is_valid:
                raise ValueError(f"Invalid template: {error}")

            # Validate target member IDs
            if not target_member_ids or not isinstance(target_member_ids, list):
                raise ValueError("Target member IDs must be a non-empty list")
            if len(target_member_ids) > 10000:
                raise ValueError("Cannot target more than 10,000 members in a single campaign")
            for member_id in target_member_ids:
                if not isinstance(member_id, int) or member_id <= 0:
                    raise ValueError(f"Invalid member ID: {member_id}. Must be a positive integer")

            # Validate account IDs
            if not account_ids or not isinstance(account_ids, list):
                raise ValueError("Account IDs must be a non-empty list")
            if len(account_ids) > 50:
                raise ValueError("Cannot use more than 50 accounts in a single campaign")
            for account_id in account_ids:
                if not isinstance(account_id, str):
                    raise ValueError(f"Account ID must be a string: {account_id}")
                is_valid, error_msg = ValidationHelper.validate_phone_number(account_id)
                if not is_valid:
                    raise ValueError(f"Invalid account phone number '{account_id}': {error_msg}")

            # Validate config
            if config is not None and not isinstance(config, dict):
                raise ValueError("Config must be a dictionary or None")

            # Validate schedule
            if schedule is not None and not isinstance(schedule, dict):
                raise ValueError("Schedule must be a dictionary or None")

        except ImportError:
            # Skip validation if ValidationHelper not available
            logger.warning("ValidationHelper not available, using basic validation")

            # Basic validation fallback
            if not name or not isinstance(name, str):
                raise ValueError("Campaign name is required and must be a string") from None
            if not template or not isinstance(template, str):
                raise ValueError("Message template is required and must be a string") from None
            if not target_member_ids or not isinstance(target_member_ids, list):
                raise ValueError("Target member IDs must be a non-empty list") from None
            if not account_ids or not isinstance(account_ids, list):
                raise ValueError("Account IDs must be a non-empty list") from None

        if not account_ids:
            raise ValueError("At least one account must be specified")

        if not target_member_ids:
            raise ValueError("At least one target member must be specified")

        config = config or {}
        schedule = schedule or {}

        # Parse schedule
        scheduled_start = schedule.get("scheduled_start")
        scheduled_end = schedule.get("scheduled_end")
        active_hours_start = schedule.get("active_hours_start")
        active_hours_end = schedule.get("active_hours_end")
        active_days = schedule.get("active_days")
        timezone = schedule.get("timezone", "UTC")
        recurring = schedule.get("recurring", False)
        recurrence_interval = schedule.get("recurrence_interval")

        # Validate schedule
        if active_hours_start is not None and (active_hours_start < 0 or active_hours_start > 23):
            raise ValueError("active_hours_start must be between 0 and 23")
        if active_hours_end is not None and (active_hours_end < 0 or active_hours_end > 23):
            raise ValueError("active_hours_end must be between 0 and 23")
        if active_days is not None:
            if not all(0 <= d <= 6 for d in active_days):
                raise ValueError("active_days must contain values 0-6 (Mon-Sun)")

        # Determine initial status
        initial_status = CampaignStatus.DRAFT
        if scheduled_start and scheduled_start > datetime.now():
            initial_status = CampaignStatus.QUEUED

        campaign = Campaign(
            id=None,
            name=name,
            template=template,
            status=initial_status,
            target_channel_id=config.get("channel_id"),
            target_member_ids=target_member_ids,
            account_ids=account_ids,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            total_targets=len(target_member_ids),
            sent_count=0,
            failed_count=0,
            blocked_count=0,
            rate_limit_delay=config.get("rate_limit_delay", 5),
            max_messages_per_hour=config.get("max_messages_per_hour", 20),
            max_messages_per_account=config.get("max_messages_per_account", 100),
            config=config,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            active_hours_start=active_hours_start,
            active_hours_end=active_hours_end,
            active_days=active_days,
            timezone=timezone,
            recurring=recurring,
            recurrence_interval=recurrence_interval,
        )

        # Save to database
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO campaigns
                (
                    name,
                    template,
                    status,
                    target_channel_id,
                    target_member_ids,
                    account_ids,
                    total_targets,
                    rate_limit_delay,
                    max_messages_per_hour,
                    max_messages_per_account,
                    config,
                    scheduled_start,
                    scheduled_end,
                    active_hours_start,
                    active_hours_end,
                    active_days,
                 timezone, recurring, recurrence_interval)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    campaign.name,
                    campaign.template,
                    campaign.status.value,
                    campaign.target_channel_id,
                    json.dumps(campaign.target_member_ids),
                    json.dumps(campaign.account_ids),
                    campaign.total_targets,
                    campaign.rate_limit_delay,
                    campaign.max_messages_per_hour,
                    campaign.max_messages_per_account,
                    json.dumps(campaign.config),
                    campaign.scheduled_start.isoformat() if campaign.scheduled_start else None,
                    campaign.scheduled_end.isoformat() if campaign.scheduled_end else None,
                    campaign.active_hours_start,
                    campaign.active_hours_end,
                    json.dumps(campaign.active_days) if campaign.active_days else None,
                    campaign.timezone,
                    1 if campaign.recurring else 0,
                    campaign.recurrence_interval,
                ),
            )
            campaign.id = cursor.lastrowid
            conn.commit()

        self.active_campaigns[campaign.id] = campaign
        logger.info(
            f"Created campaign: {campaign.name} (ID: {campaign.id}), status: {initial_status.value}"
        )
        return campaign

    def _select_template_variant(self, campaign: Campaign, user_id: int) -> Tuple[str, str]:
        """Select which template variant to send and return (template, label)."""
        config = campaign.config or {}
        variant_config = config.get("template_variants") or config.get("templates") or []

        parsed_variants = []
        for idx, entry in enumerate(variant_config):
            if isinstance(entry, dict):
                template_text = entry.get("template")
                if not template_text:
                    continue
                label = entry.get("name") or entry.get("label") or f"variant_{idx + 1}"
                try:
                    weight = float(entry.get("weight", 1.0))
                except (TypeError, ValueError):
                    weight = 1.0
                weight = max(weight, 0.0)
                parsed_variants.append((template_text, label, weight))

        if not parsed_variants:
            default_label = config.get("template_label", "default")
            return campaign.template, default_label

        total_weight = sum(v[2] for v in parsed_variants) or len(parsed_variants)
        chooser = random.Random(user_id)
        roll = chooser.uniform(0, total_weight)

        cumulative = 0.0
        for template_text, label, weight in parsed_variants:
            cumulative += weight or 1.0
            if roll <= cumulative:
                return template_text, label

        # Fallback to last variant if rounding issues occur
        fallback_template, fallback_label, _ = parsed_variants[-1]
        return fallback_template, fallback_label

    async def start_campaign(self, campaign_id: int) -> bool:
        """Start a campaign.

        Args:
            campaign_id: Campaign ID

        Returns:
            True if started successfully
        """
        if campaign_id not in self.active_campaigns:
            # Load from database
            campaign = self._load_campaign(campaign_id)
            if not campaign:
                return False
            self.active_campaigns[campaign_id] = campaign

        campaign = self.active_campaigns[campaign_id]

        if campaign.status != CampaignStatus.DRAFT and campaign.status != CampaignStatus.PAUSED:
            logger.warning(
                f"Campaign {campaign_id} cannot be started from status {campaign.status}"
            )
            return False

        # Update status
        campaign.status = CampaignStatus.RUNNING
        campaign.started_at = datetime.now()

        # Update database
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE campaigns
                SET status = ?, started_at = ?
                WHERE id = ?
            """,
                (CampaignStatus.RUNNING.value, campaign.started_at, campaign_id),
            )
            conn.commit()

        # Start campaign task
        self.running_campaigns.add(campaign_id)
        asyncio.create_task(self._run_campaign(campaign_id))

        logger.info(f"Started campaign: {campaign.name} (ID: {campaign_id})")
        return True

    async def _run_campaign(self, campaign_id: int):
        """Run a campaign (internal method)."""
        try:
            campaign = self.active_campaigns[campaign_id]

            # Get member data from database
            from scraping.member_scraper import MemberDatabase

            member_db = MemberDatabase("members.db")

            # Get account clients - ensure accounts are started
            account_clients = {}
            for account_phone in campaign.account_ids:
                if self.account_manager:
                    # Ensure client is started
                    if account_phone not in self.account_manager.active_clients:
                        logger.info(f"Starting client for {account_phone}...")
                        await self.account_manager.start_client(account_phone)

                    # Get client from account manager
                    if account_phone in self.account_manager.active_clients:
                        telegram_client = self.account_manager.active_clients[account_phone]
                        # Get the actual Pyrogram client
                        if hasattr(telegram_client, "client"):
                            account_clients[account_phone] = telegram_client.client
                        elif hasattr(telegram_client, "get_client"):
                            account_clients[account_phone] = telegram_client.get_client()
                        else:
                            account_clients[account_phone] = telegram_client

            if not account_clients:
                logger.error(f"No available accounts for campaign {campaign_id}")
                campaign.status = CampaignStatus.ERROR
                self._update_campaign_progress(campaign_id, campaign)
                return

            # Initialize rate limiters for each account
            for account_phone in account_clients.keys():
                self._init_rate_limiter(account_phone, campaign)

            # Create a queue of remaining targets (will be modified as we process)
            remaining_targets = list(campaign.target_member_ids)

            # Track which account messaged which user (for reply handling)
            account_user_mapping = {}  # user_id -> account_phone

            # CONCURRENT PROCESSING: Use a shared queue and process with all accounts simultaneously
            from asyncio import Lock

            # Create a lock for thread-safe access to remaining_targets and campaign stats
            targets_lock = Lock()

            async def process_account_targets(account_phone: str, client: Client):
                """Process targets for a specific account concurrently."""
                processed_count = 0

                # Pre-load member data for all targets to avoid N+1 queries
                # Process in batches of 50 for memory efficiency
                batch_size = 50
                member_cache = {}

                while campaign.status == CampaignStatus.RUNNING:
                    # Get batch of targets (thread-safe)
                    async with targets_lock:
                        if not remaining_targets:
                            break
                        # Take up to batch_size targets
                        batch_targets = []
                        for _ in range(min(batch_size, len(remaining_targets))):
                            if remaining_targets:
                                batch_targets.append(remaining_targets.pop(0))

                    if not batch_targets:
                        break

                    # Load member data for this batch efficiently
                    batch_members = member_db.get_members_batch(batch_targets)
                    # Create lookup dictionary for O(1) access
                    member_cache.update({m["user_id"]: m for m in batch_members})

                    # Process each target in the batch
                    for user_id in batch_targets:
                        # Check rate limits for this account
                        await self._check_rate_limits(account_phone, campaign)

                        # Get member data from cache (O(1) lookup)
                        member = member_cache.get(user_id)

                        template_text, template_label = self._select_template_variant(
                            campaign, user_id
                        )

                        if not member:
                            logger.warning(f"Member {user_id} not found in database")
                            self._record_message(
                                campaign_id,
                                user_id,
                                account_phone,
                                "",
                                MessageStatus.INVALID_USER,
                                "Member not found",
                                template_variant=template_label,
                            )
                            async with targets_lock:
                                campaign.failed_count += 1
                            continue

                        # Render message
                        message_text = MessageTemplateEngine.render(template_text, member)

                        # Send message
                        success = await self._send_message(
                            client,
                            campaign_id,
                            user_id,
                            account_phone,
                            message_text,
                            campaign,
                            template_label,
                        )

                        # Update campaign stats (thread-safe)
                        async with targets_lock:
                            if success:
                                campaign.sent_count += 1
                                # Track which account messaged this user (for reply handling)
                                account_user_mapping[user_id] = account_phone
                            else:
                                campaign.failed_count += 1

                        processed_count += 1
                        total_processed = campaign.sent_count + campaign.failed_count

                        # Update progress periodically
                        if total_processed % 10 == 0:
                            # Schedule update in background to avoid blocking
                            asyncio.create_task(
                                self._update_campaign_progress_async(campaign_id, campaign)
                            )

                        # Mark user as messaged in database (outside lock, non-blocking)
                        if success:
                            self._mark_user_as_messaged(user_id, account_phone, campaign_id)

                        # Rate limiting delay (per account) - allows other accounts to continue
                        delay = campaign.rate_limit_delay + random.uniform(-1, 1)
                        await asyncio.sleep(delay)

            # Start concurrent tasks for ALL accounts - they all work simultaneously
            tasks = [
                process_account_targets(account_phone, client)
                for account_phone, client in account_clients.items()
            ]

            # Run all accounts concurrently - TRUE PARALLEL PROCESSING
            await asyncio.gather(*tasks, return_exceptions=True)

            # Store account-user mapping for reply handling
            campaign.config["account_user_mapping"] = account_user_mapping
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE campaigns SET config = ? WHERE id = ?",
                    (json.dumps(campaign.config), campaign_id),
                )
                conn.commit()

            logger.info(
                f"Campaign {campaign_id}: Account-user mapping stored for "
                f"{len(account_user_mapping)} users"
            )

            # Mark campaign as completed
            campaign.status = CampaignStatus.COMPLETED
            campaign.completed_at = datetime.now()
            self._update_campaign_progress(campaign_id, campaign)
            self.running_campaigns.discard(campaign_id)

            logger.info(
                f"Campaign {campaign_id} completed: "
                f"{campaign.sent_count} sent, {campaign.failed_count} failed"
            )

        except Exception as e:
            logger.error(f"Error running campaign {campaign_id}: {e}", exc_info=True)
            campaign = self.active_campaigns.get(campaign_id)
            if campaign:
                campaign.status = CampaignStatus.ERROR
                self._update_campaign_progress(campaign_id, campaign)
            self.running_campaigns.discard(campaign_id)

    async def _send_message(
        self,
        client: Client,
        campaign_id: int,
        user_id: int,
        account_phone: str,
        message_text: str,
        campaign: Campaign,
        template_variant: str,
    ) -> bool:
        """Send a message to a user with enhanced anti-detection and risk monitoring.

        Returns:
            True if sent successfully
        """
        # Idempotency check: Skip if already sent successfully
        if self._is_message_already_sent(campaign_id, user_id):
            logger.debug(f"Skipping duplicate send: campaign {campaign_id}, user {user_id}")
            return False

        # Check account risk before sending
        if self._risk_monitor:
            try:
                # Get FloodWait count from our tracking
                floodwait_count = self._get_account_floodwait_count(account_phone)

                # Calculate current risk
                risk_score = self._risk_monitor.calculate_risk_score(
                    phone_number=account_phone,
                    floodwaits_24h=floodwait_count,
                    errors_24h=(
                        self.account_risk_alerts.get(account_phone, [])[:24].__len__()
                        if account_phone in self.account_risk_alerts
                        else 0
                    ),
                    messages_1h=(
                        len(list(self.messages_sent_today.get(account_phone, [])))
                        if account_phone in self.messages_sent_today
                        else 0
                    ),
                    has_shadowban=False,  # Would check shadowban detector
                )

                # Save risk score
                self._risk_monitor.save_risk_score(risk_score)

                # Block if should quarantine
                if risk_score.should_quarantine:
                    logger.critical(
                        f"🚨 Account {account_phone} risk score {risk_score.overall_score} - "
                        f"QUARANTINE RECOMMENDED. Blocking message send and pausing campaign."
                    )

                    # Auto-pause campaign
                    try:
                        campaign_obj = self.get_campaign(campaign_id)
                        if campaign_obj and campaign_obj.status == CampaignStatus.RUNNING:
                            campaign_obj.status = CampaignStatus.PAUSED
                            campaign_obj.config["auto_paused_reason"] = (
                                f"Account {account_phone} quarantined "
                                f"(risk: {risk_score.overall_score})"
                            )
                            campaign_obj.config["auto_paused_at"] = datetime.now().isoformat()
                            self._update_campaign_progress(campaign_id, campaign_obj)
                            logger.warning(
                                f"🛑 Auto-paused campaign {campaign_id} due to account quarantine"
                            )
                    except Exception as e:
                        logger.error(f"Failed to auto-pause campaign: {e}")

                    self._record_message(
                        campaign_id,
                        user_id,
                        account_phone,
                        message_text,
                        MessageStatus.FAILED,
                        f"Account quarantined (risk score: {risk_score.overall_score})",
                        template_variant=template_variant,
                    )
                    return False

                # Warn on high risk
                if risk_score.overall_score > 60:
                    logger.warning(
                        f"⚠️ Account {account_phone} risk score "
                        f"{risk_score.overall_score} - HIGH RISK. "
                        f"Recommendations: {'; '.join(risk_score.recommended_actions[:2])}"
                    )

            except Exception as e:
                logger.debug(f"Could not check account risk: {e}")

        max_length = (
            campaign.config.get("max_message_length", 4096)
            if campaign and campaign.config
            else 4096
        )
        if len(message_text) > max_length:
            logger.warning(
                f"Message length {len(message_text)} exceeds platform max; trimming to {max_length}"
            )
            message_text = message_text[:max_length]
            self._record_message(
                campaign_id,
                user_id,
                account_phone,
                message_text,
                MessageStatus.FAILED,
                f"Message exceeded max length {max_length}",
                template_variant=template_variant,
            )
            return False

        # Check with anti-detection system first
        if self._anti_detection_system:
            can_send, delay, reason = self._anti_detection_system.can_send_message(account_phone)

            if not can_send:
                logger.warning(f"Anti-detection blocked message from {account_phone}: {reason}")
                self._record_message(
                    campaign_id,
                    user_id,
                    account_phone,
                    message_text,
                    MessageStatus.RATE_LIMITED,
                    f"Anti-detection: {reason}",
                    template_variant=template_variant,
                )
                return False

            if delay > 0:
                logger.info(f"Anti-detection delay for {account_phone}: {delay:.1f}s")
                await asyncio.sleep(delay)

        try:
            sent = await client.send_message(user_id, message_text)

            # Record success in anti-detection
            if self._anti_detection_system:
                self._anti_detection_system.record_message_sent(
                    account_phone, message_text, user_id
                )

            # Track for diversity analysis
            if account_phone not in self.messages_sent_today:
                self.messages_sent_today[account_phone] = []
            self.messages_sent_today[account_phone].append(message_text)

            # Record success
            self._record_message(
                campaign_id,
                user_id,
                account_phone,
                message_text,
                MessageStatus.SENT,
                None,
                datetime.now(),
                template_variant,
            )

            # Record in delivery analytics for tracking
            if self._delivery_analytics:
                try:
                    self._delivery_analytics.record_message_sent(
                        message_id=sent.id if hasattr(sent, "id") else 0,
                        campaign_id=campaign_id,
                        user_id=user_id,
                        account_phone=account_phone,
                        sent_at=datetime.now(),
                    )
                except Exception as e:
                    logger.debug(f"Could not record delivery analytics: {e}")

            # Update rate limiter
            self._update_rate_limiter(account_phone)

            # Check account health after message
            await self._check_account_health(account_phone, campaign)

            return True

        except FloodWait as e:
            # Rate limited - record error and wait with actionable guidance
            wait_time = e.value

            # Provide actionable guidance to operators
            guidance = self._get_floodwait_guidance(wait_time, account_phone)
            logger.warning(
                f"⚠️ FloodWait for account {account_phone}: {wait_time}s\n"
                f"   Guidance: {guidance}"
            )

            # Record in anti-detection with guidance
            if self._anti_detection_system:
                self._anti_detection_system.record_error(
                    account_phone, "FloodWait", f"{str(e)} | Guidance: {guidance}"
                )

            # Store FloodWait event for analytics and operator visibility
            self._record_floodwait_event(account_phone, wait_time, campaign_id, guidance)

            await asyncio.sleep(wait_time + random.randint(5, 15))  # Add jitter

            self._record_message(
                campaign_id,
                user_id,
                account_phone,
                message_text,
                MessageStatus.RATE_LIMITED,
                f"FloodWait: {wait_time}s | {guidance}",
                template_variant=template_variant,
            )
            return False

        except (UserBlocked, UserPrivacyRestricted) as e:
            # User blocked or privacy restricted
            if self._anti_detection_system:
                self._anti_detection_system.record_error(account_phone, type(e).__name__, str(e))

            status = (
                MessageStatus.BLOCKED
                if isinstance(e, UserBlocked)
                else MessageStatus.PRIVACY_RESTRICTED
            )
            self._record_message(
                campaign_id,
                user_id,
                account_phone,
                message_text,
                status,
                str(e),
                template_variant=template_variant,
            )
            campaign.blocked_count += 1
            return False

        except (PeerIdInvalid, UserDeactivated, UserBannedInChannel) as e:
            # Invalid user
            if self._anti_detection_system:
                self._anti_detection_system.record_error(account_phone, type(e).__name__, str(e))

            self._record_message(
                campaign_id,
                user_id,
                account_phone,
                message_text,
                MessageStatus.INVALID_USER,
                str(e),
                template_variant=template_variant,
            )
            return False

        except Exception as e:
            # Other error
            logger.error(f"Error sending message to {user_id}: {e}")

            if self._anti_detection_system:
                self._anti_detection_system.record_error(account_phone, type(e).__name__, str(e))

            self._record_message(
                campaign_id,
                user_id,
                account_phone,
                message_text,
                MessageStatus.FAILED,
                str(e),
                template_variant=template_variant,
            )
            return False

    async def _check_account_health(self, account_phone: str, campaign: Campaign):
        """Check account health after message and handle high-risk accounts."""
        if not self._anti_detection_system:
            return

        status = self._anti_detection_system.get_account_status(account_phone)

        if status.get("risk_level") == "critical":
            # Remove from campaign temporarily
            logger.warning(f"Account {account_phone} in critical state - removing from campaign")
            if account_phone in campaign.account_ids:
                campaign.account_ids.remove(account_phone)

            # Add alert
            if account_phone not in self.account_risk_alerts:
                self.account_risk_alerts[account_phone] = []
            self.account_risk_alerts[account_phone].append(
                f"Critical risk at {datetime.now().isoformat()} - removed from campaign"
            )

        elif status.get("risk_level") == "high":
            # Add extra delay for high-risk accounts
            logger.info(f"Account {account_phone} at high risk - adding extra delay")
            await asyncio.sleep(random.uniform(30, 60))

    def get_campaign_risk_report(self, campaign_id: int) -> Dict[str, Any]:
        """Get risk report for a campaign.

        Returns:
            Dictionary with risk analysis
        """
        campaign = self.active_campaigns.get(campaign_id)
        if not campaign:
            return {"error": "Campaign not found"}

        report = {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "accounts": [],
            "overall_risk": "low",
            "recommendations": [],
        }

        if not self._anti_detection_system:
            report["warning"] = "Anti-detection system not available"
            return report

        high_risk_count = 0
        for account_phone in campaign.account_ids:
            status = self._anti_detection_system.get_account_status(account_phone)

            account_report = {
                "phone": account_phone,
                "risk_level": status.get("risk_level", "unknown"),
                "ban_probability": status.get("ban_probability", 0),
                "message_diversity": status.get("message_diversity_score", 1.0),
                "is_quarantined": status.get("is_quarantined", False),
                "alerts": self.account_risk_alerts.get(account_phone, []),
            }

            report["accounts"].append(account_report)

            if status.get("risk_level") in ["high", "critical"]:
                high_risk_count += 1

        # Determine overall risk
        if high_risk_count > len(campaign.account_ids) * 0.5:
            report["overall_risk"] = "critical"
            report["recommendations"].append("Pause campaign immediately")
            report["recommendations"].append("Review message templates for diversity")
        elif high_risk_count > 0:
            report["overall_risk"] = "high"
            report["recommendations"].append("Consider reducing message frequency")
            report["recommendations"].append("Add more message template variations")

        return report

    def _init_rate_limiter(self, account_phone: str, campaign: Campaign):
        """Initialize rate limiter for an account."""
        self.rate_limiters[account_phone] = {
            "messages_sent": 0,
            "hour_start": datetime.now(),
            "messages_this_hour": 0,
            "max_per_hour": campaign.max_messages_per_hour,
            "max_per_account": campaign.max_messages_per_account,
        }

    async def _check_rate_limits(self, account_phone: str, campaign: Campaign):
        """Check and enforce rate limits."""
        if account_phone not in self.rate_limiters:
            self._init_rate_limiter(account_phone, campaign)

        limiter = self.rate_limiters[account_phone]

        # Check hourly limit
        now = datetime.now()
        if (now - limiter["hour_start"]).total_seconds() > 3600:
            # Reset hourly counter
            limiter["hour_start"] = now
            limiter["messages_this_hour"] = 0

        if limiter["messages_this_hour"] >= limiter["max_per_hour"]:
            # Wait until next hour
            wait_time = 3600 - (now - limiter["hour_start"]).total_seconds()
            logger.info(
                f"Hourly limit reached for {account_phone}, "
                f"waiting {wait_time:.0f}s"
            )
            await asyncio.sleep(wait_time)
            limiter["hour_start"] = datetime.now()
            limiter["messages_this_hour"] = 0

        # Check account total limit
        if limiter["messages_sent"] >= limiter["max_per_account"]:
            logger.warning(f"Account {account_phone} reached message limit")
            # Could switch to another account here

    def _update_rate_limiter(self, account_phone: str):
        """Update rate limiter after sending message."""
        if account_phone in self.rate_limiters:
            self.rate_limiters[account_phone]["messages_sent"] += 1
            self.rate_limiters[account_phone]["messages_this_hour"] += 1

    def _is_message_already_sent(self, campaign_id: int, user_id: int) -> bool:
        """Check if message already sent to prevent duplicates."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM campaign_messages WHERE campaign_id = ? "
                    "AND user_id = ? AND status = ? LIMIT 1",
                    (campaign_id, user_id, MessageStatus.SENT.value),
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking message duplicate: {e}")
            return False

    def _record_message(
        self,
        campaign_id: int,
        user_id: int,
        account_phone: Optional[str],
        message_text: str,
        status: MessageStatus,
        error_message: Optional[str] = None,
        sent_at: Optional[datetime] = None,
        template_variant: str = "default",
    ):
        """Record a message in the database with idempotency support."""
        template_variant = template_variant or "default"
        with self._get_connection() as conn:
            if self._messages_have_variant:
                conn.execute(
                    """
                    INSERT INTO campaign_messages
                    (
                        campaign_id,
                        user_id,
                        account_phone,
                        message_text,
                        status,
                        sent_at,
                        error_message,
                        template_variant,
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(campaign_id, user_id) DO UPDATE SET
                        account_phone = excluded.account_phone,
                        status = excluded.status,
                        sent_at = excluded.sent_at,
                        error_message = excluded.error_message,
                        retry_count = retry_count + 1
                    """,
                    (
                        campaign_id,
                        user_id,
                        account_phone,
                        message_text,
                        status.value,
                        sent_at,
                        error_message,
                        template_variant,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO campaign_messages
                    (
                        campaign_id, user_id, account_phone, message_text,
                        status, sent_at, error_message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(campaign_id, user_id) DO UPDATE SET
                        account_phone = excluded.account_phone,
                        status = excluded.status,
                        sent_at = excluded.sent_at,
                        error_message = excluded.error_message,
                        retry_count = retry_count + 1
                    """,
                    (
                        campaign_id,
                        user_id,
                        account_phone,
                        message_text,
                        status.value,
                        sent_at,
                        error_message,
                    ),
                )
            conn.commit()

    def _mark_user_as_messaged(self, user_id: int, account_phone: str, campaign_id: int):
        """Mark user as messaged in member database and track for reply handling."""
        try:
            # Update member database to mark as messaged
            from scraping.member_scraper import MemberDatabase

            member_db = MemberDatabase("members.db")

            # Get member efficiently
            member = member_db.get_member_by_id(user_id)

            if member:
                # Update member with messaging info
                channel_id = member.get("channel_id")
                member_db.save_member(
                    user_id=user_id,
                    username=member.get("username"),
                    first_name=member.get("first_name"),
                    last_name=member.get("last_name"),
                    phone=member.get("phone"),
                    joined_at=member.get("joined_at"),
                    last_seen=member.get("last_seen"),
                    status=member.get("status"),
                    channel_id=channel_id,
                    activity_score=member.get("activity_score", 0),
                    threat_score=member.get("threat_score", 0),
                    is_admin=member.get("is_admin", False),
                    is_moderator=member.get("is_moderator", False),
                    is_owner=member.get("is_owner", False),
                    message_count=member.get("message_count", 0),
                    last_message_date=member.get("last_message_date"),
                    is_safe_target=member.get("is_safe_target", True),
                    threat_reasons=member.get("threat_reasons"),
                )

            # Store account-user mapping in campaign config for reply handling
            campaign = self.get_campaign(campaign_id)
            if campaign:
                if "account_user_mapping" not in campaign.config:
                    campaign.config["account_user_mapping"] = {}
                campaign.config["account_user_mapping"][user_id] = account_phone
                # Update in database
                with self._get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE campaigns SET config = ? WHERE id = ?
                    """,
                        (json.dumps(campaign.config), campaign_id),
                    )
                    conn.commit()

        except Exception as e:
            logger.error(f"Error marking user as messaged: {e}")

    def get_account_for_user(self, user_id: int, campaign_id: int) -> Optional[str]:
        """Get which account messaged a specific user (for reply handling).

        Returns:
            Account phone number or None
        """
        campaign = self.get_campaign(campaign_id)
        if campaign and "account_user_mapping" in campaign.config:
            return campaign.config["account_user_mapping"].get(user_id)
        return None

    def is_user_in_campaign(self, user_id: int) -> Optional[int]:
        """Check if a user is part of any active campaign.

        Returns:
            Campaign ID or None
        """
        campaigns = self.get_all_campaigns()
        for campaign in campaigns:
            if user_id in campaign.target_member_ids:
                return campaign.id
        return None

    def _update_campaign_progress(self, campaign_id: int, campaign: Campaign):
        """Update campaign progress in database."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE campaigns
                SET status = ?, sent_count = ?, failed_count = ?, blocked_count = ?,
                    completed_at = ?
                WHERE id = ?
            """,
                (
                    campaign.status.value,
                    campaign.sent_count,
                    campaign.failed_count,
                    campaign.blocked_count,
                    campaign.completed_at,
                    campaign_id,
                ),
            )
            conn.commit()

    async def _update_campaign_progress_async(self, campaign_id: int, campaign: Campaign):
        """Async wrapper for updating campaign progress."""
        # Run in thread pool to avoid blocking
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, this shouldn't happen in async context
            logger.error("No running event loop in async function")
            raise
        await loop.run_in_executor(None, self._update_campaign_progress, campaign_id, campaign)

    def _load_campaign(self, campaign_id: int) -> Optional[Campaign]:
        """Load campaign from database."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
            row = cursor.fetchone()
            if not row:
                return None

            return Campaign(
                id=row[0],
                name=row[1],
                template=row[2],
                status=CampaignStatus(row[3]),
                target_channel_id=row[4],
                target_member_ids=json.loads(row[5] or "[]"),
                account_ids=json.loads(row[6] or "[]"),
                created_at=datetime.fromisoformat(row[7]) if row[7] else datetime.now(),
                started_at=datetime.fromisoformat(row[8]) if row[8] else None,
                completed_at=datetime.fromisoformat(row[9]) if row[9] else None,
                total_targets=row[10],
                sent_count=row[11],
                failed_count=row[12],
                blocked_count=row[13],
                rate_limit_delay=row[14],
                max_messages_per_hour=row[15],
                max_messages_per_account=row[16],
                config=json.loads(row[17] or "{}"),
            )

    def get_campaign(self, campaign_id: int) -> Optional[Campaign]:
        """Get campaign by ID."""
        if campaign_id in self.active_campaigns:
            return self.active_campaigns[campaign_id]
        return self._load_campaign(campaign_id)

    def get_all_campaigns(self) -> List[Campaign]:
        """Get all campaigns. Optimized to avoid N+1 queries."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM campaigns
                ORDER BY created_at DESC
            """
            )
            rows = cursor.fetchall()

        campaigns = []
        for row in rows:
            campaign = self._row_to_campaign(row)
            # Update cache
            self.active_campaigns[campaign.id] = campaign
            campaigns.append(campaign)

        return campaigns

    def get_campaign_stats(self, campaign_id: int) -> Dict:
        """Get campaign statistics."""
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return {}

        with self._get_connection() as conn:
            # Get message status counts
            cursor = conn.execute(
                """
                SELECT status, COUNT(*)
                FROM campaign_messages
                WHERE campaign_id = ?
                GROUP BY status
            """,
                (campaign_id,),
            )
            status_counts = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "campaign_id": campaign_id,
            "name": campaign.name,
            "status": campaign.status.value,
            "total_targets": campaign.total_targets,
            "sent": campaign.sent_count,
            "failed": campaign.failed_count,
            "blocked": campaign.blocked_count,
            "progress": (
                (campaign.sent_count + campaign.failed_count) / campaign.total_targets * 100
                if campaign.total_targets > 0
                else 0
            ),
            "status_breakdown": status_counts,
        }

    async def pause_campaign(self, campaign_id: int):
        """Pause a running campaign."""
        if campaign_id in self.active_campaigns:
            campaign = self.active_campaigns[campaign_id]
            campaign.status = CampaignStatus.PAUSED
            self._update_campaign_progress(campaign_id, campaign)
            self.running_campaigns.discard(campaign_id)
            return True
        return False

    async def cancel_campaign(self, campaign_id: int):
        """Cancel a campaign."""
        if campaign_id in self.active_campaigns:
            campaign = self.active_campaigns[campaign_id]
            campaign.status = CampaignStatus.CANCELLED
            self._update_campaign_progress(campaign_id, campaign)
            self.running_campaigns.discard(campaign_id)
            return True
        return False

    async def resume_campaign(self, campaign_id: int):
        """Resume a paused campaign."""
        if campaign_id in self.active_campaigns:
            campaign = self.active_campaigns[campaign_id]
            if campaign.status == CampaignStatus.PAUSED:
                campaign.status = CampaignStatus.RUNNING
                campaign.config.pop("auto_paused_for_hours", None)  # Clear auto-pause flag
                self._update_campaign_progress(campaign_id, campaign)
                self.running_campaigns.add(campaign_id)
                # Restart campaign execution
                asyncio.create_task(self._run_campaign(campaign_id))
                return True
        return False

    def get_campaigns_by_status(self, status: CampaignStatus) -> List[Campaign]:
        """Get all campaigns with a specific status.

        Args:
            status: CampaignStatus to filter by

        Returns:
            List of matching campaigns
        """
        campaigns = []

        # Check active campaigns in memory first
        for campaign in self.active_campaigns.values():
            if campaign.status == status:
                campaigns.append(campaign)

        # Also check database for campaigns not in memory
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM campaigns WHERE status = ?", (status.value,))
                for row in cursor:
                    campaign_id = row["id"]
                    # Skip if already in active campaigns
                    if campaign_id not in self.active_campaigns:
                        campaign = self._row_to_campaign(row)
                        campaigns.append(campaign)
                        # Cache in memory
                        self.active_campaigns[campaign_id] = campaign
        except Exception as e:
            logger.error(f"Error fetching campaigns by status: {e}")

        return campaigns

    def _row_to_campaign(self, row: sqlite3.Row) -> Campaign:
        """Convert database row to Campaign object.

        Args:
            row: Database row

        Returns:
            Campaign object
        """
        return Campaign(
            id=row["id"],
            name=row["name"],
            template=row["template"],
            status=CampaignStatus(row["status"]),
            target_channel_id=row["target_channel_id"],
            target_member_ids=json.loads(row["target_member_ids"] or "[]"),
            account_ids=json.loads(row["account_ids"] or "[]"),
            created_at=(
                datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now()
            ),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
            total_targets=row["total_targets"] or 0,
            sent_count=row["sent_count"] or 0,
            failed_count=row["failed_count"] or 0,
            blocked_count=row["blocked_count"] or 0,
            rate_limit_delay=row["rate_limit_delay"] or 5,
            max_messages_per_hour=row["max_messages_per_hour"] or 20,
            max_messages_per_account=row["max_messages_per_account"] or 100,
            config=json.loads(row["config"] or "{}"),
            scheduled_start=(
                datetime.fromisoformat(row["scheduled_start"])
                if row.get("scheduled_start")
                else None
            ),
            scheduled_end=(
                datetime.fromisoformat(row["scheduled_end"]) if row.get("scheduled_end") else None
            ),
            active_hours_start=row.get("active_hours_start"),
            active_hours_end=row.get("active_hours_end"),
            active_days=json.loads(row["active_days"]) if row.get("active_days") else None,
            timezone=row.get("timezone", "UTC") or "UTC",
            recurring=bool(row.get("recurring", 0)),
            recurrence_interval=row.get("recurrence_interval"),
        )

    def _get_floodwait_guidance(self, wait_time: int, account_phone: str) -> str:
        """
        Provide actionable guidance based on FloodWait duration.

        Args:
            wait_time: FloodWait duration in seconds
            account_phone: Account that triggered the FloodWait

        Returns:
            Actionable guidance string for operators
        """
        if wait_time < 60:
            # Short wait - normal rate limiting
            return (
                "Short FloodWait (<1min). Normal rate limiting. "
                "Consider increasing delays between messages or reducing concurrent accounts."
            )
        elif wait_time < 300:
            # 1-5 minutes - moderate rate limiting
            return (
                f"Moderate FloodWait ({wait_time//60}min). "
                "Account may be sending too fast. "
                "Recommendation: Increase min_delay to 30-60s and reduce hourly limit."
            )
        elif wait_time < 3600:
            # 5-60 minutes - significant rate limiting
            return (
                f"Significant FloodWait ({wait_time//60}min). "
                f"Account {account_phone} hitting Telegram rate limits. "
                "Recommendation: Pause campaign on this account for 1 hour, "
                "reduce hourly message limit to 10-15, and increase delays to 120-300s."
            )
        elif wait_time < 86400:
            # 1-24 hours - severe rate limiting
            hours = wait_time // 3600
            return (
                f"⚠️ SEVERE FloodWait ({hours}h). "
                f"Account {account_phone} may be at risk of ban. "
                "Recommendation: Immediately pause all campaigns on this account, "
                "review anti-detection settings, and consider account warmup protocol."
            )
        else:
            # 24+ hours - critical
            days = wait_time // 86400
            return (
                f"🚨 CRITICAL FloodWait ({days}d). "
                f"Account {account_phone} is likely flagged and at high ban risk. "
                "Recommendation: Quarantine account, stop all activity, "
                "enable shadowban monitoring, and consider account rotation."
            )

    def _record_floodwait_event(
        self, account_phone: str, wait_time: int, campaign_id: int, guidance: str
    ):
        """
        Record FloodWait event for analytics and operator visibility.

        Args:
            account_phone: Account that triggered FloodWait
            wait_time: FloodWait duration in seconds
            campaign_id: Campaign ID
            guidance: Actionable guidance message
        """
        try:
            with self._get_connection() as conn:
                # Ensure floodwait_events table exists
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS floodwait_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        campaign_id INTEGER,
                        account_phone TEXT NOT NULL,
                        wait_time_seconds INTEGER NOT NULL,
                        severity TEXT NOT NULL,
                        guidance TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
                    )
                """
                )

                # Create index for fast lookups
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_floodwait_account
                    ON floodwait_events(account_phone, timestamp DESC)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_floodwait_campaign
                    ON floodwait_events(campaign_id, timestamp DESC)
                """
                )

                # Determine severity
                if wait_time < 60:
                    severity = "low"
                elif wait_time < 300:
                    severity = "moderate"
                elif wait_time < 3600:
                    severity = "high"
                elif wait_time < 86400:
                    severity = "severe"
                else:
                    severity = "critical"

                # Insert event
                conn.execute(
                    """
                    INSERT INTO floodwait_events
                    (campaign_id, account_phone, wait_time_seconds, severity, guidance)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (campaign_id, account_phone, wait_time, severity, guidance),
                )

                conn.commit()
                logger.info(
                    f"Recorded FloodWait event for {account_phone}: {severity} ({wait_time}s)"
                )

        except Exception as e:
            logger.error(f"Failed to record FloodWait event: {e}")

    def _get_account_floodwait_count(self, account_phone: str, hours: int = 24) -> int:
        """Get FloodWait count for an account in the last N hours."""
        try:
            cutoff = datetime.now() - timedelta(hours=hours)

            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) FROM floodwait_events
                    WHERE account_phone = ? AND timestamp >= ?
                """,
                    (account_phone, cutoff),
                )

                return cursor.fetchone()[0] or 0
        except Exception as e:
            logger.debug(f"Could not get FloodWait count: {e}")
            return 0

    def get_floodwait_history(
        self,
        account_phone: Optional[str] = None,
        campaign_id: Optional[int] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get FloodWait history for analysis and operator review.

        Args:
            account_phone: Filter by account (optional)
            campaign_id: Filter by campaign (optional)
            severity: Filter by severity level (optional)
            limit: Maximum number of events to return

        Returns:
            List of FloodWait events
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row

                # Build query with filters
                query = "SELECT * FROM floodwait_events WHERE 1=1"
                params = []

                if account_phone:
                    query += " AND account_phone = ?"
                    params.append(account_phone)

                if campaign_id:
                    query += " AND campaign_id = ?"
                    params.append(campaign_id)

                if severity:
                    query += " AND severity = ?"
                    params.append(severity)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor = conn.execute(query, params)

                events = []
                for row in cursor:
                    events.append(
                        {
                            "id": row["id"],
                            "campaign_id": row["campaign_id"],
                            "account_phone": row["account_phone"],
                            "wait_time_seconds": row["wait_time_seconds"],
                            "severity": row["severity"],
                            "guidance": row["guidance"],
                            "timestamp": row["timestamp"],
                        }
                    )

                return events

        except Exception as e:
            logger.error(f"Failed to get FloodWait history: {e}")
            return []
