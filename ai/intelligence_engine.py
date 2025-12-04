"""
Enhanced Member Intelligence System - Deep profile analysis and intelligence gathering.

Features:
- Common groups detection for relationship mapping
- User activity tracking and online/offline patterns
- Profile change detection (username, bio, photo)
- Interaction history mapping
- AI-powered value scoring and lead qualification
"""

import asyncio
import logging
import sqlite3
import json
import time
from typing import List, Dict, Optional, Set, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict, deque
import statistics
import hashlib

from pyrogram import Client
from pyrogram.types import User, Chat, Message
from pyrogram.errors import FloodWait, UserPrivacyRestricted, PeerIdInvalid
from pyrogram.enums import UserStatus

logger = logging.getLogger(__name__)


class ActivityLevel(Enum):
    """User activity levels."""
    INACTIVE = "inactive"      # No activity in 30+ days
    LOW = "low"               # Activity 1-2x per week
    MODERATE = "moderate"     # Activity 3-5x per week
    ACTIVE = "active"         # Daily activity
    VERY_ACTIVE = "very_active"  # Multiple times per day


class ValueTier(Enum):
    """Lead value tiers."""
    COLD = "cold"           # Low value, minimal engagement
    WARM = "warm"           # Some potential, moderate engagement
    HOT = "hot"             # High value, good engagement
    PREMIUM = "premium"     # Top tier, very high value


@dataclass
class UserIntelligence:
    """Comprehensive user intelligence profile."""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    
    # Activity tracking
    last_online: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    activity_level: ActivityLevel = ActivityLevel.INACTIVE
    online_patterns: List[int] = field(default_factory=list)  # Hour of day patterns
    timezone_offset: Optional[int] = None
    
    # Profile tracking
    username_history: List[Tuple[str, datetime]] = field(default_factory=list)
    profile_photo_hash: Optional[str] = None
    profile_changes: int = 0
    
    # Relationship data
    common_groups: List[int] = field(default_factory=list)
    mutual_contacts: List[int] = field(default_factory=list)
    interaction_score: float = 0.0
    
    # Engagement metrics
    messages_received: int = 0
    messages_sent: int = 0
    reactions_given: int = 0
    reactions_received: int = 0
    avg_response_time: Optional[float] = None
    
    # Value scoring
    value_score: float = 0.0
    value_tier: ValueTier = ValueTier.COLD
    conversion_probability: float = 0.0
    
    # Metadata
    first_seen: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['activity_level'] = self.activity_level.value
        data['value_tier'] = self.value_tier.value
        # Convert datetime objects to ISO strings
        for key in ['last_online', 'last_seen', 'first_seen', 'last_updated']:
            if data.get(key):
                data[key] = data[key].isoformat() if isinstance(data[key], datetime) else data[key]
        return data


@dataclass
class GroupIntelligence:
    """Intelligence about a group/channel."""
    group_id: int
    title: str
    username: Optional[str] = None
    member_count: int = 0
    active_member_count: int = 0
    admin_count: int = 0
    
    # Activity metrics
    messages_per_day: float = 0.0
    growth_rate: float = 0.0
    engagement_rate: float = 0.0
    
    # Quality scoring
    quality_score: float = 0.0
    spam_probability: float = 0.0
    value_rating: int = 0  # 1-5 stars
    
    # Metadata
    discovered_at: datetime = field(default_factory=datetime.now)
    last_analyzed: datetime = field(default_factory=datetime.now)


