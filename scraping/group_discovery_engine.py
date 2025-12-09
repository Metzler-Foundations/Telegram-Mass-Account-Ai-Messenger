"""
Advanced Group Discovery System - Multi-method group discovery and analysis.

Features:
- Nearby groups discovery with location spoofing
- Invite link harvesting and validation
- Common group mining
- Event log analysis for group intelligence
- Group quality scoring and ranking
"""

import asyncio
import logging
import sqlite3
import json
import re
import random
from typing import List, Dict, Optional, Set, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
import hashlib

from pyrogram import Client
from pyrogram.types import Chat, Message, ChatEvent
from pyrogram.errors import (
    FloodWait,
    InviteHashExpired,
    InviteHashInvalid,
    ChannelPrivate,
    ChatAdminRequired,
    PeerIdInvalid,
)
from pyrogram.enums import ChatType, ChatMemberStatus

logger = logging.getLogger(__name__)


class DiscoveryMethod(Enum):
    """Discovery methods."""

    NEARBY = "nearby"
    INVITE_LINK = "invite_link"
    COMMON_GROUPS = "common_groups"
    EVENT_LOG = "event_log"
    SEARCH = "search"
    MEMBER_GROUPS = "member_groups"


class GroupQuality(Enum):
    """Group quality levels."""

    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    SPAM = "spam"


@dataclass
class DiscoveredGroup:
    """Discovered group information."""

    group_id: int
    title: str
    username: Optional[str] = None
    invite_link: Optional[str] = None

    # Discovery info
    discovery_method: DiscoveryMethod = DiscoveryMethod.SEARCH
    discovered_at: datetime = field(default_factory=datetime.now)
    discovered_from: Optional[int] = None  # Source group/user ID

    # Group metrics
    member_count: Optional[int] = None
    online_count: Optional[int] = None
    description: Optional[str] = None
    is_verified: bool = False
    is_scam: bool = False
    is_fake: bool = False

    # Location data (if from nearby discovery)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance: Optional[int] = None

    # Quality assessment
    quality_score: float = 0.0
    quality_level: GroupQuality = GroupQuality.AVERAGE
    spam_indicators: List[str] = field(default_factory=list)

    # Activity metrics
    messages_per_day: Optional[float] = None
    activity_score: float = 0.0

    # Join status
    is_joined: bool = False
    joined_at: Optional[datetime] = None
    join_attempts: int = 0

    # Metadata
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class LocationProfile:
    """Location profile for nearby group discovery."""

    latitude: float
    longitude: float
    name: str
    country: str = ""
    city: str = ""
    radius_km: float = 5.0


