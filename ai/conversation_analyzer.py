"""
Conversation Analyzer - Pattern analysis and success tracking.

Features:
- Analyze successful conversation patterns
- Extract winning message templates
- Track conversion paths
- Identify optimal conversation flows
"""

import hashlib
import logging
import sqlite3
import json
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
from contextlib import contextmanager
import statistics

logger = logging.getLogger(__name__)


@dataclass
class ConversationFlow:
    """Represents a conversation flow pattern."""
    flow_id: str
    messages: List[str] = field(default_factory=list)
    user_responses: List[str] = field(default_factory=list)
    outcome: str = "unknown"  # success, failed, ongoing
    conversion_value: float = 0.0
    duration_minutes: float = 0.0
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None


@dataclass
class MessagePattern:
    """Successful message pattern."""
    pattern_id: str
    message_template: str
    keywords: List[str] = field(default_factory=list)
    avg_response_time: float = 0.0
    response_rate: float = 0.0
    conversion_rate: float = 0.0
    times_used: int = 0
    success_count: int = 0


class ConversationAnalyzer:
    """Analyze conversation patterns and success rates."""
    
    def __init__(self, db_path: str = "conversation_analytics.db"):
        """Initialize."""
        self.db_path = db_path
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool
            self._connection_pool = get_pool(self.db_path)
        except Exception as e:
            logger.debug(f"Error initializing conversation analyzer database (non-critical): {e}")
            pass
        self._init_database()
    
    def _get_connection(self):
        if self._connection_pool:
            return self._connection_pool.get_connection()
        else:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

    @contextmanager
    def _connection_context(self):
        """Context manager for database operations."""
        conn_manager = self._get_connection()
        if hasattr(conn_manager, '__enter__'):
            # Using connection pool (already a context manager)
            with conn_manager as conn:
                yield conn
        else:
            # Direct connection
            try:
                yield conn_manager
            finally:
                try:
                    conn_manager.close()
                except Exception:
                    pass
        self.max_sentiment_records_per_user = 500
        self._stage_has_user_id = False
        self._ensure_stage_schema()
        self._ensure_stage_indexes()
        self._prune_old_flows()
        self._prune_sentiment_history()
    
    def _init_database(self):
        """Initialize analytics database."""
        with self._connection_context() as conn:
            cursor = conn.cursor()

            # Conversation flows
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_flows (
                    flow_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    messages TEXT,
                    user_responses TEXT,
                    outcome TEXT,
                    conversion_value REAL,
                    duration_minutes REAL,
                    started_at TIMESTAMP,
                    ended_at TIMESTAMP
                )
            """)

            # Message patterns
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    message_template TEXT,
                    keywords TEXT,
                    avg_response_time REAL,
                    response_rate REAL,
                    conversion_rate REAL,
                    times_used INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP,
                    last_used TIMESTAMP
                )
            """)

            # Conversation stages
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_stages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flow_id TEXT,
                    stage_number INTEGER,
                    our_message TEXT,
                    user_response TEXT,
                    response_time REAL,
                    sentiment_score REAL,
                    timestamp TIMESTAMP
                )
            """)

            # Successful conversions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flow_id TEXT,
                    user_id INTEGER,
                    conversion_type TEXT,
                    value REAL,
                    messages_to_convert INTEGER,
                    time_to_convert REAL,
                    timestamp TIMESTAMP
                )
            """)

            conn.commit()
        logger.info("Conversation analytics database initialized")

    def _ensure_stage_schema(self):
        """Add missing columns to conversation_stages for sentiment tracking."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(conversation_stages)")
            columns = {row[1] for row in cursor.fetchall()}

            if "user_id" not in columns:
                try:
                    cursor.execute("ALTER TABLE conversation_stages ADD COLUMN user_id INTEGER")
                    conn.commit()
                    columns.add("user_id")
                except sqlite3.OperationalError as exc:
                    logger.warning(f"Failed to add user_id to conversation_stages: {exc}")

            if "timestamp" not in columns:
                try:
                    cursor.execute("ALTER TABLE conversation_stages ADD COLUMN timestamp TIMESTAMP")
                    conn.commit()
                except sqlite3.OperationalError as exc:
                    logger.warning(f"Failed to backfill timestamp column: {exc}")

            self._stage_has_user_id = "user_id" in columns
        except Exception as exc:
            logger.error(f"Failed to verify stage schema: {exc}")
        finally:
            if conn:
                conn.close()

    def _ensure_stage_indexes(self):
        """Create indexes to keep stage lookups and pruning efficient."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            if self._stage_has_user_id:
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_conversation_stages_user_timestamp "
                    "ON conversation_stages(user_id, timestamp)"
                )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_stages_flow "
                "ON conversation_stages(flow_id)"
            )
            conn.commit()
        except Exception as exc:
            logger.warning(f"Failed to ensure conversation stage indexes: {exc}")
        finally:
            if conn:
                conn.close()

    def _prune_old_flows(self):
        """Remove stale conversation flows and associated data."""
        try:
            cutoff = datetime.now() - timedelta(days=self.flow_retention_days)
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT flow_id FROM conversation_flows WHERE ended_at IS NOT NULL AND ended_at < ?", (cutoff,))
            stale_ids = [row[0] for row in cursor.fetchall()]

            if stale_ids:
                cursor.executemany("DELETE FROM conversation_stages WHERE flow_id = ?", [(fid,) for fid in stale_ids])
                cursor.executemany("DELETE FROM conversions WHERE flow_id = ?", [(fid,) for fid in stale_ids])
                cursor.executemany("DELETE FROM conversation_flows WHERE flow_id = ?", [(fid,) for fid in stale_ids])
                conn.commit()

            conn.close()
        except Exception as exc:
            logger.debug(f"Failed to prune old conversation flows: {exc}")

    def _prune_sentiment_history(self):
        """Limit sentiment history depth per user to bound storage growth."""
        if not self._stage_has_user_id:
            return

        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT user_id, COUNT(*) AS cnt
                FROM conversation_stages
                WHERE user_id IS NOT NULL
                GROUP BY user_id
                HAVING cnt > ?
                """,
                (self.max_sentiment_records_per_user,)
            )

            for user_id, _ in cursor.fetchall():
                cursor.execute(
                    """
                    DELETE FROM conversation_stages
                    WHERE id IN (
                        SELECT id FROM conversation_stages
                        WHERE user_id = ?
                        ORDER BY COALESCE(timestamp, '1970-01-01') DESC, id DESC
                        LIMIT -1 OFFSET ?
                    )
                    """,
                    (user_id, self.max_sentiment_records_per_user)
                )

            conn.commit()
        except Exception as exc:
            logger.error(f"Failed to prune sentiment history: {exc}")
        finally:
            if conn:
                conn.close()
    
    def analyze_conversation(self, flow_id: str, user_id: int,
                           messages: List[str], responses: List[str],
                           outcome: str, value: float = 0.0,
                           timestamps: Optional[List[Tuple[datetime, datetime]]] = None) -> Dict:
        """Analyze a complete conversation.
        
        Args:
            flow_id: Conversation flow ID
            user_id: User ID
            messages: Our messages
            responses: User responses
            outcome: Conversation outcome
            value: Conversion value if applicable
            
        Returns:
            Analysis results
        """
        # Extract patterns
        patterns = self._extract_patterns(messages, responses, outcome)
        
        # Calculate metrics
        response_times = self._calculate_response_times(messages, responses, timestamps)
        
        # Save flow
        self._save_conversation_flow(flow_id, user_id, messages, responses,
                                    outcome, value, response_times, timestamps)
        
        # Update patterns
        for pattern in patterns:
            self._update_pattern(pattern)
        
        return {
            'flow_id': flow_id,
            'patterns_found': len(patterns),
            'outcome': outcome,
            'value': value,
            'avg_response_time': statistics.mean(response_times) if response_times else 0
        }
    
    def _extract_patterns(self, messages: List[str], responses: List[str], 
                         outcome: str) -> List[MessagePattern]:
        """Extract successful patterns from conversation."""
        patterns = []
        
        for i, msg in enumerate(messages):
            if i < len(responses):
                # Extract keywords
                keywords = self._extract_keywords(msg)

                # Check if message got a response
                got_response = bool(responses[i])
                was_successful = outcome == "success"

                deterministic_id = hashlib.sha256(msg.strip().encode('utf-8')).hexdigest()[:16]

                pattern = MessagePattern(
                    pattern_id=f"pattern_{deterministic_id}",
                    message_template=self._templatize_message(msg),
                    keywords=keywords,
                    response_rate=1.0 if got_response else 0.0,
                    conversion_rate=1.0 if was_successful else 0.0,
                    times_used=1,
                    success_count=1 if was_successful else 0
                )
                patterns.append(pattern)
        
        return patterns
    
    def _extract_keywords(self, message: str) -> List[str]:
        """Extract keywords from message."""
        # Simple keyword extraction
        words = re.findall(r'\w+', message.lower())
        # Filter stopwords (simplified)
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        keywords = [w for w in words if len(w) > 3 and w not in stopwords]
        return keywords[:10]  # Top 10
    
    def _templatize_message(self, message: str) -> str:
        """Convert message to template by replacing specific values."""
        # Replace numbers with placeholders
        template = re.sub(r'\d+', '{number}', message)
        # Replace prices
        template = re.sub(r'\$\{number\}', '{price}', template)
        return template
    
    def _calculate_response_times(self, messages: List[str], responses: List[str],
                                  timestamps: Optional[List[Tuple[datetime, datetime]]] = None) -> List[float]:
        """Calculate response times using provided timestamps; fallback to zero."""
        pair_count = min(len(messages), len(responses))
        if not timestamps:
            return [0.0 for _ in range(pair_count)]

        cleaned = []
        for idx in range(pair_count):
            try:
                sent_at, responded_at = timestamps[idx]
                if sent_at and responded_at:
                    cleaned.append(max((responded_at - sent_at).total_seconds(), 0.0))
                else:
                    cleaned.append(0.0)
            except Exception:
                cleaned.append(0.0)
        return cleaned

    def _score_sentiment(self, text: str) -> float:
        """Very lightweight sentiment heuristic in range [-1, 1]."""
        if not text:
            return 0.0

        positive_words = {"great", "thanks", "thank", "awesome", "good", "love", "amazing", "perfect", "yes"}
        negative_words = {"bad", "no", "hate", "angry", "upset", "terrible", "refund", "cancel", "problem"}

        words = re.findall(r"\w+", text.lower())
        score = 0
        for word in words:
            if word in positive_words:
                score += 1
            if word in negative_words:
                score -= 1

        if not words:
            return 0.0

        normalized = max(-1.0, min(1.0, score / len(words)))
        return normalized
    
    def _save_conversation_flow(self, flow_id: str, user_id: int,
                                messages: List[str], responses: List[str],
                                outcome: str, value: float, response_times: List[float],
                                timestamps: Optional[List[Tuple[datetime, datetime]]] = None):
        """Save conversation flow to database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        duration = sum(response_times) if response_times else 0.0
        started_at = timestamps[0][0] if timestamps and timestamps[0][0] else datetime.now()
        ended_at = timestamps[-1][1] if timestamps and timestamps[-1][1] else datetime.now()
        
        cursor.execute("""
            INSERT OR REPLACE INTO conversation_flows
            (flow_id, user_id, messages, user_responses, outcome, conversion_value,
             duration_minutes, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (flow_id, user_id, json.dumps(messages), json.dumps(responses),
              outcome, value, duration, started_at, ended_at))
        
        # Save individual stages
        for i, (msg, resp) in enumerate(zip(messages, responses)):
            resp_time = response_times[i] if i < len(response_times) else 0
            sentiment = self._score_sentiment(resp)
            sent_at, responded_at = (timestamps[i] if timestamps and i < len(timestamps) else (None, None))
            stage_timestamp = responded_at or sent_at or datetime.now()
            columns = [
                "flow_id", "stage_number", "our_message", "user_response",
                "response_time", "sentiment_score", "timestamp"
            ]
            params = [flow_id, i + 1, msg, resp, resp_time, sentiment, stage_timestamp]

            if self._stage_has_user_id:
                columns.append("user_id")
                params.append(user_id)

            placeholders = ", ".join(["?"] * len(columns))
            cursor.execute(
                f"INSERT INTO conversation_stages ({', '.join(columns)}) VALUES ({placeholders})",
                params
            )
        
        conn.commit()
        conn.close()

        # Enforce per-user sentiment history limits after each flow save
        self._prune_sentiment_history()
    
    def _update_pattern(self, pattern: MessagePattern):
        """Update or create message pattern."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT times_used, success_count FROM message_patterns WHERE pattern_id = ?",
                      (pattern.pattern_id,))
        row = cursor.fetchone()
        
        if row:
            # Update existing
            new_times = row[0] + pattern.times_used
            new_success = row[1] + pattern.success_count
            new_conversion = new_success / new_times if new_times > 0 else 0
            
            cursor.execute("""
                UPDATE message_patterns 
                SET times_used = ?, success_count = ?, conversion_rate = ?, last_used = ?
                WHERE pattern_id = ?
            """, (new_times, new_success, new_conversion, datetime.now(), pattern.pattern_id))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO message_patterns
                (pattern_id, message_template, keywords, response_rate, conversion_rate,
                 times_used, success_count, created_at, last_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (pattern.pattern_id, pattern.message_template, json.dumps(pattern.keywords),
                  pattern.response_rate, pattern.conversion_rate, pattern.times_used,
                  pattern.success_count, datetime.now(), datetime.now()))
        
        conn.commit()
        conn.close()
    
    def get_top_patterns(self, limit: int = 10, min_uses: int = 3) -> List[MessagePattern]:
        """Get top performing message patterns."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM message_patterns
            WHERE times_used >= ?
            ORDER BY conversion_rate DESC, times_used DESC
            LIMIT ?
        """, (min_uses, limit))
        
        patterns = []
        for row in cursor.fetchall():
            pattern = MessagePattern(
                pattern_id=row[0],
                message_template=row[1],
                keywords=json.loads(row[2]) if row[2] else [],
                avg_response_time=row[3] or 0.0,
                response_rate=row[4] or 0.0,
                conversion_rate=row[5] or 0.0,
                times_used=row[6] or 0,
                success_count=row[7] or 0
            )
            patterns.append(pattern)
        
        conn.close()
        return patterns
    
    def get_conversion_insights(self) -> Dict:
        """Get insights about successful conversions."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Average messages to convert
        cursor.execute("""
            SELECT AVG(messages_to_convert), AVG(time_to_convert), COUNT(*)
            FROM conversions
        """)
        row = cursor.fetchone()
        
        insights = {
            'avg_messages_to_convert': row[0] or 0,
            'avg_time_to_convert': row[1] or 0,
            'total_conversions': row[2] or 0
        }
        
        # Best performing flows
        cursor.execute("""
            SELECT messages, conversion_value FROM conversation_flows
            WHERE outcome = 'success'
            ORDER BY conversion_value DESC
            LIMIT 10
        """)
        
        best_flows = []
        for row in cursor.fetchall():
            best_flows.append({
                'messages': json.loads(row[0]) if row[0] else [],
                'value': row[1]
            })
        
        insights['best_flows'] = best_flows
        conn.close()
        return insights


