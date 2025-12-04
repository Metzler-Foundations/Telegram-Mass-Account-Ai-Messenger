"""
Engagement Automation - Automated reactions and smart engagement system.

Features:
- Auto-react to messages in target groups
- Smart reaction selection based on message content
- Human-like timing and patterns
- Selective targeting based on user value
- Engagement scoring and tracking
"""

import asyncio
import logging
import sqlite3
import random
import json
import re
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict

from pyrogram import Client, filters
from pyrogram.types import Message, Chat
from pyrogram.errors import FloodWait, ReactionInvalid, ChatAdminRequired
from pyrogram.enums import ChatType

logger = logging.getLogger(__name__)


class EngagementStrategy(Enum):
    """Engagement strategies."""
    CONSERVATIVE = "conservative"  # React rarely, high-value only
    MODERATE = "moderate"          # Balanced engagement
    AGGRESSIVE = "aggressive"      # React frequently, broad targeting
    TARGETED = "targeted"          # Only specific users/keywords


class ReactionType(Enum):
    """Types of reactions."""
    LIKE = "👍"
    LOVE = "❤️"
    FIRE = "🔥"
    CLAP = "👏"
    LAUGH = "😂"
    THINK = "🤔"
    STAR = "⭐"
    CELEBRATE = "🎉"


@dataclass
class EngagementRule:
    """Rule for automated engagement."""
    rule_id: str
    name: str
    enabled: bool = True
    
    # Targeting
    target_groups: List[int] = field(default_factory=list)
    target_users: List[int] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    min_user_value_score: float = 0.0
    
    # Reaction settings
    reaction_emojis: List[str] = field(default_factory=list)
    reaction_probability: float = 0.3  # Probability of reacting
    
    # Timing
    min_delay_seconds: int = 5
    max_delay_seconds: int = 120
    
    # Rate limiting
    max_reactions_per_hour: int = 20
    max_reactions_per_group_per_hour: int = 10

    # Filters
    exclude_keywords: List[str] = field(default_factory=list)
    only_reply_to_messages: bool = False
    min_message_length: int = 10
    disabled_groups: List[int] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class EngagementLog:
    """Log of engagement action."""
    log_id: Optional[int]
    rule_id: str
    group_id: int
    message_id: int
    user_id: int
    reaction_emoji: str
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None


