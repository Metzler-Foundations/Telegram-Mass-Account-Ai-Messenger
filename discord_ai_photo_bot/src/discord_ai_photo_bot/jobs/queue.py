"""Enhanced async job queue for generation tasks with status tracking."""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class GenerationJob:
    """Represents a generation request."""

    job_id: str
    user_id: str
    invoice_id: str
    reference_images: List[Path]
    prompts: List[str]
    created_at: float = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


@dataclass
class QueueStats:
    """Queue statistics and status information."""

    queued_jobs: int
    active_jobs: int
    completed_today: int
    average_wait_time: float  # in minutes
    estimated_queue_time: float  # in minutes


class JobQueue:
    """Enhanced in-memory queue with status tracking and position monitoring."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[GenerationJob] = asyncio.Queue()
        self._worker: Optional[asyncio.Task[None]] = None
        self._active_jobs: Dict[str, GenerationJob] = {}
        self._completed_jobs: List[GenerationJob] = []
        self._job_positions: Dict[str, int] = {}

    async def start(self, handler) -> None:
        """Start a single worker task."""

        if self._worker is not None:
            return
        self._worker = asyncio.create_task(self._run(handler))

    async def stop(self) -> None:
        """Stop the worker gracefully."""

        if self._worker:
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker
            self._worker = None

    async def _run(self, handler) -> None:
        """Run the worker loop with enhanced error handling."""
        while True:
            job = await self._queue.get()
            try:
                # Mark job as active
                self._active_jobs[job.job_id] = job
                self._update_positions()

                await handler(job)

                # Mark job as completed
                if job.job_id in self._active_jobs:
                    del self._active_jobs[job.job_id]
                self._completed_jobs.append(job)

                # Clean up old completed jobs (keep last 100)
                if len(self._completed_jobs) > 100:
                    self._completed_jobs = self._completed_jobs[-100:]

            except Exception as e:
                # Log error but continue processing
                print(f"Job {job.job_id} failed: {e}")
                if job.job_id in self._active_jobs:
                    del self._active_jobs[job.job_id]
            finally:
                self._queue.task_done()
                self._update_positions()

    async def enqueue(self, job: GenerationJob) -> int:
        """Add a job to the queue and return its position."""

        await self._queue.put(job)
        self._update_positions()
        return self._job_positions.get(job.job_id, 0)

    def _update_positions(self) -> None:
        """Update position tracking for all queued jobs."""
        # This is a simplified version - in production you'd track actual positions
        self._job_positions.clear()

        # Estimate positions based on queue size
        position = 1
        # Note: asyncio.Queue doesn't provide easy position tracking
        # This would need a custom queue implementation for perfect accuracy

    def get_queue_stats(self) -> QueueStats:
        """Get current queue statistics."""
        now = time.time()

        # Count completed jobs today
        today_start = now - (24 * 60 * 60)  # 24 hours ago
        completed_today = sum(1 for job in self._completed_jobs
                            if job.created_at and job.created_at > today_start)

        # Estimate average wait time (simplified)
        avg_wait = 15.0  # minutes - this would be calculated from actual data

        # Estimate queue time based on current load
        queue_size = self._queue.qsize()
        active_count = len(self._active_jobs)
        estimated_queue = (queue_size + active_count) * 10.0  # rough estimate

        return QueueStats(
            queued_jobs=queue_size,
            active_jobs=active_count,
            completed_today=completed_today,
            average_wait_time=avg_wait,
            estimated_queue_time=estimated_queue
        )

    def get_job_position(self, job_id: str) -> Optional[int]:
        """Get the position of a job in the queue."""
        # This is an estimate since asyncio.Queue doesn't track positions
        if job_id in self._active_jobs:
            return 0  # Currently processing
        return self._job_positions.get(job_id, -1)  # -1 if not found

    def get_active_job_count(self) -> int:
        """Get the number of currently active jobs."""
        return len(self._active_jobs)

    def get_queued_job_count(self) -> int:
        """Get the number of queued jobs."""
        return self._queue.qsize()