class IntelligenceEngine:
    """Core intelligence gathering and analysis engine."""
    
    def __init__(self, db_path: str = "intelligence.db"):
        """Initialize."""
        self.db_path = db_path
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool
            self._connection_pool = get_pool(self.db_path)
        except: pass
        self._init_database()
    
    def _get_connection(self):
        if self._connection_pool:
            return self._connection_pool.get_connection()
        return self._get_connection()
        self._cache = {}
        self._cache_ttl = 3600  # 1 hour cache
        
    def _init_database(self):
        """Initialize intelligence database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # User intelligence table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_intelligence (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                bio TEXT,
                last_online TIMESTAMP,
                last_seen TIMESTAMP,
                activity_level TEXT,
                online_patterns TEXT,
                timezone_offset INTEGER,
                username_history TEXT,
                profile_photo_hash TEXT,
                profile_changes INTEGER DEFAULT 0,
                common_groups TEXT,
                mutual_contacts TEXT,
                interaction_score REAL DEFAULT 0.0,
                messages_received INTEGER DEFAULT 0,
                messages_sent INTEGER DEFAULT 0,
                reactions_given INTEGER DEFAULT 0,
                reactions_received INTEGER DEFAULT 0,
                avg_response_time REAL,
                value_score REAL DEFAULT 0.0,
                value_tier TEXT DEFAULT 'cold',
                conversion_probability REAL DEFAULT 0.0,
                first_seen TIMESTAMP,
                last_updated TIMESTAMP
            )
        """)
        
        # Group intelligence table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_intelligence (
                group_id INTEGER PRIMARY KEY,
                title TEXT,
                username TEXT,
                member_count INTEGER DEFAULT 0,
                active_member_count INTEGER DEFAULT 0,
                admin_count INTEGER DEFAULT 0,
                messages_per_day REAL DEFAULT 0.0,
                growth_rate REAL DEFAULT 0.0,
                engagement_rate REAL DEFAULT 0.0,
                quality_score REAL DEFAULT 0.0,
                spam_probability REAL DEFAULT 0.0,
                value_rating INTEGER DEFAULT 0,
                discovered_at TIMESTAMP,
                last_analyzed TIMESTAMP
            )
        """)
        
        # Common groups mapping
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS common_groups_map (
                user_id INTEGER,
                group_id INTEGER,
                discovered_at TIMESTAMP,
                PRIMARY KEY (user_id, group_id)
            )
        """)
        
        # Activity log for pattern analysis
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                activity_type TEXT,
                timestamp TIMESTAMP,
                hour_of_day INTEGER,
                day_of_week INTEGER,
                metadata TEXT
            )
        """)
        
        # Profile change history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                change_type TEXT,
                old_value TEXT,
                new_value TEXT,
                detected_at TIMESTAMP
            )
        """)
        
        # Interaction history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                interaction_type TEXT,
                target_id INTEGER,
                message_id INTEGER,
                timestamp TIMESTAMP,
                metadata TEXT
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_value_score ON user_intelligence(value_score DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_activity ON user_intelligence(activity_level, last_online)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_group_quality ON group_intelligence(quality_score DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id, timestamp)")
        
        conn.commit()
        conn.close()
        logger.info("Intelligence database initialized")
    
    async def gather_user_intelligence(self, client: Client, user_id: int, 
                                      deep_analysis: bool = False) -> Optional[UserIntelligence]:
        """Gather comprehensive intelligence on a user.
        
        Args:
            client: Pyrogram client instance
            user_id: User ID to analyze
            deep_analysis: Perform deep analysis (common groups, etc.)
            
        Returns:
            UserIntelligence object or None
        """
        try:
            # Get basic user info
            user = await client.get_users(user_id)
            
            # Build intelligence profile
            intel = UserIntelligence(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                phone=user.phone_number,
                bio=user.bio if hasattr(user, 'bio') else None
            )
            
            # Get last seen / online status
            if user.status:
                intel.last_seen = self._parse_user_status(user.status)
                if user.status == UserStatus.ONLINE:
                    intel.last_online = datetime.now()
            
            # Load existing data from DB
            existing = self._load_user_intelligence(user_id)
            if existing:
                # Detect profile changes
                if existing.username != intel.username:
                    intel.username_history = existing.username_history.copy()
                    intel.username_history.append((existing.username, datetime.now()))
                    intel.profile_changes = existing.profile_changes + 1
                    self._log_profile_change(user_id, "username", existing.username, intel.username)
                else:
                    intel.username_history = existing.username_history
                    intel.profile_changes = existing.profile_changes
                
                # Preserve historical data
                intel.common_groups = existing.common_groups
                intel.interaction_score = existing.interaction_score
                intel.messages_received = existing.messages_received
                intel.messages_sent = existing.messages_sent
                intel.first_seen = existing.first_seen
            
            # Deep analysis
            if deep_analysis:
                # Get common groups
                common_groups = await self._get_common_groups(client, user_id)
                intel.common_groups = common_groups
                
                # Analyze activity patterns
                intel.online_patterns = self._analyze_online_patterns(user_id)
                intel.timezone_offset = self._infer_timezone(intel.online_patterns)
                intel.activity_level = self._calculate_activity_level(user_id)
            
            # Calculate value score
            intel.value_score = self._calculate_value_score(intel)
            intel.value_tier = self._get_value_tier(intel.value_score)
            intel.conversion_probability = self._calculate_conversion_probability(intel)
            
            # Update timestamp
            intel.last_updated = datetime.now()
            
            # Save to database
            self._save_user_intelligence(intel)
            
            # Log activity
            self._log_activity(user_id, "profile_update", {
                "username": intel.username,
                "status": str(user.status) if user.status else None
            })
            
            logger.info(f"Gathered intelligence on user {user_id}: {intel.value_tier.value} tier, score {intel.value_score:.2f}")
            return intel
            
        except FloodWait as e:
            logger.warning(f"FloodWait gathering intelligence on {user_id}: {e.value}s")
            await asyncio.sleep(e.value)
            return None
        except (UserPrivacyRestricted, PeerIdInvalid) as e:
            logger.debug(f"Cannot gather intelligence on {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error gathering intelligence on {user_id}: {e}", exc_info=True)
            return None
    
    async def _get_common_groups(self, client: Client, user_id: int) -> List[int]:
        """Get common groups with a user.
        
        Args:
            client: Pyrogram client
            user_id: User ID
            
        Returns:
            List of common group IDs
        """
        try:
            common_chats = await client.get_common_chats(user_id)
            group_ids = [chat.id for chat in common_chats]
            
            # Save to database
            conn = self._get_connection()
            cursor = conn.cursor()
            for group_id in group_ids:
                cursor.execute("""
                    INSERT OR REPLACE INTO common_groups_map (user_id, group_id, discovered_at)
                    VALUES (?, ?, ?)
                """, (user_id, group_id, datetime.now()))
            conn.commit()
            conn.close()
            
            logger.info(f"Found {len(group_ids)} common groups with user {user_id}")
            return group_ids
            
        except Exception as e:
            logger.debug(f"Error getting common groups for {user_id}: {e}")
            return []
    
    def _parse_user_status(self, status: UserStatus) -> Optional[datetime]:
        """Parse user status to last seen time."""
        if status == UserStatus.ONLINE:
            return datetime.now()
        elif status == UserStatus.RECENTLY:
            return datetime.now() - timedelta(minutes=30)
        elif status == UserStatus.LAST_WEEK:
            return datetime.now() - timedelta(days=5)
        elif status == UserStatus.LAST_MONTH:
            return datetime.now() - timedelta(days=20)
        return None
    
    def _analyze_online_patterns(self, user_id: int) -> List[int]:
        """Analyze user's online patterns by hour of day.
        
        Returns:
            List of hours (0-23) when user is typically online
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT hour_of_day, COUNT(*) as count
            FROM activity_log
            WHERE user_id = ? AND activity_type = 'online'
            AND timestamp > datetime('now', '-30 days')
            GROUP BY hour_of_day
            ORDER BY count DESC
            LIMIT 5
        """, (user_id,))
        
        patterns = [row[0] for row in cursor.fetchall()]
        conn.close()
        return patterns
    
    def _infer_timezone(self, online_patterns: List[int]) -> Optional[int]:
        """Infer timezone offset from online patterns."""
        if not online_patterns:
            return None
        
        # Assume most active hours are during typical waking hours (9-22)
        avg_active_hour = sum(online_patterns) / len(online_patterns) if online_patterns else 15
        
        # Calculate offset from UTC (assuming 15:00 average is ~0 offset)
        offset = int(15 - avg_active_hour)
        return max(-12, min(12, offset))
    
    def _calculate_activity_level(self, user_id: int) -> ActivityLevel:
        """Calculate user's activity level."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Count activities in last 30 days
        cursor.execute("""
            SELECT COUNT(DISTINCT DATE(timestamp)) as active_days
            FROM activity_log
            WHERE user_id = ? AND timestamp > datetime('now', '-30 days')
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        active_days = row[0] if row else 0
        
        if active_days == 0:
            return ActivityLevel.INACTIVE
        elif active_days <= 8:  # ~1-2x per week
            return ActivityLevel.LOW
        elif active_days <= 20:  # ~3-5x per week
            return ActivityLevel.MODERATE
        elif active_days <= 25:
            return ActivityLevel.ACTIVE
        else:
            return ActivityLevel.VERY_ACTIVE
    
    def _calculate_value_score(self, intel: UserIntelligence) -> float:
        """Calculate overall value score (0-100)."""
        score = 0.0
        
        # Activity level (0-30 points)
        activity_scores = {
            ActivityLevel.INACTIVE: 0,
            ActivityLevel.LOW: 5,
            ActivityLevel.MODERATE: 15,
            ActivityLevel.ACTIVE: 25,
            ActivityLevel.VERY_ACTIVE: 30
        }
        score += activity_scores.get(intel.activity_level, 0)
        
        # Engagement (0-25 points)
        if intel.messages_sent > 0:
            response_rate = intel.messages_received / intel.messages_sent
            score += min(25, response_rate * 25)
        
        # Common groups (0-20 points)
        score += min(20, len(intel.common_groups) * 2)
        
        # Interaction score (0-15 points)
        score += min(15, intel.interaction_score)
        
        # Profile completeness (0-10 points)
        completeness = sum([
            bool(intel.username),
            bool(intel.first_name),
            bool(intel.bio),
            bool(intel.phone)
        ])
        score += (completeness / 4) * 10
        
        return min(100.0, score)
    
    def _get_value_tier(self, score: float) -> ValueTier:
        """Convert value score to tier."""
        if score >= 75:
            return ValueTier.PREMIUM
        elif score >= 50:
            return ValueTier.HOT
        elif score >= 25:
            return ValueTier.WARM
        else:
            return ValueTier.COLD
    
    def _calculate_conversion_probability(self, intel: UserIntelligence) -> float:
        """Calculate probability of conversion (0-1)."""
        # Simple model based on activity and engagement
        base_prob = 0.1
        
        if intel.activity_level in [ActivityLevel.ACTIVE, ActivityLevel.VERY_ACTIVE]:
            base_prob += 0.3
        elif intel.activity_level == ActivityLevel.MODERATE:
            base_prob += 0.15
        
        if intel.messages_sent > 0 and intel.messages_received > 0:
            response_rate = intel.messages_received / intel.messages_sent
            base_prob += response_rate * 0.4
        
        if len(intel.common_groups) > 3:
            base_prob += 0.2
        
        return min(1.0, base_prob)
    
    def _load_user_intelligence(self, user_id: int) -> Optional[UserIntelligence]:
        """Load existing intelligence from database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_intelligence WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        # Parse row data
        return UserIntelligence(
            user_id=row[0],
            username=row[1],
            first_name=row[2],
            last_name=row[3],
            phone=row[4],
            bio=row[5],
            last_online=datetime.fromisoformat(row[6]) if row[6] else None,
            last_seen=datetime.fromisoformat(row[7]) if row[7] else None,
            activity_level=ActivityLevel(row[8]) if row[8] else ActivityLevel.INACTIVE,
            online_patterns=json.loads(row[9]) if row[9] else [],
            timezone_offset=row[10],
            username_history=json.loads(row[11]) if row[11] else [],
            profile_photo_hash=row[12],
            profile_changes=row[13] or 0,
            common_groups=json.loads(row[14]) if row[14] else [],
            mutual_contacts=json.loads(row[15]) if row[15] else [],
            interaction_score=row[16] or 0.0,
            messages_received=row[17] or 0,
            messages_sent=row[18] or 0,
            reactions_given=row[19] or 0,
            reactions_received=row[20] or 0,
            avg_response_time=row[21],
            value_score=row[22] or 0.0,
            value_tier=ValueTier(row[23]) if row[23] else ValueTier.COLD,
            conversion_probability=row[24] or 0.0,
            first_seen=datetime.fromisoformat(row[25]) if row[25] else datetime.now(),
            last_updated=datetime.fromisoformat(row[26]) if row[26] else datetime.now()
        )
    
    def _save_user_intelligence(self, intel: UserIntelligence):
        """Save user intelligence to database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO user_intelligence VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            intel.user_id, intel.username, intel.first_name, intel.last_name,
            intel.phone, intel.bio,
            intel.last_online.isoformat() if intel.last_online else None,
            intel.last_seen.isoformat() if intel.last_seen else None,
            intel.activity_level.value,
            json.dumps(intel.online_patterns),
            intel.timezone_offset,
            json.dumps(intel.username_history),
            intel.profile_photo_hash,
            intel.profile_changes,
            json.dumps(intel.common_groups),
            json.dumps(intel.mutual_contacts),
            intel.interaction_score,
            intel.messages_received,
            intel.messages_sent,
            intel.reactions_given,
            intel.reactions_received,
            intel.avg_response_time,
            intel.value_score,
            intel.value_tier.value,
            intel.conversion_probability,
            intel.first_seen.isoformat(),
            intel.last_updated.isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def _log_profile_change(self, user_id: int, change_type: str, old_value: str, new_value: str):
        """Log a profile change."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO profile_changes (user_id, change_type, old_value, new_value, detected_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, change_type, old_value, new_value, datetime.now()))
        conn.commit()
        conn.close()
    
    def _log_activity(self, user_id: int, activity_type: str, metadata: Dict = None):
        """Log user activity."""
        now = datetime.now()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activity_log (user_id, activity_type, timestamp, hour_of_day, day_of_week, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id, activity_type, now,
            now.hour, now.weekday(),
            json.dumps(metadata) if metadata else None
        ))
        conn.commit()
        conn.close()
    
    def log_interaction(self, user_id: int, interaction_type: str, 
                       target_id: Optional[int] = None, message_id: Optional[int] = None,
                       metadata: Dict = None):
        """Log an interaction with a user.
        
        Args:
            user_id: User ID
            interaction_type: Type (message_sent, reaction, etc.)
            target_id: Target user/group ID
            message_id: Message ID
            metadata: Additional data
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interactions (user_id, interaction_type, target_id, message_id, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, interaction_type, target_id, message_id, datetime.now(), 
              json.dumps(metadata) if metadata else None))
        conn.commit()
        conn.close()
    
    def get_top_value_users(self, limit: int = 100, min_score: float = 50.0) -> List[UserIntelligence]:
        """Get top value users.
        
        Args:
            limit: Maximum number to return
            min_score: Minimum value score
            
        Returns:
            List of UserIntelligence objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM user_intelligence
            WHERE value_score >= ?
            ORDER BY value_score DESC
            LIMIT ?
        """, (min_score, limit))
        
        users = []
        for row in cursor.fetchall():
            users.append(self._row_to_intelligence(row))
        
        conn.close()
        return users
    
    def _row_to_intelligence(self, row) -> UserIntelligence:
        """Convert database row to UserIntelligence."""
        return UserIntelligence(
            user_id=row[0],
            username=row[1],
            first_name=row[2],
            last_name=row[3],
            phone=row[4],
            bio=row[5],
            last_online=datetime.fromisoformat(row[6]) if row[6] else None,
            last_seen=datetime.fromisoformat(row[7]) if row[7] else None,
            activity_level=ActivityLevel(row[8]) if row[8] else ActivityLevel.INACTIVE,
            online_patterns=json.loads(row[9]) if row[9] else [],
            timezone_offset=row[10],
            username_history=json.loads(row[11]) if row[11] else [],
            profile_photo_hash=row[12],
            profile_changes=row[13] or 0,
            common_groups=json.loads(row[14]) if row[14] else [],
            mutual_contacts=json.loads(row[15]) if row[15] else [],
            interaction_score=row[16] or 0.0,
            messages_received=row[17] or 0,
            messages_sent=row[18] or 0,
            reactions_given=row[19] or 0,
            reactions_received=row[20] or 0,
            avg_response_time=row[21],
            value_score=row[22] or 0.0,
            value_tier=ValueTier(row[23]) if row[23] else ValueTier.COLD,
            conversion_probability=row[24] or 0.0,
            first_seen=datetime.fromisoformat(row[25]) if row[25] else datetime.now(),
            last_updated=datetime.fromisoformat(row[26]) if row[26] else datetime.now()
        )
    
    async def batch_analyze_users(self, client: Client, user_ids: List[int], 
                                  deep_analysis: bool = False, 
                                  delay_range: Tuple[float, float] = (1.0, 3.0)) -> List[UserIntelligence]:
        """Analyze multiple users with rate limiting.
        
        Args:
            client: Pyrogram client
            user_ids: List of user IDs
            deep_analysis: Perform deep analysis
            delay_range: Delay range between requests
            
        Returns:
            List of UserIntelligence objects
        """
        results = []
        
        for i, user_id in enumerate(user_ids):
            intel = await self.gather_user_intelligence(client, user_id, deep_analysis)
            if intel:
                results.append(intel)
            
            # Rate limiting
            if i < len(user_ids) - 1:
                delay = random.uniform(*delay_range)
                await asyncio.sleep(delay)
        
        logger.info(f"Batch analyzed {len(results)}/{len(user_ids)} users")
        return results
    
    def get_user_statistics(self) -> Dict[str, Any]:
        """Get overall intelligence statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) FROM user_intelligence")
        total_users = cursor.fetchone()[0]
        
        # Users by tier
        cursor.execute("SELECT value_tier, COUNT(*) FROM user_intelligence GROUP BY value_tier")
        tier_counts = dict(cursor.fetchall())
        
        # Average value score
        cursor.execute("SELECT AVG(value_score) FROM user_intelligence")
        avg_score = cursor.fetchone()[0] or 0.0
        
        # Activity distribution
        cursor.execute("SELECT activity_level, COUNT(*) FROM user_intelligence GROUP BY activity_level")
        activity_dist = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            'total_users': total_users,
            'tier_counts': tier_counts,
            'average_value_score': avg_score,
            'activity_distribution': activity_dist
        }


# Utility function for integration
async def analyze_campaign_targets(client: Client, user_ids: List[int]) -> List[UserIntelligence]:
    """Analyze campaign targets and return prioritized list.
    
    Args:
        client: Pyrogram client
        user_ids: List of user IDs to analyze
        
    Returns:
        List of UserIntelligence sorted by value score
    """
    engine = IntelligenceEngine()
    results = await engine.batch_analyze_users(client, user_ids, deep_analysis=True)
    return sorted(results, key=lambda x: x.value_score, reverse=True)