class EngagementAutomation:
    """Automated engagement and reaction system."""
    
    def __init__(self, db_path: str = "engagement.db", intelligence_db: str = "intelligence.db"):
        """Initialize engagement automation.
        
        Args:
            db_path: Path to engagement database
            intelligence_db: Path to intelligence database
        """
        self.db_path = db_path
        self.intelligence_db = intelligence_db
        self._init_database()

        # Retention controls
        self.stats_retention_days = 90

        # Rate limiting tracking
        self._reaction_counts = defaultdict(lambda: defaultdict(int))  # {hour: {group_id: count}}
        self._last_reactions = {}  # {group_id: timestamp}
        
        # Active rules
        self._rules: Dict[str, EngagementRule] = {}
        self._load_rules()
        
    def _init_database(self):
        """Initialize engagement database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Engagement rules
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS engagement_rules (
                rule_id TEXT PRIMARY KEY,
                name TEXT,
                enabled INTEGER,
                target_groups TEXT,
                target_users TEXT,
                keywords TEXT,
                min_user_value_score REAL,
                reaction_emojis TEXT,
                reaction_probability REAL,
                min_delay_seconds INTEGER,
                max_delay_seconds INTEGER,
                max_reactions_per_hour INTEGER,
                max_reactions_per_group_per_hour INTEGER,
                exclude_keywords TEXT,
                only_reply_to_messages INTEGER,
                min_message_length INTEGER,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                disabled_groups TEXT DEFAULT '[]'
            )
        """)

        try:
            cursor.execute("ALTER TABLE engagement_rules ADD COLUMN disabled_groups TEXT DEFAULT '[]'")
        except sqlite3.OperationalError:
            # Column already exists
            pass
        
        # Engagement log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS engagement_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id TEXT,
                group_id INTEGER,
                message_id INTEGER,
                user_id INTEGER,
                reaction_emoji TEXT,
                timestamp TIMESTAMP,
                success INTEGER,
                error_message TEXT
            )
        """)
        
        # Engagement statistics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS engagement_stats (
                user_id INTEGER,
                group_id INTEGER,
                reactions_given INTEGER DEFAULT 0,
                reactions_received INTEGER DEFAULT 0,
                last_engagement TIMESTAMP,
                PRIMARY KEY (user_id, group_id)
            )
        """)
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_timestamp ON engagement_log(timestamp)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_log_rule_message ON engagement_log(rule_id, message_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_group ON engagement_log(group_id, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_user ON engagement_stats(user_id)")
        
        conn.commit()
        conn.close()
        logger.info("Engagement database initialized")
    
    def _load_rules(self):
        """Load engagement rules from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM engagement_rules WHERE enabled = 1")

        for row in cursor.fetchall():
            rule = EngagementRule(
                rule_id=row[0],
                name=row[1],
                enabled=bool(row[2]),
                target_groups=json.loads(row[3]) if row[3] else [],
                target_users=json.loads(row[4]) if row[4] else [],
                keywords=json.loads(row[5]) if row[5] else [],
                min_user_value_score=row[6] or 0.0,
                reaction_emojis=json.loads(row[7]) if row[7] else [],
                reaction_probability=row[8] or 0.3,
                min_delay_seconds=row[9] or 5,
                max_delay_seconds=row[10] or 120,
                max_reactions_per_hour=row[11] or 20,
                max_reactions_per_group_per_hour=row[12] or 10,
                exclude_keywords=json.loads(row[13]) if row[13] else [],
                only_reply_to_messages=bool(row[14]),
                min_message_length=row[15] or 10,
                created_at=datetime.fromisoformat(row[16]) if row[16] else datetime.now(),
                updated_at=datetime.fromisoformat(row[17]) if row[17] else datetime.now(),
                disabled_groups=json.loads(row[18]) if len(row) > 18 and row[18] else []
            )
            self._rules[rule.rule_id] = rule
        
        conn.close()
        logger.info(f"Loaded {len(self._rules)} engagement rules")
    
    def add_rule(self, rule: EngagementRule):
        """Add or update an engagement rule."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        rule.updated_at = datetime.now()
        
        cursor.execute("""
            INSERT OR REPLACE INTO engagement_rules VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            rule.rule_id, rule.name, int(rule.enabled),
            json.dumps(rule.target_groups),
            json.dumps(rule.target_users),
            json.dumps(rule.keywords),
            rule.min_user_value_score,
            json.dumps(rule.reaction_emojis),
            rule.reaction_probability,
            rule.min_delay_seconds,
            rule.max_delay_seconds,
            rule.max_reactions_per_hour,
            rule.max_reactions_per_group_per_hour,
            json.dumps(rule.exclude_keywords),
            int(rule.only_reply_to_messages),
            rule.min_message_length,
            rule.created_at.isoformat(),
            rule.updated_at.isoformat(),
            json.dumps(rule.disabled_groups)
        ))
        
        conn.commit()
        conn.close()

        self._rules[rule.rule_id] = rule
        logger.info(f"Added/updated engagement rule: {rule.name}")

    def disable_group_for_rule(self, rule_id: str, group_id: int) -> bool:
        """Disable engagement for a specific group without turning off the rule."""
        rule = self._rules.get(rule_id)
        if not rule:
            logger.warning("Cannot disable group %s for missing rule %s", group_id, rule_id)
            return False

        if group_id in rule.disabled_groups:
            return True

        rule.disabled_groups.append(group_id)
        self.add_rule(rule)
        logger.info("Disabled group %s for rule %s", group_id, rule_id)
        return True

    def enable_group_for_rule(self, rule_id: str, group_id: int) -> bool:
        """Re-enable engagement for a previously disabled group."""
        rule = self._rules.get(rule_id)
        if not rule:
            logger.warning("Cannot enable group %s for missing rule %s", group_id, rule_id)
            return False

        if group_id not in rule.disabled_groups:
            return True

        rule.disabled_groups = [gid for gid in rule.disabled_groups if gid != group_id]
        self.add_rule(rule)
        logger.info("Enabled group %s for rule %s", group_id, rule_id)
        return True
    
    async def process_message(self, client: Client, message: Message) -> bool:
        """Process a message for potential engagement.
        
        Args:
            client: Pyrogram client
            message: Message to process
            
        Returns:
            True if engaged, False otherwise
        """
        if not message.chat or not message.from_user:
            return False
        
        # Check all rules
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            # Check if should engage
            if await self._should_engage(message, rule):
                # Add human-like delay
                delay = random.uniform(rule.min_delay_seconds, rule.max_delay_seconds)
                await asyncio.sleep(delay)
                
                # Perform engagement
                success = await self._engage(client, message, rule)
                if success:
                    return True
        
        return False
    
    async def _should_engage(self, message: Message, rule: EngagementRule) -> bool:
        """Determine if should engage with a message.
        
        Args:
            message: Message to evaluate
            rule: Engagement rule
            
        Returns:
            True if should engage
        """
        # Check group targeting
        if rule.target_groups and message.chat.id not in rule.target_groups:
            return False

        # Per-group disable toggle
        if rule.disabled_groups and message.chat.id in rule.disabled_groups:
            return False
        
        # Check user targeting
        if rule.target_users and message.from_user.id not in rule.target_users:
            # If no specific users but has min value score, check intelligence
            if rule.min_user_value_score > 0:
                user_value = await self._get_user_value_score(message.from_user.id)
                if user_value < rule.min_user_value_score:
                    return False
        
        # Check message length
        if not message.text or len(message.text) < rule.min_message_length:
            return False
        
        # Check if reply required
        if rule.only_reply_to_messages and not message.reply_to_message:
            return False
        
        # Check exclude keywords
        if rule.exclude_keywords:
            text_lower = message.text.lower()
            if any(keyword.lower() in text_lower for keyword in rule.exclude_keywords):
                return False
        
        # Check include keywords
        if rule.keywords:
            text_lower = message.text.lower()
            if not any(keyword.lower() in text_lower for keyword in rule.keywords):
                return False
        
        # Check rate limits
        if not self._check_rate_limits(message.chat.id, rule):
            return False
        
        # Probability check
        if random.random() > rule.reaction_probability:
            return False
        
        return True
    
    def _check_rate_limits(self, group_id: int, rule: EngagementRule) -> bool:
        """Check if rate limits allow engagement."""
        current_hour = datetime.now().hour
        
        # Check global rate limit
        total_this_hour = sum(
            counts[group_id] 
            for hour, counts in self._reaction_counts.items() 
            if hour == current_hour
        )
        if total_this_hour >= rule.max_reactions_per_hour:
            return False
        
        # Check per-group rate limit
        group_count = self._reaction_counts[current_hour][group_id]
        if group_count >= rule.max_reactions_per_group_per_hour:
            return False
        
        # Check minimum time since last reaction in this group
        if group_id in self._last_reactions:
            time_since = (datetime.now() - self._last_reactions[group_id]).total_seconds()
            if time_since < 30:  # Minimum 30 seconds between reactions in same group
                return False
        
        return True
    
    async def _engage(self, client: Client, message: Message, rule: EngagementRule) -> bool:
        """Perform engagement action (react to message).
        
        Args:
            client: Pyrogram client
            message: Message to react to
            rule: Engagement rule
            
        Returns:
            True if successful
        """
        try:
            if self._already_engaged(rule.rule_id, message.id):
                logger.debug(f"Skipping duplicate engagement for message {message.id} and rule {rule.rule_id}")
                return False

            # Select reaction
            if rule.reaction_emojis:
                reaction = random.choice(rule.reaction_emojis)
            else:
                reaction = random.choice(["👍", "❤️", "🔥"])
            
            # Send reaction
            await client.send_reaction(
                chat_id=message.chat.id,
                message_id=message.id,
                emoji=reaction
            )
            
            # Update tracking
            current_hour = datetime.now().hour
            self._reaction_counts[current_hour][message.chat.id] += 1
            self._last_reactions[message.chat.id] = datetime.now()
            
            # Log engagement
            self._log_engagement(
                rule.rule_id,
                message.chat.id,
                message.id,
                message.from_user.id,
                reaction,
                True
            )
            
            # Update stats
            self._update_engagement_stats(message.from_user.id, message.chat.id, gave_reaction=True)
            
            logger.info(f"Engaged with message {message.id} in group {message.chat.id} using reaction {reaction}")
            return True
            
        except FloodWait as e:
            logger.warning(f"FloodWait on reaction: {e.value}s")
            self._log_engagement(
                rule.rule_id, message.chat.id, message.id,
                message.from_user.id, reaction, False, f"FloodWait: {e.value}s"
            )
            await asyncio.sleep(e.value)
            return False
            
        except (ReactionInvalid, ChatAdminRequired) as e:
            logger.debug(f"Cannot react to message: {e}")
            self._log_engagement(
                rule.rule_id, message.chat.id, message.id,
                message.from_user.id, reaction, False, str(e)
            )
            return False
            
        except Exception as e:
            logger.error(f"Error engaging with message: {e}", exc_info=True)
            self._log_engagement(
                rule.rule_id, message.chat.id, message.id,
                message.from_user.id, reaction, False, str(e)
            )
            return False
    
    async def _get_user_value_score(self, user_id: int) -> float:
        """Get user value score from intelligence database."""
        try:
            conn = sqlite3.connect(self.intelligence_db)
            cursor = conn.cursor()
            cursor.execute("SELECT value_score FROM user_intelligence WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else 0.0
        except Exception as e:
            logger.debug(f"Error getting value score for {user_id}: {e}")
            return 0.0
    
    def _log_engagement(self, rule_id: str, group_id: int, message_id: int,
                       user_id: int, reaction: str, success: bool, error: str = None):
        """Log an engagement action."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO engagement_log (
                rule_id, group_id, message_id, user_id, reaction_emoji,
                timestamp, success, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (rule_id, group_id, message_id, user_id, reaction,
              datetime.now(), int(success), error))
        conn.commit()
        conn.close()

    def _prune_engagement_stats(self, conn):
        """Delete stale engagement stats to prevent unbounded growth."""
        try:
            cutoff = datetime.now() - timedelta(days=self.stats_retention_days)
            stats_result = conn.execute(
                "DELETE FROM engagement_stats WHERE last_engagement IS NOT NULL AND last_engagement < ?",
                (cutoff,),
            )
            log_result = conn.execute(
                "DELETE FROM engagement_log WHERE timestamp < ?",
                (cutoff,),
            )
            conn.commit()

            removed_stats = stats_result.rowcount if stats_result is not None else 0
            removed_logs = log_result.rowcount if log_result is not None else 0
            if removed_stats == 0 and removed_logs == 0:
                logger.warning(
                    "Engagement pruning completed without removing records. Check retention window (%s days) or DB locks.",
                    self.stats_retention_days,
                )
        except Exception as exc:
            logger.debug(f"Engagement stats pruning failed: {exc}")

    def _already_engaged(self, rule_id: str, message_id: int) -> bool:
        """Check if we've already reacted to this message for the given rule."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM engagement_log WHERE rule_id = ? AND message_id = ? LIMIT 1",
                (rule_id, message_id)
            )
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as exc:
            logger.debug(f"Duplicate engagement check failed: {exc}")
            return False
    
    def _update_engagement_stats(self, user_id: int, group_id: int,
                                 gave_reaction: bool = False, received_reaction: bool = False):
        """Update engagement statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if gave_reaction:
            cursor.execute("""
                INSERT INTO engagement_stats (user_id, group_id, reactions_given, last_engagement)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_id, group_id) DO UPDATE SET
                    reactions_given = reactions_given + 1,
                    last_engagement = excluded.last_engagement
            """, (user_id, group_id, datetime.now()))
        
        if received_reaction:
            cursor.execute("""
                INSERT INTO engagement_stats (user_id, group_id, reactions_received, last_engagement)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_id, group_id) DO UPDATE SET
                    reactions_received = reactions_received + 1,
                    last_engagement = excluded.last_engagement
            """, (user_id, group_id, datetime.now()))

        conn.commit()
        self._prune_engagement_stats(conn)
        conn.close()
    
    def get_engagement_stats(self, period_hours: int = 24) -> Dict:
        """Get engagement statistics for a period.
        
        Args:
            period_hours: Time period in hours
            
        Returns:
            Dictionary with statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(hours=period_hours)
        
        # Total reactions
        cursor.execute("""
            SELECT COUNT(*) FROM engagement_log 
            WHERE timestamp > ? AND success = 1
        """, (since,))
        total_reactions = cursor.fetchone()[0]
        
        # By rule
        cursor.execute("""
            SELECT rule_id, COUNT(*) FROM engagement_log
            WHERE timestamp > ? AND success = 1
            GROUP BY rule_id
        """, (since,))
        by_rule = dict(cursor.fetchall())
        
        # By group
        cursor.execute("""
            SELECT group_id, COUNT(*) FROM engagement_log
            WHERE timestamp > ? AND success = 1
            GROUP BY group_id
        """, (since,))
        by_group = dict(cursor.fetchall())
        
        # Success rate
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
            FROM engagement_log
            WHERE timestamp > ?
        """, (since,))
        success_rate = cursor.fetchone()[0] or 0.0
        
        conn.close()
        
        return {
            'total_reactions': total_reactions,
            'by_rule': by_rule,
            'by_group': by_group,
            'success_rate': success_rate,
            'period_hours': period_hours
        }
    
    def create_smart_rule(self, name: str, strategy: EngagementStrategy,
                         target_groups: List[int] = None,
                         keywords: List[str] = None) -> EngagementRule:
        """Create a smart engagement rule with preset configurations.
        
        Args:
            name: Rule name
            strategy: Engagement strategy
            target_groups: Target group IDs
            keywords: Keywords to match
            
        Returns:
            Created EngagementRule
        """
        rule_id = f"rule_{datetime.now().timestamp()}"
        
        # Strategy presets
        if strategy == EngagementStrategy.CONSERVATIVE:
            rule = EngagementRule(
                rule_id=rule_id,
                name=name,
                target_groups=target_groups or [],
                keywords=keywords or [],
                min_user_value_score=50.0,
                reaction_emojis=["👍", "❤️"],
                reaction_probability=0.15,
                min_delay_seconds=30,
                max_delay_seconds=180,
                max_reactions_per_hour=10,
                max_reactions_per_group_per_hour=3
            )
        elif strategy == EngagementStrategy.MODERATE:
            rule = EngagementRule(
                rule_id=rule_id,
                name=name,
                target_groups=target_groups or [],
                keywords=keywords or [],
                min_user_value_score=25.0,
                reaction_emojis=["👍", "❤️", "🔥", "👏"],
                reaction_probability=0.3,
                min_delay_seconds=15,
                max_delay_seconds=120,
                max_reactions_per_hour=20,
                max_reactions_per_group_per_hour=7
            )
        elif strategy == EngagementStrategy.AGGRESSIVE:
            rule = EngagementRule(
                rule_id=rule_id,
                name=name,
                target_groups=target_groups or [],
                keywords=keywords or [],
                min_user_value_score=0.0,
                reaction_emojis=["👍", "❤️", "🔥", "👏", "😂", "🎉"],
                reaction_probability=0.5,
                min_delay_seconds=5,
                max_delay_seconds=60,
                max_reactions_per_hour=40,
                max_reactions_per_group_per_hour=15
            )
        else:  # TARGETED
            rule = EngagementRule(
                rule_id=rule_id,
                name=name,
                target_groups=target_groups or [],
                keywords=keywords or [],
                min_user_value_score=60.0,
                reaction_emojis=["👍", "❤️", "🔥"],
                reaction_probability=0.8,
                min_delay_seconds=10,
                max_delay_seconds=90,
                max_reactions_per_hour=15,
                max_reactions_per_group_per_hour=5
            )
        
        self.add_rule(rule)
        return rule
    
    def cleanup_old_logs(self, days: int = 30):
        """Clean up old engagement logs.
        
        Args:
            days: Keep logs newer than this many days
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM engagement_log WHERE timestamp < ?", (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleaned up {deleted} old engagement logs")

