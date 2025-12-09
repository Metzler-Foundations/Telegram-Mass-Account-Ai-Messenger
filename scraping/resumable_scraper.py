"""
Resumable Scraping System - Persist cursors for resume after interruption.

Features:
- Checkpoint persistence to database
- Resume from last successful position
- Partial result recovery on failures
- Progress tracking per scraping job
- Multi-method scraping state management
"""

import logging
import sqlite3
import json
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class ScrapingMethod(Enum):
    """Scraping method types."""

    ADMINISTRATORS = "administrators"
    VISIBLE_MEMBERS = "visible_members"
    MESSAGE_HISTORY = "message_history"
    REACTIONS = "reactions"
    MEDIA_ANALYSIS = "media_analysis"


class JobStatus(Enum):
    """Scraping job status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScrapingCheckpoint:
    """Checkpoint data for resumable scraping."""

    job_id: str
    channel_id: str
    channel_name: str
    method: ScrapingMethod
    cursor_position: Optional[int] = None  # Message ID or offset
    members_scraped: int = 0
    last_user_id: Optional[int] = None
    progress_percentage: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = None
    updated_at: datetime = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["method"] = self.method.value
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            data["updated_at"] = self.updated_at.isoformat()
        if self.metadata:
            data["metadata"] = json.dumps(self.metadata)
        return data


@dataclass
class ScrapingJob:
    """Scraping job with resume capability."""

    job_id: str
    channel_identifier: str
    status: JobStatus
    total_members_found: int = 0
    methods_completed: List[str] = None
    checkpoints: Dict[str, ScrapingCheckpoint] = None
    partial_results: List[int] = None  # User IDs scraped so far
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.methods_completed is None:
            self.methods_completed = []
        if self.checkpoints is None:
            self.checkpoints = {}
        if self.partial_results is None:
            self.partial_results = []


class ResumableScraperManager:
    """
    Manager for resumable scraping jobs with checkpoint persistence.
    """

    def __init__(self, db_path: str = "scraping_checkpoints.db"):
        """Initialize resumable scraper manager."""
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
        return sqlite3.connect(self.db_path)

    def _init_database(self):
        """Initialize checkpoint database."""
        with self._get_connection() as conn:
            # Scraping jobs table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scraping_jobs (
                    job_id TEXT PRIMARY KEY,
                    channel_identifier TEXT NOT NULL,
                    channel_id TEXT,
                    channel_name TEXT,
                    status TEXT NOT NULL,
                    total_members_found INTEGER DEFAULT 0,
                    methods_completed TEXT,  -- JSON array
                    partial_results TEXT,    -- JSON array of user IDs
                    error_message TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Checkpoints table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scraping_checkpoints (
                    checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    channel_name TEXT,
                    method TEXT NOT NULL,
                    cursor_position INTEGER,
                    members_scraped INTEGER DEFAULT 0,
                    last_user_id INTEGER,
                    progress_percentage REAL DEFAULT 0,
                    metadata TEXT,  -- JSON
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(job_id) REFERENCES scraping_jobs(job_id)
                )
            """
            )

            # Indexes for performance
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_status 
                ON scraping_jobs(status, created_at DESC)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_channel 
                ON scraping_jobs(channel_identifier, status)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_checkpoints_job 
                ON scraping_checkpoints(job_id, method)
            """
            )

            conn.commit()

    def create_job(self, job_id: str, channel_identifier: str) -> ScrapingJob:
        """
        Create a new scraping job.

        Args:
            job_id: Unique job identifier
            channel_identifier: Channel username or ID

        Returns:
            ScrapingJob object
        """
        job = ScrapingJob(
            job_id=job_id,
            channel_identifier=channel_identifier,
            status=JobStatus.PENDING,
            started_at=datetime.now(),
        )

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO scraping_jobs 
                    (job_id, channel_identifier, status, started_at)
                    VALUES (?, ?, ?, ?)
                """,
                    (job_id, channel_identifier, job.status.value, job.started_at),
                )
                conn.commit()

            logger.info(f"Created scraping job {job_id} for {channel_identifier}")
            return job

        except Exception as e:
            logger.error(f"Failed to create scraping job: {e}")
            raise

    def save_checkpoint(
        self,
        job_id: str,
        method: ScrapingMethod,
        cursor_position: Optional[int] = None,
        members_scraped: int = 0,
        last_user_id: Optional[int] = None,
        progress_percentage: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
    ) -> bool:
        """
        Save a checkpoint for resumable scraping.

        Args:
            job_id: Job identifier
            method: Scraping method
            cursor_position: Current position (message ID, offset, etc.)
            members_scraped: Number of members scraped so far
            last_user_id: Last user ID processed
            progress_percentage: Progress as percentage
            metadata: Additional metadata
            channel_id: Channel ID
            channel_name: Channel name

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO scraping_checkpoints
                    (job_id, channel_id, channel_name, method, cursor_position, 
                     members_scraped, last_user_id, progress_percentage, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        job_id,
                        channel_id or "",
                        channel_name or "",
                        method.value,
                        cursor_position,
                        members_scraped,
                        last_user_id,
                        progress_percentage,
                        json.dumps(metadata) if metadata else None,
                        datetime.now(),
                    ),
                )
                conn.commit()

            logger.debug(
                f"Saved checkpoint for job {job_id}, method {method.value}: "
                f"{members_scraped} members, {progress_percentage:.1f}% complete"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False

    def get_job(self, job_id: str) -> Optional[ScrapingJob]:
        """Get scraping job by ID."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM scraping_jobs WHERE job_id = ?
                """,
                    (job_id,),
                )
                row = cursor.fetchone()

                if not row:
                    return None

                # Load job
                job = ScrapingJob(
                    job_id=row["job_id"],
                    channel_identifier=row["channel_identifier"],
                    status=JobStatus(row["status"]),
                    total_members_found=row["total_members_found"],
                    methods_completed=(
                        json.loads(row["methods_completed"]) if row["methods_completed"] else []
                    ),
                    partial_results=(
                        json.loads(row["partial_results"]) if row["partial_results"] else []
                    ),
                    error_message=row["error_message"],
                    started_at=(
                        datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
                    ),
                    completed_at=(
                        datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
                    ),
                )

                # Load checkpoints
                job.checkpoints = self.get_job_checkpoints(job_id)

                return job

        except Exception as e:
            logger.error(f"Failed to get job: {e}")
            return None

    def get_job_checkpoints(self, job_id: str) -> Dict[str, ScrapingCheckpoint]:
        """Get all checkpoints for a job."""
        checkpoints = {}

        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM scraping_checkpoints 
                    WHERE job_id = ?
                    ORDER BY created_at DESC
                """,
                    (job_id,),
                )

                for row in cursor:
                    method = ScrapingMethod(row["method"])
                    checkpoint = ScrapingCheckpoint(
                        job_id=row["job_id"],
                        channel_id=row["channel_id"],
                        channel_name=row["channel_name"],
                        method=method,
                        cursor_position=row["cursor_position"],
                        members_scraped=row["members_scraped"],
                        last_user_id=row["last_user_id"],
                        progress_percentage=row["progress_percentage"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                    checkpoints[method.value] = checkpoint

        except Exception as e:
            logger.error(f"Failed to get checkpoints: {e}")

        return checkpoints

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        total_members: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update job status."""
        try:
            with self._get_connection() as conn:
                if status == JobStatus.COMPLETED:
                    conn.execute(
                        """
                        UPDATE scraping_jobs
                        SET status = ?, total_members_found = ?, completed_at = ?, updated_at = ?
                        WHERE job_id = ?
                    """,
                        (status.value, total_members or 0, datetime.now(), datetime.now(), job_id),
                    )
                elif status == JobStatus.FAILED:
                    conn.execute(
                        """
                        UPDATE scraping_jobs
                        SET status = ?, error_message = ?, updated_at = ?
                        WHERE job_id = ?
                    """,
                        (status.value, error_message, datetime.now(), job_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE scraping_jobs
                        SET status = ?, updated_at = ?
                        WHERE job_id = ?
                    """,
                        (status.value, datetime.now(), job_id),
                    )

                conn.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            return False

    def save_partial_results(self, job_id: str, user_ids: List[int]) -> bool:
        """Save partial results (user IDs scraped so far)."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE scraping_jobs
                    SET partial_results = ?, total_members_found = ?, updated_at = ?
                    WHERE job_id = ?
                """,
                    (json.dumps(user_ids), len(user_ids), datetime.now(), job_id),
                )
                conn.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to save partial results: {e}")
            return False

    def mark_method_completed(self, job_id: str, method: ScrapingMethod) -> bool:
        """Mark a scraping method as completed."""
        try:
            job = self.get_job(job_id)
            if not job:
                return False

            if method.value not in job.methods_completed:
                job.methods_completed.append(method.value)

                with self._get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE scraping_jobs
                        SET methods_completed = ?, updated_at = ?
                        WHERE job_id = ?
                    """,
                        (json.dumps(job.methods_completed), datetime.now(), job_id),
                    )
                    conn.commit()

                logger.info(f"Marked method {method.value} as completed for job {job_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to mark method completed: {e}")
            return False

    def get_resumable_jobs(self) -> List[ScrapingJob]:
        """Get all jobs that can be resumed (paused or in progress)."""
        jobs = []

        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT job_id FROM scraping_jobs 
                    WHERE status IN (?, ?)
                    ORDER BY updated_at DESC
                """,
                    (JobStatus.PAUSED.value, JobStatus.IN_PROGRESS.value),
                )

                for row in cursor:
                    job = self.get_job(row["job_id"])
                    if job:
                        jobs.append(job)

        except Exception as e:
            logger.error(f"Failed to get resumable jobs: {e}")

        return jobs

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """Clean up completed/failed jobs older than specified days."""
        try:
            with self._get_connection() as conn:
                # Delete old checkpoints first
                conn.execute(
                    """
                    DELETE FROM scraping_checkpoints
                    WHERE job_id IN (
                        SELECT job_id FROM scraping_jobs
                        WHERE status IN (?, ?)
                        AND datetime(completed_at) < datetime('now', ?)
                    )
                """,
                    (JobStatus.COMPLETED.value, JobStatus.FAILED.value, f"-{days} days"),
                )

                # Delete old jobs
                cursor = conn.execute(
                    """
                    DELETE FROM scraping_jobs
                    WHERE status IN (?, ?)
                    AND datetime(completed_at) < datetime('now', ?)
                """,
                    (JobStatus.COMPLETED.value, JobStatus.FAILED.value, f"-{days} days"),
                )

                deleted = cursor.rowcount
                conn.commit()

                logger.info(f"Cleaned up {deleted} old scraping jobs")
                return deleted

        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0


# Singleton instance
_manager: Optional[ResumableScraperManager] = None


def get_resumable_scraper_manager() -> ResumableScraperManager:
    """Get singleton resumable scraper manager."""
    global _manager
    if _manager is None:
        _manager = ResumableScraperManager()
    return _manager