class GroupDiscoveryEngine:
    """Advanced group discovery system."""

    def __init__(self, db_path: str = "discovered_groups.db"):
        """Initialize."""
        self.db_path = db_path
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool

            self._connection_pool = get_pool(self.db_path)
        except:
            pass
        self._init_database()

    def _get_connection(self):
        if self._connection_pool:
            return self._connection_pool.get_connection()
        return self._get_connection()

        # Discovery tracking
        self._discovered_ids: Set[int] = set()
        self._load_discovered_ids()

        # Rate limiting
        self._last_discovery: Dict[str, datetime] = {}

    def _init_database(self):
        """Initialize discovery database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Discovered groups
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS discovered_groups (
                group_id INTEGER PRIMARY KEY,
                title TEXT,
                username TEXT,
                invite_link TEXT,
                discovery_method TEXT,
                discovered_at TIMESTAMP,
                discovered_from INTEGER,
                member_count INTEGER,
                online_count INTEGER,
                description TEXT,
                is_verified INTEGER,
                is_scam INTEGER,
                is_fake INTEGER,
                latitude REAL,
                longitude REAL,
                distance INTEGER,
                quality_score REAL,
                quality_level TEXT,
                spam_indicators TEXT,
                messages_per_day REAL,
                activity_score REAL,
                is_joined INTEGER,
                joined_at TIMESTAMP,
                join_attempts INTEGER,
                last_updated TIMESTAMP
            )
        """
        )

        # Invite links
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS invite_links (
                link_hash TEXT PRIMARY KEY,
                full_link TEXT,
                group_id INTEGER,
                discovered_at TIMESTAMP,
                source TEXT,
                is_valid INTEGER,
                last_checked TIMESTAMP,
                uses_count INTEGER DEFAULT 0
            )
        """
        )

        # Location profiles
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS location_profiles (
                profile_id TEXT PRIMARY KEY,
                name TEXT,
                latitude REAL,
                longitude REAL,
                country TEXT,
                city TEXT,
                radius_km REAL,
                last_used TIMESTAMP
            )
        """
        )

        # Discovery log
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS discovery_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                method TEXT,
                groups_found INTEGER,
                timestamp TIMESTAMP,
                parameters TEXT,
                success INTEGER
            )
        """
        )

        # Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_group_quality ON discovered_groups(quality_score DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_group_method ON discovered_groups(discovery_method)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_group_joined ON discovered_groups(is_joined)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_valid ON invite_links(is_valid)")

        conn.commit()
        conn.close()
        logger.info("Group discovery database initialized")

    def _load_discovered_ids(self):
        """Load discovered group IDs into memory."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT group_id FROM discovered_groups")
        self._discovered_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        logger.info(f"Loaded {len(self._discovered_ids)} discovered group IDs")

    async def discover_nearby_groups(
        self, client: Client, location: LocationProfile, max_groups: int = 50
    ) -> List[DiscoveredGroup]:
        """Discover nearby groups using geolocation.

        Args:
            client: Pyrogram client
            location: Location profile
            max_groups: Maximum groups to discover

        Returns:
            List of discovered groups
        """
        try:
            # Get nearby chats
            nearby = await client.get_nearby_chats(
                latitude=location.latitude, longitude=location.longitude
            )

            discovered = []
            for chat in nearby[:max_groups]:
                if chat.id not in self._discovered_ids:
                    group = await self._process_discovered_group(
                        client, chat, DiscoveryMethod.NEARBY, location=location
                    )
                    if group:
                        discovered.append(group)
                        self._save_group(group)

            self._log_discovery(
                DiscoveryMethod.NEARBY,
                len(discovered),
                True,
                {
                    "location": location.name,
                    "coordinates": f"{location.latitude},{location.longitude}",
                },
            )

            logger.info(f"Discovered {len(discovered)} nearby groups at {location.name}")
            return discovered

        except FloodWait as e:
            logger.warning(f"FloodWait on nearby discovery: {e.value}s")
            await asyncio.sleep(e.value)
            return []
        except Exception as e:
            logger.error(f"Error discovering nearby groups: {e}", exc_info=True)
            self._log_discovery(DiscoveryMethod.NEARBY, 0, False, {"error": str(e)})
            return []

    async def discover_from_common_groups(
        self, client: Client, user_ids: List[int], max_per_user: int = 10
    ) -> List[DiscoveredGroup]:
        """Discover groups through common groups with users.

        Args:
            client: Pyrogram client
            user_ids: List of user IDs
            max_per_user: Max groups per user

        Returns:
            List of discovered groups
        """
        discovered = []

        for user_id in user_ids:
            try:
                common = await client.get_common_chats(user_id)

                for chat in common[:max_per_user]:
                    if chat.id not in self._discovered_ids:
                        group = await self._process_discovered_group(
                            client, chat, DiscoveryMethod.COMMON_GROUPS, source_id=user_id
                        )
                        if group:
                            discovered.append(group)
                            self._save_group(group)

                # Rate limiting
                await asyncio.sleep(random.uniform(2, 5))

            except (FloodWait, PeerIdInvalid) as e:
                logger.debug(f"Error getting common groups for {user_id}: {e}")
                continue

        self._log_discovery(
            DiscoveryMethod.COMMON_GROUPS, len(discovered), True, {"users_checked": len(user_ids)}
        )

        logger.info(f"Discovered {len(discovered)} groups from common groups")
        return discovered

    async def validate_invite_link(
        self, client: Client, invite_link: str
    ) -> Optional[DiscoveredGroup]:
        """Validate and process an invite link.

        Args:
            client: Pyrogram client
            invite_link: Invite link to validate

        Returns:
            DiscoveredGroup if valid, None otherwise
        """
        try:
            # Extract hash from link
            match = re.search(r"t\.me/(?:\+|joinchat/)([a-zA-Z0-9_-]+)", invite_link)
            if not match:
                return None

            link_hash = match.group(1)

            # Check if already processed
            if self._is_link_processed(link_hash):
                return None

            # Try to get chat preview
            chat = await client.join_chat(invite_link)

            if chat and chat.id not in self._discovered_ids:
                group = await self._process_discovered_group(
                    client, chat, DiscoveryMethod.INVITE_LINK
                )
                if group:
                    group.invite_link = invite_link
                    self._save_group(group)
                    self._save_invite_link(link_hash, invite_link, chat.id, True)
                    logger.info(f"Validated invite link for group: {chat.title}")
                    return group

            return None

        except (InviteHashExpired, InviteHashInvalid, ChannelPrivate) as e:
            logger.debug(f"Invalid invite link: {e}")
            self._save_invite_link(link_hash, invite_link, None, False)
            return None
        except FloodWait as e:
            logger.warning(f"FloodWait on invite validation: {e.value}s")
            await asyncio.sleep(e.value)
            return None
        except Exception as e:
            logger.error(f"Error validating invite link: {e}")
            return None

    async def harvest_invite_links(self, text: str) -> List[str]:
        """Extract invite links from text.

        Args:
            text: Text to search

        Returns:
            List of invite links
        """
        # Regex patterns for Telegram invite links
        patterns = [
            r"https?://t\.me/\+[a-zA-Z0-9_-]+",
            r"https?://t\.me/joinchat/[a-zA-Z0-9_-]+",
            r"t\.me/\+[a-zA-Z0-9_-]+",
            r"t\.me/joinchat/[a-zA-Z0-9_-]+",
        ]

        links = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            links.extend(matches)

        # Normalize links
        normalized = []
        for link in links:
            if not link.startswith("http"):
                link = f"https://{link}"
            normalized.append(link)

        return list(set(normalized))  # Remove duplicates

    async def analyze_group_events(
        self, client: Client, group_id: int, days: int = 2
    ) -> Dict[str, Any]:
        """Analyze group event log for intelligence.

        Args:
            client: Pyrogram client
            group_id: Group ID to analyze
            days: Days of history

        Returns:
            Dictionary with analysis results
        """
        try:
            events = []
            async for event in client.get_chat_event_log(group_id):
                events.append(event)
                if len(events) >= 100:  # Limit
                    break

            analysis = {
                "total_events": len(events),
                "member_joins": 0,
                "member_leaves": 0,
                "admin_actions": 0,
                "message_deletions": 0,
                "title_changes": 0,
                "active_admins": set(),
                "growth_trend": "stable",
            }

            for event in events:
                if hasattr(event, "action"):
                    action = str(event.action)
                    if "join" in action.lower():
                        analysis["member_joins"] += 1
                    elif "left" in action.lower():
                        analysis["member_leaves"] += 1
                    elif "delete" in action.lower():
                        analysis["message_deletions"] += 1
                    elif "title" in action.lower():
                        analysis["title_changes"] += 1

                    analysis["admin_actions"] += 1
                    if hasattr(event, "user_id"):
                        analysis["active_admins"].add(event.user_id)

            # Calculate growth trend
            if analysis["member_joins"] > analysis["member_leaves"] * 1.5:
                analysis["growth_trend"] = "growing"
            elif analysis["member_leaves"] > analysis["member_joins"] * 1.5:
                analysis["growth_trend"] = "declining"

            analysis["active_admins"] = len(analysis["active_admins"])

            logger.info(f"Analyzed events for group {group_id}: {analysis['total_events']} events")
            return analysis

        except ChatAdminRequired:
            logger.debug(f"Cannot access event log for group {group_id}: not admin")
            return {}
        except Exception as e:
            logger.error(f"Error analyzing group events: {e}")
            return {}

    async def _process_discovered_group(
        self,
        client: Client,
        chat: Chat,
        method: DiscoveryMethod,
        source_id: Optional[int] = None,
        location: Optional[LocationProfile] = None,
    ) -> Optional[DiscoveredGroup]:
        """Process a discovered group and extract information.

        Args:
            client: Pyrogram client
            chat: Chat object
            method: Discovery method
            source_id: Source user/group ID
            location: Location profile if from nearby

        Returns:
            DiscoveredGroup object
        """
        try:
            group = DiscoveredGroup(
                group_id=chat.id,
                title=chat.title,
                username=chat.username,
                discovery_method=method,
                discovered_from=source_id,
                member_count=chat.members_count if hasattr(chat, "members_count") else None,
                description=chat.description if hasattr(chat, "description") else None,
                is_verified=chat.is_verified if hasattr(chat, "is_verified") else False,
                is_scam=chat.is_scam if hasattr(chat, "is_scam") else False,
                is_fake=chat.is_fake if hasattr(chat, "is_fake") else False,
            )

            # Location data
            if location:
                group.latitude = location.latitude
                group.longitude = location.longitude
                if hasattr(chat, "distance"):
                    group.distance = chat.distance

            # Get online count if possible
            try:
                online_count = await client.get_chat_online_count(chat.id)
                group.online_count = online_count
            except Exception:
                pass  # Not all chats support online count

            # Calculate quality score
            group.quality_score = self._calculate_quality_score(group)
            group.quality_level = self._get_quality_level(group.quality_score)

            # Mark as discovered
            self._discovered_ids.add(chat.id)

            return group

        except Exception as e:
            logger.error(f"Error processing group {chat.id}: {e}")
            return None

    def _calculate_quality_score(self, group: DiscoveredGroup) -> float:
        """Calculate group quality score (0-100).

        Args:
            group: DiscoveredGroup object

        Returns:
            Quality score
        """
        score = 50.0  # Base score

        # Verified groups get bonus
        if group.is_verified:
            score += 20

        # Scam/fake penalties
        if group.is_scam or group.is_fake:
            score -= 50
            group.spam_indicators.append("marked_as_scam_or_fake")

        # Member count scoring
        if group.member_count:
            if group.member_count > 10000:
                score += 15
            elif group.member_count > 1000:
                score += 10
            elif group.member_count > 100:
                score += 5
            elif group.member_count < 10:
                score -= 10
                group.spam_indicators.append("very_low_member_count")

        # Online ratio (if available)
        if group.online_count and group.member_count:
            online_ratio = group.online_count / group.member_count
            if online_ratio > 0.1:  # More than 10% online is good
                score += 10
            elif online_ratio < 0.01:  # Less than 1% online is concerning
                score -= 5

        # Username presence (public groups are generally better quality)
        if group.username:
            score += 5

        # Description presence
        if group.description and len(group.description) > 20:
            score += 5

        # Spam indicator checks in title/description
        spam_keywords = [
            "free",
            "download",
            "movie",
            "xxx",
            "porn",
            "18+",
            "casino",
            "bet",
            "earn",
            "money",
            "prize",
        ]
        title_lower = group.title.lower()

        spam_count = sum(1 for kw in spam_keywords if kw in title_lower)
        if spam_count >= 2:
            score -= 15
            group.spam_indicators.append(f"spam_keywords_in_title: {spam_count}")

        return max(0.0, min(100.0, score))

    def _get_quality_level(self, score: float) -> GroupQuality:
        """Convert quality score to level."""
        if score >= 80:
            return GroupQuality.EXCELLENT
        elif score >= 60:
            return GroupQuality.GOOD
        elif score >= 40:
            return GroupQuality.AVERAGE
        elif score >= 20:
            return GroupQuality.POOR
        else:
            return GroupQuality.SPAM

    def _save_group(self, group: DiscoveredGroup):
        """Save discovered group to database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO discovered_groups VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """,
            (
                group.group_id,
                group.title,
                group.username,
                group.invite_link,
                group.discovery_method.value,
                group.discovered_at,
                group.discovered_from,
                group.member_count,
                group.online_count,
                group.description,
                int(group.is_verified),
                int(group.is_scam),
                int(group.is_fake),
                group.latitude,
                group.longitude,
                group.distance,
                group.quality_score,
                group.quality_level.value,
                json.dumps(group.spam_indicators),
                group.messages_per_day,
                group.activity_score,
                int(group.is_joined),
                group.joined_at.isoformat() if group.joined_at else None,
                group.join_attempts,
                group.last_updated,
            ),
        )

        conn.commit()
        conn.close()

    def _save_invite_link(
        self, link_hash: str, full_link: str, group_id: Optional[int], is_valid: bool
    ):
        """Save invite link to database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO invite_links 
            (link_hash, full_link, group_id, discovered_at, is_valid, last_checked)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (link_hash, full_link, group_id, datetime.now(), int(is_valid), datetime.now()),
        )
        conn.commit()
        conn.close()

    def _is_link_processed(self, link_hash: str) -> bool:
        """Check if invite link has been processed."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM invite_links WHERE link_hash = ?", (link_hash,))
        result = cursor.fetchone() is not None
        conn.close()
        return result

    def _log_discovery(
        self, method: DiscoveryMethod, groups_found: int, success: bool, params: Dict = None
    ):
        """Log a discovery operation."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO discovery_log (method, groups_found, timestamp, parameters, success)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                method.value,
                groups_found,
                datetime.now(),
                json.dumps(params) if params else None,
                int(success),
            ),
        )
        conn.commit()
        conn.close()

    def get_top_quality_groups(
        self, limit: int = 50, min_score: float = 60.0, not_joined_only: bool = False
    ) -> List[DiscoveredGroup]:
        """Get top quality discovered groups.

        Args:
            limit: Maximum number to return
            min_score: Minimum quality score
            not_joined_only: Only return groups not yet joined

        Returns:
            List of DiscoveredGroup objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT * FROM discovered_groups
            WHERE quality_score >= ?
        """
        params = [min_score]

        if not_joined_only:
            query += " AND is_joined = 0"

        query += " ORDER BY quality_score DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        groups = [self._row_to_group(row) for row in cursor.fetchall()]
        conn.close()

        return groups

    def _row_to_group(self, row) -> DiscoveredGroup:
        """Convert database row to DiscoveredGroup."""
        return DiscoveredGroup(
            group_id=row[0],
            title=row[1],
            username=row[2],
            invite_link=row[3],
            discovery_method=DiscoveryMethod(row[4]),
            discovered_at=datetime.fromisoformat(row[5]) if row[5] else datetime.now(),
            discovered_from=row[6],
            member_count=row[7],
            online_count=row[8],
            description=row[9],
            is_verified=bool(row[10]),
            is_scam=bool(row[11]),
            is_fake=bool(row[12]),
            latitude=row[13],
            longitude=row[14],
            distance=row[15],
            quality_score=row[16] or 0.0,
            quality_level=GroupQuality(row[17]) if row[17] else GroupQuality.AVERAGE,
            spam_indicators=json.loads(row[18]) if row[18] else [],
            messages_per_day=row[19],
            activity_score=row[20] or 0.0,
            is_joined=bool(row[21]),
            joined_at=datetime.fromisoformat(row[22]) if row[22] else None,
            join_attempts=row[23] or 0,
            last_updated=datetime.fromisoformat(row[24]) if row[24] else datetime.now(),
        )

    def get_discovery_stats(self) -> Dict[str, Any]:
        """Get discovery statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total discovered
        cursor.execute("SELECT COUNT(*) FROM discovered_groups")
        total = cursor.fetchone()[0]

        # By method
        cursor.execute(
            """
            SELECT discovery_method, COUNT(*) 
            FROM discovered_groups 
            GROUP BY discovery_method
        """
        )
        by_method = dict(cursor.fetchall())

        # By quality
        cursor.execute(
            """
            SELECT quality_level, COUNT(*) 
            FROM discovered_groups 
            GROUP BY quality_level
        """
        )
        by_quality = dict(cursor.fetchall())

        # Average quality
        cursor.execute("SELECT AVG(quality_score) FROM discovered_groups")
        avg_quality = cursor.fetchone()[0] or 0.0

        # Joined vs not joined
        cursor.execute(
            """
            SELECT is_joined, COUNT(*) 
            FROM discovered_groups 
            GROUP BY is_joined
        """
        )
        join_status = dict(cursor.fetchall())

        conn.close()

        return {
            "total_discovered": total,
            "by_method": by_method,
            "by_quality": by_quality,
            "average_quality": avg_quality,
            "join_status": join_status,
        }


# Predefined location profiles for discovery
LOCATION_PROFILES = {
    "new_york": LocationProfile(40.7128, -74.0060, "New York, USA", "US", "New York"),
    "london": LocationProfile(51.5074, -0.1278, "London, UK", "GB", "London"),
    "tokyo": LocationProfile(35.6762, 139.6503, "Tokyo, Japan", "JP", "Tokyo"),
    "dubai": LocationProfile(25.2048, 55.2708, "Dubai, UAE", "AE", "Dubai"),
    "singapore": LocationProfile(1.3521, 103.8198, "Singapore", "SG", "Singapore"),
    "sydney": LocationProfile(-33.8688, 151.2093, "Sydney, Australia", "AU", "Sydney"),
    "berlin": LocationProfile(52.5200, 13.4050, "Berlin, Germany", "DE", "Berlin"),
    "paris": LocationProfile(48.8566, 2.3522, "Paris, France", "FR", "Paris"),
    "los_angeles": LocationProfile(34.0522, -118.2437, "Los Angeles, USA", "US", "Los Angeles"),
    "mumbai": LocationProfile(19.0760, 72.8777, "Mumbai, India", "IN", "Mumbai"),
}
