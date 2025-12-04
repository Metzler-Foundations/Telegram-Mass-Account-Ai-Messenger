import asyncio
import logging
import random
import json
import os
import time
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import psutil

try:
    from ai.gemini_service import GeminiService
    GEMINI_AVAILABLE = True
except ImportError:
    # Create a dummy GeminiService class for type hints
    class GeminiService:
        pass
    GEMINI_AVAILABLE = False
from accounts.account_manager import AccountManager
from telegram.telegram_client import TelegramClient

logger = logging.getLogger(__name__)


class WarmupStage(Enum):
    """Stages of account warmup process."""
    CREATED = "created"
    INITIAL_SETUP = "initial_setup"
    PROFILE_COMPLETION = "profile_completion"
    CONTACT_BUILDING = "contact_building"
    GROUP_JOINING = "group_joining"
    CONVERSATION_STARTERS = "conversation_starters"
    ACTIVITY_INCREASE = "activity_increase"
    ADVANCED_INTERACTIONS = "advanced_interactions"
    STABILIZATION = "stabilization"
    COMPLETED = "completed"
    FAILED = "failed"


class WarmupPriority(Enum):
    """Priority levels for warmup jobs."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class WarmupJob:
    """Represents a warmup job in the queue."""
    job_id: str
    phone_number: str
    stage: WarmupStage
    priority: WarmupPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    next_attempt_at: Optional[datetime] = None
    progress: float = 0.0
    status_message: str = ""
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to strings
        data['stage'] = self.stage.value
        data['priority'] = self.priority.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WarmupJob':
        """Create from dictionary."""
        # Convert strings back to enums
        try:
            data['stage'] = WarmupStage(data['stage'])
        except Exception:
            logger.error(f"Invalid warmup stage encountered during load: {data.get('stage')}")
            data['stage'] = WarmupStage.FAILED

        try:
            data['priority'] = WarmupPriority(data['priority'])
        except Exception:
            logger.error(f"Invalid warmup priority encountered during load: {data.get('priority')}")
            data['priority'] = WarmupPriority.NORMAL

        # Convert datetime strings back to datetime objects
        for field in ['created_at', 'started_at', 'completed_at', 'last_activity', 'next_attempt_at']:
            if data.get(field) and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except (ValueError, TypeError):
                    # If parsing fails, set to None
                    data[field] = None

        return cls(**data)


@dataclass
class WarmupConfig:
    """Configuration for account warmup."""
    # Timing configurations
    initial_delay_hours: int = 24  # Wait 24 hours after creation
    stage_delays: Dict[str, int] = None  # Hours between stages
    daily_activity_limit: int = 20  # Max activities per day
    session_max_duration: int = 30  # Max minutes per session

    # Activity configurations
    contacts_per_day: int = 5
    groups_per_day: int = 2
    messages_per_day: int = 10
    profile_updates_per_day: int = 1

    # Safety configurations
    min_delay_between_actions: int = 30  # Seconds
    max_delay_between_actions: int = 300  # Seconds
    ip_rotation_frequency: int = 10  # Change IP every N actions

    # AI configurations
    use_gemini_for_responses: bool = True
    use_gemini_for_decisions: bool = True
    
    # Blackout windows (hours in UTC, 0-23)
    blackout_window_1_start: Optional[int] = 2  # 2 AM UTC
    blackout_window_1_end: Optional[int] = 6  # 6 AM UTC
    blackout_window_2_start: Optional[int] = None
    blackout_window_2_end: Optional[int] = None
    
    # Stage weights for time allocation (relative importance)
    stage_weights: Dict[str, float] = None

    def __post_init__(self):
        if self.stage_delays is None:
            self.stage_delays = {
                'initial_setup': 6,
                'profile_completion': 12,
                'contact_building': 24,
                'group_joining': 48,
                'conversation_starters': 72,
                'activity_increase': 96,
                'advanced_interactions': 120,
                'stabilization': 168  # 1 week
            }
        
        if self.stage_weights is None:
            self.stage_weights = {
                'initial_setup': 0.5,           # Quick setup
                'profile_completion': 1.0,      # Standard weight
                'contact_building': 1.5,        # More important
                'group_joining': 1.5,           # More important
                'conversation_starters': 2.0,   # High importance
                'activity_increase': 2.0,       # High importance
                'advanced_interactions': 1.5,   # Moderate
                'stabilization': 3.0            # Most critical
            }
    
    def is_in_blackout_window(self, check_time: Optional[datetime] = None) -> bool:
        """Check if current time is within a blackout window."""
        if check_time is None:
            check_time = datetime.now()
        
        current_hour = check_time.hour
        
        # Check window 1
        if self.blackout_window_1_start is not None and self.blackout_window_1_end is not None:
            if self._is_hour_in_range(current_hour, self.blackout_window_1_start, self.blackout_window_1_end):
                return True
        
        # Check window 2
        if self.blackout_window_2_start is not None and self.blackout_window_2_end is not None:
            if self._is_hour_in_range(current_hour, self.blackout_window_2_start, self.blackout_window_2_end):
                return True
        
        return False
    
    @staticmethod
    def _is_hour_in_range(hour: int, start: int, end: int) -> bool:
        """Check if hour is in range, handling overnight periods."""
        if start <= end:
            return start <= hour < end
        else:  # Overnight (e.g., 22-6)
            return hour >= start or hour < end


class AccountWarmupService:
    """Advanced service for warming up Telegram accounts with AI-powered intelligence."""

    def __init__(self, account_manager: AccountManager, gemini_service: Optional[GeminiService] = None):
        self.account_manager = account_manager
        self.gemini_service = gemini_service
        # Store reference for status updates

        # Queue management
        self.job_queue: List[WarmupJob] = []
        self.active_jobs: Dict[str, WarmupJob] = {}
        self.completed_jobs: List[WarmupJob] = []
        self.failed_jobs: List[WarmupJob] = []

        # Status tracking
        self.status_callbacks: List[Callable] = []
        self.is_running = False
        self._shutdown_event: asyncio.Event = asyncio.Event()

        # Configuration
        self.config = WarmupConfig()

        # Persistence
        self.jobs_file = Path("warmup_jobs.json")
        self.load_jobs()

        # Activity tracking persistence
        self.activity_file = Path("warmup_activity.json")
        self.daily_activity_log: Dict[str, List[datetime]] = {}
        self._load_activity_log()

        # Initialize warmup intelligence
        self.warmup_intelligence = WarmupIntelligence(gemini_service)

    def add_status_callback(self, callback: Callable):
        """Add a callback for status updates."""
        self.status_callbacks.append(callback)

    def _notify_status_update(self, job: WarmupJob, message: str = None):
        """Notify all status callbacks of an update."""
        if message:
            job.status_message = message

        for callback in self.status_callbacks:
            try:
                callback(job)
            except Exception as e:
                logger.warning(f"Status callback failed: {e}")
        
        # Also update account manager if available
        if hasattr(self, 'account_manager') and self.account_manager:
            try:
                from account_manager import AccountStatus
                # Update account status based on warmup stage
                if job.stage == WarmupStage.COMPLETED:
                    self.account_manager.update_account_status(
                        job.phone_number,
                        AccountStatus.READY,
                        {
                            'warmup_job_id': job.job_id,
                            'warmup_stage': job.stage.value,
                            'warmup_progress': 100.0
                        }
                    )
                elif job.stage == WarmupStage.FAILED:
                    self.account_manager.update_account_status(
                        job.phone_number,
                        AccountStatus.ERROR,
                        {
                            'error_message': job.error_message or "Warmup failed",
                            'warmup_job_id': job.job_id,
                            'warmup_stage': job.stage.value
                        }
                    )
                else:
                    # Update warmup progress
                    if job.phone_number in self.account_manager.account_status:
                        self.account_manager.account_status[job.phone_number]['warmup_stage'] = job.stage.value
                        self.account_manager.account_status[job.phone_number]['warmup_progress'] = job.progress
                        # Ensure status is WARMING_UP if not already in a later stage
                        current_status = self.account_manager.account_status[job.phone_number].get('status')
                        if current_status not in [AccountStatus.CLONING.value, AccountStatus.READY.value]:
                            self.account_manager.update_account_status(
                                job.phone_number,
                                AccountStatus.WARMING_UP,
                                {
                                    'warmup_job_id': job.job_id,
                                    'warmup_stage': job.stage.value,
                                    'warmup_progress': job.progress
                                }
                            )
            except Exception as e:
                logger.warning(f"Failed to update account manager with warmup status: {e}")

    async def start_warmup_service(self):
        """Start the warmup service."""
        if self.is_running:
            logger.warning("Warmup service is already running")
            return

        self.is_running = True
        self._shutdown_event.clear()
        logger.info("🚀 Starting Account Warmup Service")

        # Track tasks for proper cleanup
        if not hasattr(self, '_background_tasks'):
            self._background_tasks = []

        # Start the main processing loop
        task1 = asyncio.create_task(self._process_job_queue())
        self._background_tasks.append(task1)

        # Start the status monitoring loop
        task2 = asyncio.create_task(self._monitor_job_status())
        self._monitor_task = task2
        self._background_tasks.append(task2)

    async def stop_warmup_service(self):
        """Stop the warmup service."""
        self.is_running = False
        self._shutdown_event.set()
        logger.info("🛑 Stopping Account Warmup Service")
        
        # Cancel all background tasks
        if hasattr(self, '_background_tasks'):
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self._background_tasks.clear()
        if hasattr(self, '_monitor_task'):
            self._monitor_task = None

    def add_warmup_job(self, phone_number: str, priority: WarmupPriority = WarmupPriority.NORMAL) -> str:
        """Add a new warmup job to the queue."""
        job_id = f"warmup_{phone_number}_{int(time.time())}_{random.randint(1000, 9999)}"

        job = WarmupJob(
            job_id=job_id,
            phone_number=phone_number,
            stage=WarmupStage.CREATED,
            priority=priority,
            created_at=datetime.now(),
            status_message="Job queued for warmup"
        )

        self.job_queue.append(job)
        self.save_jobs()

        # Sort queue by priority
        self._sort_job_queue()

        logger.info(f"📋 Added warmup job {job_id} for {phone_number}")
        self._notify_status_update(job, f"Queued for {priority.value} priority warmup")

        return job_id

    def _sort_job_queue(self):
        """Sort job queue by priority."""
        priority_order = {
            WarmupPriority.CRITICAL: 0,
            WarmupPriority.HIGH: 1,
            WarmupPriority.NORMAL: 2,
            WarmupPriority.LOW: 3
        }

        self.job_queue.sort(key=lambda j: (priority_order[j.priority], j.created_at))

    async def _sleep_with_cancellation(self, total_seconds: float) -> bool:
        """Sleep in small intervals while honoring shutdown requests.

        Returns False if the service was stopped before the delay elapsed.
        """
        if total_seconds <= 0:
            return self.is_running and not self._shutdown_event.is_set()

        loop = asyncio.get_event_loop()
        end_time = loop.time() + total_seconds

        while self.is_running and not self._shutdown_event.is_set():
            remaining = end_time - loop.time()
            if remaining <= 0:
                return True

            wait_time = min(remaining, 60)
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=wait_time)
                return False
            except asyncio.TimeoutError:
                continue

        return False

    async def _process_job_queue(self):
        """Main job processing loop."""
        while self.is_running:
            try:
                # Get next job
                job = self._get_next_job()
                if not job:
                    if not await self._sleep_with_cancellation(30):
                        break
                    continue

                # Start processing job
                job.started_at = datetime.now()
                job.last_activity = datetime.now()
                self.active_jobs[job.job_id] = job
                self._record_activity(job.phone_number, f"stage_start:{job.stage.value}")

                logger.info(f"🔄 Starting warmup job {job.job_id} for {job.phone_number} (Stage: {job.stage.value})")
                self._notify_status_update(job, f"Starting {job.stage.value} stage")

                # Process the job
                success = await self._process_warmup_job(job)

                if success:
                    # Move to next stage or complete
                    if job.stage != WarmupStage.STABILIZATION:
                        next_stage = self._get_next_stage(job.stage)
                        if next_stage:
                            job.stage = next_stage
                            job.progress = 0.0
                            job.next_attempt_at = None
                            job.status_message = f"Completed {job.stage.value}, moving to {next_stage.value}"
                            self._record_activity(job.phone_number, f"stage_complete:{next_stage.value}")
                            # Re-queue for next stage
                            self.job_queue.append(job)
                        else:
                            job.stage = WarmupStage.COMPLETED
                            job.completed_at = datetime.now()
                            job.progress = 100.0
                            job.next_attempt_at = None
                            job.status_message = "Warmup completed successfully"
                            self.completed_jobs.append(job)
                    else:
                        job.stage = WarmupStage.COMPLETED
                        job.completed_at = datetime.now()
                        job.progress = 100.0
                        job.next_attempt_at = None
                        job.status_message = "Warmup completed successfully"
                        self.completed_jobs.append(job)
                else:
                    # Handle failure
                    job.retry_count += 1
                    if job.retry_count >= job.max_retries:
                        job.stage = WarmupStage.FAILED
                        job.completed_at = datetime.now()
                        job.status_message = f"Job failed after {job.max_retries} retries"
                        self.failed_jobs.append(job)
                        logger.error(f"❌ Job {job.job_id} failed permanently")
                    else:
                        # Re-queue with backoff
                        delay_hours = 2 ** job.retry_count  # Exponential backoff
                        job.status_message = f"Job failed, retrying in {delay_hours} hours"
                        job.next_attempt_at = datetime.now() + timedelta(hours=delay_hours)
                        self.job_queue.append(job)
                        self.save_jobs()
                        should_resume = await self._sleep_with_cancellation(delay_hours * 3600)
                        if not should_resume:
                            logger.info("Warmup service stopping during backoff; preserving queued retry state")

                # Remove from active jobs
                if job.job_id in self.active_jobs:
                    del self.active_jobs[job.job_id]

                # Save state
                self.save_jobs()

            except Exception as e:
                logger.error(f"Error processing warmup job: {e}")
                if not await self._sleep_with_cancellation(60):
                    break

    def _get_next_job(self) -> Optional[WarmupJob]:
        """Get the next job to process."""
        if not self.job_queue:
            return None

        # Check if job is ready (respecting stage delays)
        for job in self.job_queue:
            if self._is_job_ready(job):
                self.job_queue.remove(job)
                return job

        return None

    def _is_job_ready(self, job: WarmupJob) -> bool:
        """Check if a job is ready to be processed."""
        if job.next_attempt_at and datetime.now() < job.next_attempt_at:
            return False

        if job.stage == WarmupStage.CREATED:
            # Check initial delay
            hours_since_creation = (datetime.now() - job.created_at).total_seconds() / 3600
            return hours_since_creation >= self.config.initial_delay_hours

        # Check stage-specific delays
        stage_delay = self.config.stage_delays.get(job.stage.value, 24)
        if job.completed_at:
            hours_since_completion = (datetime.now() - job.completed_at).total_seconds() / 3600
            return hours_since_completion >= stage_delay

        return True

    def _get_next_stage(self, current_stage: WarmupStage) -> Optional[WarmupStage]:
        """Get the next warmup stage."""
        stage_progression = [
            WarmupStage.CREATED,
            WarmupStage.INITIAL_SETUP,
            WarmupStage.PROFILE_COMPLETION,
            WarmupStage.CONTACT_BUILDING,
            WarmupStage.GROUP_JOINING,
            WarmupStage.CONVERSATION_STARTERS,
            WarmupStage.ACTIVITY_INCREASE,
            WarmupStage.ADVANCED_INTERACTIONS,
            WarmupStage.STABILIZATION
        ]

        try:
            current_index = stage_progression.index(current_stage)
            if current_index + 1 < len(stage_progression):
                return stage_progression[current_index + 1]
        except ValueError:
            logger.error(f"Unexpected warmup stage stored for progression: {current_stage}")

        return None

    async def _process_warmup_job(self, job: WarmupJob) -> bool:
        """Process a single warmup job."""
        try:
            if not self._validate_job(job):
                return False
            
            # Check blackout window
            if self.config.is_in_blackout_window():
                logger.info(f"⏸ Job {job.job_id} delayed - in blackout window")
                job.status_message = "Waiting for blackout window to pass"
                # Re-queue for later
                job.next_attempt_at = datetime.now() + timedelta(hours=1)
                self.job_queue.append(job)
                self.save_jobs()
                return True  # Not a failure, just delayed
            
            # Get account client
            client = await self._get_account_client(job.phone_number)
            if not client:
                job.error_message = "Could not initialize account client"
                return False

            # Process based on stage
            if job.stage == WarmupStage.INITIAL_SETUP:
                success = await self._perform_initial_setup(job, client)
            elif job.stage == WarmupStage.PROFILE_COMPLETION:
                success = await self._perform_profile_completion(job, client)
            elif job.stage == WarmupStage.CONTACT_BUILDING:
                success = await self._perform_contact_building(job, client)
            elif job.stage == WarmupStage.GROUP_JOINING:
                success = await self._perform_group_joining(job, client)
            elif job.stage == WarmupStage.CONVERSATION_STARTERS:
                success = await self._perform_conversation_starters(job, client)
            elif job.stage == WarmupStage.ACTIVITY_INCREASE:
                success = await self._perform_activity_increase(job, client)
            elif job.stage == WarmupStage.ADVANCED_INTERACTIONS:
                success = await self._perform_advanced_interactions(job, client)
            elif job.stage == WarmupStage.STABILIZATION:
                success = await self._perform_stabilization(job, client)
            else:
                logger.warning(f"Unknown warmup stage: {job.stage}")
                return False

            return success

        except Exception as e:
            logger.error(f"Error processing warmup job {job.job_id}: {e}")
            job.error_message = str(e)
            return False
        finally:
            # Clean up client
            if 'client' in locals():
                try:
                    await client.stop()
                except (AttributeError, RuntimeError, ConnectionError, Exception) as e:
                    logger.warning(f"Error stopping client during cleanup: {e}")

    def _validate_job(self, job: WarmupJob) -> bool:
        """Ensure the job has a valid stage and required identifiers."""
        if not isinstance(job.stage, WarmupStage):
            logger.error(f"Warmup job {job.job_id} has invalid stage: {job.stage}")
            job.error_message = "Invalid warmup stage"
            job.stage = WarmupStage.FAILED
            self.failed_jobs.append(job)
            return False

        if not job.phone_number:
            logger.error(f"Warmup job {job.job_id} missing phone number")
            job.error_message = "Missing phone number"
            job.stage = WarmupStage.FAILED
            self.failed_jobs.append(job)
            return False

        return True

    async def _get_account_client(self, phone_number: str) -> Optional[TelegramClient]:
        """Get a Telegram client for the account."""
        try:
            account_data = self.account_manager.accounts.get(phone_number)
            if not account_data:
                logger.error(f"Account data not found for {phone_number}")
                return None

            api_id = account_data.get('api_id')
            api_hash = account_data.get('api_hash')
            
            if not api_id or not api_hash:
                logger.error(f"Missing API credentials for warmup account {phone_number} in account manager.")
                return None
            
            client = TelegramClient(
                api_id=api_id,
                api_hash=api_hash,
                phone_number=phone_number
            )

            success = await client.initialize()
            if success:
                return client
            else:
                logger.error(f"Failed to initialize client for {phone_number}")
                return None

        except Exception as e:
            logger.error(f"Error getting client for {phone_number}: {e}")
            return None

    # ... (rest of methods remain the same) ...

    async def _perform_initial_setup(self, job: WarmupJob, client: TelegramClient) -> bool:
        """Perform initial account setup."""
        try:
            # Basic online/offline simulation
            await self._simulate_online_presence(client, duration_minutes=5)
            job.progress = 25
            self._save_job_progress(job)

            # Set basic privacy settings
            await self._configure_privacy_settings(client)
            job.progress = 50
            self._save_job_progress(job)

            # Basic profile validation
            await self._validate_profile_setup(client)
            job.progress = 75
            self._save_job_progress(job)

            # Set initial online status
            await client.update_status(online=False)
            job.progress = 100
            self._save_job_progress(job)

            logger.info(f"✅ Initial setup completed for {job.phone_number}")
            return True

        except Exception as e:
            logger.error(f"Initial setup failed for {job.phone_number}: {e}")
            return False

    async def _perform_profile_completion(self, job: WarmupJob, client: TelegramClient) -> bool:
        """Complete account profile setup with AI intelligence."""
        try:
            # Use Gemini to generate intelligent profile content based on account analysis
            account_analysis = await self.warmup_intelligence.analyze_account_for_profile(job.phone_number)
            profile_data = await self.warmup_intelligence.generate_profile_content(job.phone_number, account_analysis)

            # Update profile with AI-generated content
            await self._update_profile_with_content(client, profile_data)
            job.progress = 40

            # Set profile photo with AI selection
            photo_suggestion = await self.warmup_intelligence.suggest_profile_photo(job.phone_number, profile_data)
            if photo_suggestion:
                await self._set_profile_photo_with_ai(client, photo_suggestion)
            job.progress = 70

            # Generate and set bio with AI
            bio_suggestion = await self.warmup_intelligence.generate_bio_for_account(job.phone_number, profile_data)
            if bio_suggestion:
                await client.update_profile(bio=bio_suggestion)
            job.progress = 85

            # Configure additional profile settings with AI recommendations
            await self._configure_profile_settings_with_ai(client, profile_data)
            job.progress = 100

            logger.info(f"✅ AI-powered profile completion finished for {job.phone_number}")
            return True

        except Exception as e:
            logger.error(f"Profile completion failed for {job.phone_number}: {e}")
            return False

    async def _perform_contact_building(self, job: WarmupJob, client: TelegramClient) -> bool:
        """Build contacts gradually."""
        try:
            # Apply stage weight to activity count
            base_contacts = self.config.contacts_per_day
            stage_weight = self.config.stage_weights.get('contact_building', 1.0)
            contacts_to_add = min(int(base_contacts * stage_weight), 10)

            for i in range(contacts_to_add):
                # Use Gemini to find suitable contacts to add
                contact_suggestion = await self.warmup_intelligence.suggest_contact_to_add(job.phone_number)

                if contact_suggestion:
                    await self._add_contact_safely(client, contact_suggestion)
                    job.progress = (i + 1) / contacts_to_add * 100

                # Respect rate limits
                await self._respect_rate_limits()

            logger.info(f"✅ Added {contacts_to_add} contacts for {job.phone_number}")
            return True

        except Exception as e:
            logger.error(f"Contact building failed for {job.phone_number}: {e}")
            return False

    async def _perform_group_joining(self, job: WarmupJob, client: TelegramClient) -> bool:
        """Join groups and channels."""
        try:
            # Apply stage weight to activity count
            base_groups = self.config.groups_per_day
            stage_weight = self.config.stage_weights.get('group_joining', 1.0)
            groups_to_join = min(int(base_groups * stage_weight), 5)

            for i in range(groups_to_join):
                # Use Gemini to find suitable groups
                group_suggestion = await self.warmup_intelligence.suggest_group_to_join(job.phone_number)

                if group_suggestion:
                    await self._join_group_safely(client, group_suggestion)
                    job.progress = (i + 1) / groups_to_join * 100

                # Respect rate limits
                await self._respect_rate_limits()

            logger.info(f"✅ Joined {groups_to_join} groups for {job.phone_number}")
            return True

        except Exception as e:
            logger.error(f"Group joining failed for {job.phone_number}: {e}")
            return False

    async def _perform_conversation_starters(self, job: WarmupJob, client: TelegramClient) -> bool:
        """Start natural conversations."""
        try:
            # Apply stage weight to activity count
            base_messages = self.config.messages_per_day
            stage_weight = self.config.stage_weights.get('conversation_starters', 1.0)
            conversations_to_start = min(int(base_messages * stage_weight), 15)

            for i in range(conversations_to_start):
                # Use Gemini to generate natural conversation starters
                conversation_data = await self.warmup_intelligence.generate_conversation_starter(job.phone_number)

                if conversation_data:
                    await self._send_conversation_starter(client, conversation_data)
                    job.progress = (i + 1) / conversations_to_start * 100

                # Respect rate limits
                await self._respect_rate_limits()

            logger.info(f"✅ Started {conversations_to_start} conversations for {job.phone_number}")
            return True

        except Exception as e:
            logger.error(f"Conversation starters failed for {job.phone_number}: {e}")
            return False

    async def _perform_activity_increase(self, job: WarmupJob, client: TelegramClient) -> bool:
        """Gradually increase account activity."""
        try:
            # Increase daily limits
            activities = [
                self._perform_random_interactions,
                self._update_online_status,
                self._send_followup_messages,
                self._engage_with_groups
            ]

            completed_activities = 0
            total_activities = len(activities)

            for activity_func in activities:
                try:
                    await activity_func(client, job.phone_number)
                    completed_activities += 1
                    job.progress = completed_activities / total_activities * 100
                except Exception as e:
                    logger.warning(f"Activity failed: {e}")

                await self._respect_rate_limits()

            logger.info(f"✅ Increased activity for {job.phone_number}")
            return True

        except Exception as e:
            logger.error(f"Activity increase failed for {job.phone_number}: {e}")
            return False

    async def _perform_advanced_interactions(self, job: WarmupJob, client: TelegramClient) -> bool:
        """Perform advanced interactions to make account look established."""
        try:
            # Advanced activities: polls, media sharing, etc.
            advanced_activities = [
                self._create_and_share_content,
                self._participate_in_polls,
                self._share_media_content,
                self._engage_in_group_discussions
            ]

            completed = 0
            for activity in advanced_activities:
                try:
                    await activity(client, job.phone_number)
                    completed += 1
                    job.progress = completed / len(advanced_activities) * 100
                except Exception as e:
                    logger.warning(f"Advanced activity failed: {e}")

                await self._respect_rate_limits()

            logger.info(f"✅ Advanced interactions completed for {job.phone_number}")
            return True

        except Exception as e:
            logger.error(f"Advanced interactions failed for {job.phone_number}: {e}")
            return False

    async def _perform_stabilization(self, job: WarmupJob, client: TelegramClient) -> bool:
        """Stabilize account with consistent, natural behavior."""
        try:
            # Maintain consistent activity patterns
            stabilization_activities = [
                self._maintain_online_presence,
                self._respond_to_messages_consistently,
                self._keep_groups_active,
                self._update_profile_periodically
            ]

            completed = 0
            for activity in stabilization_activities:
                try:
                    await activity(client, job.phone_number)
                    completed += 1
                    job.progress = completed / len(stabilization_activities) * 100
                except Exception as e:
                    logger.warning(f"Stabilization activity failed: {e}")

                await self._respect_rate_limits()

            logger.info(f"✅ Account stabilization completed for {job.phone_number}")
            return True

        except Exception as e:
            logger.error(f"Stabilization failed for {job.phone_number}: {e}")
            return False

    # Helper methods for various activities
    async def _simulate_online_presence(self, client: TelegramClient, duration_minutes: int):
        """Simulate realistic online presence."""
        await client.update_status(online=True)
        await asyncio.sleep(duration_minutes * 60)
        await client.update_status(online=False)

    async def _configure_privacy_settings(self, client: TelegramClient):
        """Configure basic privacy settings."""
        try:
            if not client or not client.client:
                logger.warning("Client not available for privacy settings")
                return
            
            from pyrogram import raw
            
            # Set basic privacy: allow everyone to see last seen, phone number, etc.
            # This is a conservative default for new accounts
            try:
                # Set last seen privacy to "Everybody"
                await client.client.invoke(
                    raw.functions.account.SetPrivacy(
                        key=raw.types.InputPrivacyKeyStatusTimestamp(),
                        rules=[raw.types.InputPrivacyValueAllowAll()]
                    )
                )
                logger.debug("Privacy settings configured")
            except Exception as e:
                logger.warning(f"Could not configure privacy settings: {e}")
        except Exception as e:
            logger.error(f"Failed to configure privacy settings: {e}")

    async def _validate_profile_setup(self, client: TelegramClient):
        """Validate that profile is properly set up."""
        try:
            if not client or not client.client:
                logger.warning("Client not available for profile validation")
                return False
            
            # Get current user info
            me = await client.client.get_me()
            
            # Check if profile has basic info
            has_name = bool(me.first_name)
            has_username = bool(me.username)
            
            if not has_name:
                logger.warning("Profile missing first name")
                return False
            
            logger.debug(f"Profile validation: name={has_name}, username={has_username}")
            return True
        except Exception as e:
            logger.error(f"Failed to validate profile: {e}")
            return False

    async def _update_profile_with_content(self, client: TelegramClient, profile_data: Dict):
        """Update profile with AI-generated content (sanitized)."""
        from utils.input_validation import sanitize_html
        
        if profile_data.get('bio'):
            bio = sanitize_html(profile_data['bio'])[:70]  # Sanitize and limit
            await client.update_profile(bio=bio)
        if profile_data.get('first_name') or profile_data.get('last_name'):
            first_name = sanitize_html(profile_data.get('first_name', ''))[:64] if profile_data.get('first_name') else None
            last_name = sanitize_html(profile_data.get('last_name', ''))[:64] if profile_data.get('last_name') else None
            await client.update_profile(
                first_name=first_name,
                last_name=last_name
            )

    async def _set_profile_photo(self, client: TelegramClient, profile_data: Dict):
        """Set profile photo."""
        try:
            if not client or not client.client:
                logger.warning("Client not available for setting profile photo")
                return False
            
            photo_path = profile_data.get('photo_path')
            if not photo_path:
                logger.debug("No photo path provided")
                return False
            
            from pathlib import Path
            photo_file = Path(photo_path)
            if not photo_file.exists():
                logger.warning(f"Photo file not found: {photo_path}")
                return False
            
            await client.client.set_profile_photo(photo=str(photo_file))
            logger.info("Profile photo set successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to set profile photo: {e}")
            return False

    async def _set_profile_photo_with_ai(self, client: TelegramClient, photo_suggestion: Dict):
        """Set profile photo with AI guidance."""
        try:
            if not client or not client.client:
                logger.warning("Client not available for AI profile photo")
                return False
            
            # If AI suggested a photo path, use it
            photo_path = photo_suggestion.get('photo_path')
            if photo_path:
                return await self._set_profile_photo(client, {'photo_path': photo_path})
            
            # Otherwise, AI might suggest generating or finding a photo
            # For now, just log that AI suggestion was received
            logger.debug(f"AI photo suggestion received: {photo_suggestion}")
            return False
        except Exception as e:
            logger.error(f"Failed to set AI-suggested profile photo: {e}")
            return False

    async def _configure_profile_settings_with_ai(self, client: TelegramClient, profile_data: Dict):
        """Configure profile settings with AI recommendations."""
        try:
            if not client or not client.client:
                logger.warning("Client not available for AI profile configuration")
                return False
            
            # Use AI-generated content if available
            updates = {}
            if profile_data.get('first_name'):
                updates['first_name'] = profile_data['first_name']
            if profile_data.get('last_name'):
                updates['last_name'] = profile_data['last_name']
            if profile_data.get('bio'):
                updates['bio'] = profile_data['bio'][:70]  # Max 70 chars
            
            if updates:
                await client.client.update_profile(**updates)
                logger.info("Profile updated with AI-generated content")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to configure profile with AI: {e}")
            return False

    async def _configure_profile_settings(self, client: TelegramClient):
        """Configure additional profile settings."""
        try:
            if not client or not client.client:
                logger.warning("Client not available for profile configuration")
                return False
            
            # Basic profile validation and setup
            me = await client.client.get_me()
            
            # Ensure username is set if possible
            if not me.username:
                # Try to set a username based on first name
                if me.first_name:
                    suggested_username = me.first_name.lower().replace(' ', '_') + str(random.randint(100, 999))
                    try:
                        await client.client.set_username(suggested_username)
                        logger.info(f"Set username: {suggested_username}")
                    except Exception as e:
                        logger.debug(f"Could not set username: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to configure profile settings: {e}")
            return False

    async def _add_contact_safely(self, client: TelegramClient, contact_data: Dict):
        """Add a contact safely."""
        try:
            if not client or not client.client:
                logger.warning("Client not available for adding contact")
                return False
            
            phone_number = contact_data.get('phone_number')
            first_name = contact_data.get('first_name', '')
            last_name = contact_data.get('last_name', '')
            
            if not phone_number:
                logger.warning("No phone number provided for contact")
                return False
            
            # Add delay before adding contact
            await self._respect_rate_limits()
            
            # Import contact method
            from pyrogram.types import InputPhoneContact
            from pyrogram import raw
            
            contact = InputPhoneContact(
                phone=phone_number,
                first_name=first_name,
                last_name=last_name
            )
            
            result = await client.client.invoke(
                raw.functions.contacts.ImportContacts(contacts=[contact.to_raw()])
            )
            
            if result.users:
                logger.info(f"Contact added: {phone_number}")
                return True
            else:
                logger.warning(f"Contact not found or already exists: {phone_number}")
                return False
        except Exception as e:
            logger.error(f"Failed to add contact: {e}")
            return False

    async def _join_group_safely(self, client: TelegramClient, group_data: Dict):
        """Join a group safely."""
        try:
            if not client or not client.client:
                logger.warning("Client not available for joining group")
                return False
            
            group_username = group_data.get('username')
            group_id = group_data.get('chat_id')
            
            if not group_username and not group_id:
                logger.warning("No group identifier provided")
                return False
            
            # Add delay before joining
            await self._respect_rate_limits()
            
            try:
                if group_username:
                    await client.client.join_chat(group_username)
                    logger.info(f"Joined group: {group_username}")
                elif group_id:
                    await client.client.join_chat(group_id)
                    logger.info(f"Joined group: {group_id}")
                return True
            except Exception as e:
                if "already a participant" in str(e).lower() or "already joined" in str(e).lower():
                    logger.debug(f"Already in group: {group_username or group_id}")
                    return True
                raise
        except Exception as e:
            logger.error(f"Failed to join group: {e}")
            return False

    async def _send_conversation_starter(self, client: TelegramClient, conversation_data: Dict):
        """Send a conversation starter message."""
        try:
            if not client or not client.client:
                logger.warning("Client not available for sending message")
                return False
            
            chat_id = conversation_data.get('chat_id')
            message = conversation_data.get('message')
            
            if not chat_id or not message:
                logger.warning("Missing chat_id or message for conversation starter")
                return False
            
            # Add delay before sending
            await self._respect_rate_limits()
            
            await client.client.send_message(chat_id, message)
            logger.info(f"Conversation starter sent to {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send conversation starter: {e}")
            return False

    async def _perform_random_interactions(self, client: TelegramClient, phone_number: str):
        """Perform random interactions."""
        try:
            if not client or not client.client:
                return False
            
            # Random interactions: view chats, check messages, etc.
            interactions = [
                self._view_recent_chats,
                self._check_dialogs,
            ]
            
            # Perform 1-3 random interactions
            num_interactions = random.randint(1, 3)
            selected = random.sample(interactions, min(num_interactions, len(interactions)))
            
            for interaction in selected:
                try:
                    await interaction(client)
                    await self._respect_rate_limits()
                except Exception as e:
                    logger.debug(f"Random interaction failed: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to perform random interactions: {e}")
            return False

    async def _view_recent_chats(self, client: TelegramClient):
        """View recent chats."""
        try:
            if client and client.client:
                async for dialog in client.client.get_dialogs(limit=10):
                    # Just accessing the dialog is enough to "view" it
                    pass
        except Exception as e:
            logger.debug(f"Failed to view recent chats: {e}")

    async def _check_dialogs(self, client: TelegramClient):
        """Check dialogs."""
        try:
            if client and client.client:
                dialogs = await client.client.get_dialogs(limit=20)
                logger.debug(f"Checked {len(dialogs)} dialogs")
        except Exception as e:
            logger.debug(f"Failed to check dialogs: {e}")

    async def _update_online_status(self, client: TelegramClient, phone_number: str):
        """Update online status."""
        try:
            if client:
                # Online status is managed automatically by Pyrogram
                # This is mainly for API compatibility
                await client.update_status(online=True)
                await asyncio.sleep(random.uniform(30, 120))  # Stay online for 30s-2min
                await client.update_status(online=False)
                return True
        except Exception as e:
            logger.debug(f"Failed to update online status: {e}")
            return False

    async def _send_followup_messages(self, client: TelegramClient, phone_number: str):
        """Send followup messages."""
        try:
            if not client or not client.client:
                return False
            
            # Get recent chats
            dialogs = []
            async for dialog in client.client.get_dialogs(limit=5):
                if dialog.chat.type.name in ['PRIVATE', 'GROUP', 'SUPERGROUP']:
                    dialogs.append(dialog)
            
            if not dialogs:
                logger.debug("No dialogs available for followup messages")
                return False
            
            # Send followup to 1-2 random chats
            selected_dialogs = random.sample(dialogs, min(2, len(dialogs)))
            
            for dialog in selected_dialogs:
                try:
                    # Generate a simple followup message
                    followup_messages = [
                        "Hey, how are you?",
                        "Just checking in!",
                        "Hope you're doing well!",
                    ]
                    message = random.choice(followup_messages)
                    
                    await client.client.send_message(dialog.chat.id, message)
                    await self._respect_rate_limits()
                    logger.debug(f"Sent followup to {dialog.chat.id}")
                except Exception as e:
                    logger.debug(f"Failed to send followup: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to send followup messages: {e}")
            return False

    async def _engage_with_groups(self, client: TelegramClient, phone_number: str):
        """Engage with groups."""
        try:
            if not client or not client.client:
                return False
            
            # Get group chats
            groups = []
            async for dialog in client.client.get_dialogs():
                if dialog.chat.type.name in ['GROUP', 'SUPERGROUP']:
                    groups.append(dialog.chat)
            
            if not groups:
                logger.debug("No groups available for engagement")
                return False
            
            # Engage with 1-2 random groups
            selected_groups = random.sample(groups, min(2, len(groups)))
            
            for group in selected_groups:
                try:
                    # Send a simple message to the group
                    messages = [
                        "Hello everyone!",
                        "Thanks for having me here!",
                        "Great group!",
                    ]
                    message = random.choice(messages)
                    
                    await client.client.send_message(group.id, message)
                    await self._respect_rate_limits()
                    logger.debug(f"Engaged with group {group.id}")
                except Exception as e:
                    logger.debug(f"Failed to engage with group: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to engage with groups: {e}")
            return False

    async def _create_and_share_content(self, client: TelegramClient, phone_number: str):
        """Create and share content."""
        try:
            if not client or not client.client:
                return False
            
            # Get a group or channel to share in
            groups = []
            async for dialog in client.client.get_dialogs(limit=10):
                if dialog.chat.type.name in ['GROUP', 'SUPERGROUP', 'CHANNEL']:
                    groups.append(dialog.chat)
            
            if not groups:
                logger.debug("No groups/channels available for sharing")
                return False
            
            # Share a simple text message
            content_messages = [
                "Sharing some thoughts...",
                "Interesting read!",
                "Check this out!",
            ]
            message = random.choice(content_messages)
            
            target = random.choice(groups)
            await client.client.send_message(target.id, message)
            await self._respect_rate_limits()
            
            logger.debug(f"Shared content in {target.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create and share content: {e}")
            return False

    async def _participate_in_polls(self, client: TelegramClient, phone_number: str):
        """Participate in polls."""
        try:
            if not client or not client.client:
                return False
            
            # Find messages with polls
            polls_found = 0
            async for dialog in client.client.get_dialogs(limit=20):
                try:
                    # Get recent messages from the chat
                    async for message in client.client.get_chat_history(dialog.chat.id, limit=10):
                        if message.poll:
                            # Vote on the poll (random option)
                            poll = message.poll
                            if poll.options:
                                # vote_poll takes option index (0-based), not option data
                                option_index = random.randint(0, len(poll.options) - 1)
                                try:
                                    await client.client.vote_poll(
                                        chat_id=dialog.chat.id,
                                        message_id=message.id,
                                        options=option_index
                                    )
                                    polls_found += 1
                                    await self._respect_rate_limits()
                                    logger.debug(f"Voted on poll in {dialog.chat.id}")
                                    if polls_found >= 2:  # Limit to 2 polls
                                        break
                                except Exception as e:
                                    logger.debug(f"Could not vote on poll: {e}")
                    if polls_found >= 2:
                        break
                except Exception as e:
                    logger.debug(f"Error checking chat for polls: {e}")
            
            return polls_found > 0
        except Exception as e:
            logger.error(f"Failed to participate in polls: {e}")
            return False

    async def _share_media_content(self, client: TelegramClient, phone_number: str):
        """Share media content."""
        try:
            if not client or not client.client:
                return False
            
            # For now, we'll just send text messages
            # Media sharing would require actual media files
            groups = []
            async for dialog in client.client.get_dialogs(limit=5):
                if dialog.chat.type.name in ['GROUP', 'SUPERGROUP']:
                    groups.append(dialog.chat)
            
            if not groups:
                return False
            
            target = random.choice(groups)
            # Send a message that could reference media
            await client.client.send_message(target.id, "Great content!")
            await self._respect_rate_limits()
            
            logger.debug("Shared content (text-based)")
            return True
        except Exception as e:
            logger.error(f"Failed to share media content: {e}")
            return False

    async def _engage_in_group_discussions(self, client: TelegramClient, phone_number: str):
        """Engage in group discussions."""
        try:
            if not client or not client.client:
                return False
            
            # Get group chats
            groups = []
            async for dialog in client.client.get_dialogs(limit=10):
                if dialog.chat.type.name in ['GROUP', 'SUPERGROUP']:
                    groups.append(dialog.chat)
            
            if not groups:
                return False
            
            # Engage in 1-2 group discussions
            selected_groups = random.sample(groups, min(2, len(groups)))
            
            discussion_messages = [
                "Interesting point!",
                "I agree with that.",
                "Thanks for sharing!",
                "That makes sense.",
            ]
            
            for group in selected_groups:
                try:
                    # Get recent messages to reply to
                    async for message in client.client.get_chat_history(group.id, limit=5):
                        if message.text and len(message.text) > 10:  # Only reply to substantial messages
                            reply = random.choice(discussion_messages)
                            await client.client.send_message(group.id, reply, reply_to_message_id=message.id)
                            await self._respect_rate_limits()
                            logger.debug(f"Engaged in discussion in {group.id}")
                            break
                except Exception as e:
                    logger.debug(f"Failed to engage in group discussion: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to engage in group discussions: {e}")
            return False

    async def _maintain_online_presence(self, client: TelegramClient, phone_number: str):
        """Maintain online presence."""
        try:
            if client:
                # Simulate being online for a period
                await client.update_status(online=True)
                # Stay "online" for 5-15 minutes
                duration = random.uniform(5, 15) * 60
                await asyncio.sleep(duration)
                await client.update_status(online=False)
                return True
        except Exception as e:
            logger.debug(f"Failed to maintain online presence: {e}")
            return False

    async def _respond_to_messages_consistently(self, client: TelegramClient, phone_number: str):
        """Respond to messages consistently."""
        try:
            if not client or not client.client:
                return False
            
            # Check for unread messages and respond
            dialogs = []
            async for dialog in client.client.get_dialogs(limit=20):
                if dialog.unread_count > 0:
                    dialogs.append(dialog)
            
            if not dialogs:
                logger.debug("No unread messages to respond to")
                return False
            
            # Respond to 1-3 dialogs
            selected_dialogs = random.sample(dialogs, min(3, len(dialogs)))
            
            response_messages = [
                "Thanks for your message!",
                "I'll get back to you soon.",
                "Appreciate you reaching out!",
            ]
            
            for dialog in selected_dialogs:
                try:
                    # Get the latest message
                    async for message in client.client.get_chat_history(dialog.chat.id, limit=1):
                        if message.from_user and message.from_user.id != (await client.client.get_me()).id:
                            response = random.choice(response_messages)
                            await client.client.send_message(dialog.chat.id, response)
                            await self._respect_rate_limits()
                            logger.debug(f"Responded to message in {dialog.chat.id}")
                            break
                except Exception as e:
                    logger.debug(f"Failed to respond to message: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to respond to messages consistently: {e}")
            return False

    async def _keep_groups_active(self, client: TelegramClient, phone_number: str):
        """Keep groups active."""
        try:
            if not client or not client.client:
                return False
            
            # Get active groups
            groups = []
            async for dialog in client.client.get_dialogs(limit=15):
                if dialog.chat.type.name in ['GROUP', 'SUPERGROUP']:
                    groups.append(dialog.chat)
            
            if not groups:
                return False
            
            # Send a message to 1-2 random groups to keep them active
            selected_groups = random.sample(groups, min(2, len(groups)))
            
            activity_messages = [
                "Hello!",
                "Hope everyone is doing well!",
                "Great to be here!",
            ]
            
            for group in selected_groups:
                try:
                    message = random.choice(activity_messages)
                    await client.client.send_message(group.id, message)
                    await self._respect_rate_limits()
                    logger.debug(f"Kept group active: {group.id}")
                except Exception as e:
                    logger.debug(f"Failed to keep group active: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to keep groups active: {e}")
            return False

    async def _update_profile_periodically(self, client: TelegramClient, phone_number: str):
        """Update profile periodically."""
        try:
            if not client or not client.client:
                return False
            
            # Small random profile updates (like bio tweaks)
            me = await client.client.get_me()
            current_bio = me.bio or ""
            
            # Only update if bio is short or empty
            if len(current_bio) < 50:
                # Generate a simple bio update
                bio_options = [
                    "Living life to the fullest!",
                    "Always learning, always growing.",
                    "Making the most of every day.",
                ]
                new_bio = random.choice(bio_options)
                
                try:
                    await client.client.update_profile(bio=new_bio)
                    logger.debug("Updated profile bio")
                    return True
                except Exception as e:
                    logger.debug(f"Could not update bio: {e}")
            
            return False
        except Exception as e:
            logger.error(f"Failed to update profile periodically: {e}")
            return False

    async def _respect_rate_limits(self):
        """Respect rate limits between actions."""
        delay = random.uniform(self.config.min_delay_between_actions, self.config.max_delay_between_actions)
        await asyncio.sleep(delay)

    async def _monitor_job_status(self):
        """Monitor and update job statuses."""
        while self.is_running:
            try:
                # Update status for active jobs
                for job in list(self.active_jobs.values()):
                    if job.last_activity:
                        # Check if job has been inactive too long
                        inactive_time = (datetime.now() - job.last_activity).total_seconds()
                        if inactive_time > 300:  # 5 minutes
                            job.status_message = f"Job inactive for {inactive_time:.0f} seconds"

                if not await self._sleep_with_cancellation(60):
                    break

            except Exception as e:
                logger.error(f"Error monitoring job status: {e}")
                await asyncio.sleep(60)

        logger.info("Warmup status monitor stopped")

    def get_job_status(self, job_id: str) -> Optional[WarmupJob]:
        """Get status of a specific job."""
        # Check active jobs
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]

        # Check completed jobs
        for job in self.completed_jobs:
            if job.job_id == job_id:
                return job

        # Check failed jobs
        for job in self.failed_jobs:
            if job.job_id == job_id:
                return job

        # Check queued jobs
        for job in self.job_queue:
            if job.job_id == job_id:
                return job

        return None

    def get_all_jobs(self) -> List[WarmupJob]:
        """Get all jobs."""
        return self.job_queue + list(self.active_jobs.values()) + self.completed_jobs + self.failed_jobs

    def save_jobs(self):
        """Save jobs to file."""
        try:
            data = {
                'queued_jobs': [job.to_dict() for job in self.job_queue],
                'active_jobs': [job.to_dict() for job in self.active_jobs.values()],
                'completed_jobs': [job.to_dict() for job in self.completed_jobs],
                'failed_jobs': [job.to_dict() for job in self.failed_jobs],
                'last_updated': datetime.now().isoformat()
            }

            # Atomic write pattern
            temp_file = self.jobs_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            temp_file.replace(self.jobs_file)

        except Exception as e:
            logger.error(f"Failed to save warmup jobs: {e}")

    def _record_activity(self, phone_number: str, action: str):
        """Record a warmup action for daily pacing and persist it."""
        try:
            today = datetime.now().date().isoformat()
            key = f"{phone_number}:{today}"
            self.daily_activity_log.setdefault(key, [])
            self.daily_activity_log[key].append(datetime.now())
            self._persist_activity_log()
        except Exception as exc:
            logger.debug(f"Failed to record warmup activity for {phone_number}: {exc}")

    def _persist_activity_log(self):
        """Persist daily activity log with ISO timestamps."""
        try:
            retention_cutoff = datetime.now() - timedelta(days=120)
            for key, entries in list(self.daily_activity_log.items()):
                pruned = [ts for ts in entries if ts >= retention_cutoff]
                if pruned:
                    self.daily_activity_log[key] = pruned
                else:
                    self.daily_activity_log.pop(key, None)

            serializable = {
                key: [ts.isoformat() for ts in entries]
                for key, entries in self.daily_activity_log.items()
            }
            temp_file = self.activity_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(serializable, f, indent=2)
            temp_file.replace(self.activity_file)
        except Exception as exc:
            logger.warning(f"Failed to persist warmup activity log: {exc}")

    def _save_job_progress(self, job: WarmupJob):
        """Save individual job progress immediately to prevent data loss.

        Args:
            job: The warmup job to save progress for
        """
        try:
            # Only save if this job is currently active
            if job.job_id in self.active_jobs:
                # Update the job in active_jobs
                self.active_jobs[job.job_id] = job

                # Save only the active jobs to avoid full file rewrite for performance
                active_jobs_data = {
                    'active_jobs': [j.to_dict() for j in self.active_jobs.values()],
                    'last_updated': datetime.now().isoformat()
                }

                temp_file = self.jobs_file.with_suffix('.progress.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(active_jobs_data, f, indent=2, default=str)

                temp_file.replace(self.jobs_file.with_suffix('.progress'))

                logger.debug(f"Saved progress for job {job.job_id}: {job.progress}%")

        except Exception as e:
            logger.error(f"Failed to save job progress for {job.job_id}: {e}")
            # Don't let progress saving failures stop the warmup process

    def load_jobs(self):
        """Load jobs from file."""
        if not self.jobs_file.exists():
            return

        try:
            with open(self.jobs_file, 'r') as f:
                data = json.load(f)

            # Load queued jobs
            self.job_queue = [WarmupJob.from_dict(job_data) for job_data in data.get('queued_jobs', [])]

            # Load active jobs
            for job_data in data.get('active_jobs', []):
                job = WarmupJob.from_dict(job_data)
                self.active_jobs[job.job_id] = job

            # Load completed jobs
            self.completed_jobs = [WarmupJob.from_dict(job_data) for job_data in data.get('completed_jobs', [])]

            # Load failed jobs
            self.failed_jobs = [WarmupJob.from_dict(job_data) for job_data in data.get('failed_jobs', [])]

            logger.info(f"Loaded {len(self.job_queue)} queued, {len(self.active_jobs)} active, "
                       f"{len(self.completed_jobs)} completed, {len(self.failed_jobs)} failed warmup jobs")

        except Exception as e:
            logger.error(f"Failed to load warmup jobs: {e}")

    def _load_activity_log(self):
        """Load persisted activity log into memory."""
        if not self.activity_file.exists():
            return

        try:
            with open(self.activity_file, 'r') as f:
                data = json.load(f)

            for key, entries in data.items():
                restored = []
                for ts in entries:
                    try:
                        restored.append(datetime.fromisoformat(ts))
                    except Exception:
                        continue
                if restored:
                    self.daily_activity_log[key] = restored
        except Exception as exc:
            logger.warning(f"Failed to load warmup activity log: {exc}")


class WarmupIntelligence:
    """AI-powered intelligence for warmup activities."""

    def __init__(self, gemini_service=None):
        self.gemini_service = gemini_service if GEMINI_AVAILABLE else None
        self._prompt_cache: Dict[str, Tuple[float, str]] = {}
        self._prompt_ttl_seconds = 6 * 3600  # reuse prompts for six hours per stage

    def _get_cached_reply(self, key: str) -> Optional[str]:
        """Return cached Gemini reply if still valid."""
        if key in self._prompt_cache:
            ts, value = self._prompt_cache[key]
            if time.time() - ts < self._prompt_ttl_seconds:
                return value
        return None

    def _set_cached_reply(self, key: str, value: str):
        self._prompt_cache[key] = (time.time(), value)

    async def analyze_account_for_profile(self, phone_number: str) -> Dict[str, Any]:
        """Analyze account characteristics to inform profile generation."""
        if not self.gemini_service:
            return {'account_type': 'general', 'interests': ['technology', 'general']}

        prompt = f"""
        Based on the phone number {phone_number}, analyze what type of account this might be and suggest profile characteristics:

        Consider:
        - Geographic region (from phone number patterns)
        - Likely demographics
        - Common interests for that demographic
        - Appropriate profile style

        Return analysis in JSON format with keys: account_type, region, interests, profile_style
        """

        try:
            response = await self.gemini_service.generate_reply(prompt, chat_id=f"account_analysis_{phone_number}")
            # Parse JSON response
            import json
            try:
                return json.loads(response)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.debug(f"Failed to parse JSON response: {e}")
                return {'account_type': 'general', 'interests': ['technology', 'general']}
        except Exception as e:
            logger.warning(f"Failed to analyze account: {e}")
            return {'account_type': 'general', 'interests': ['technology', 'general']}

    async def generate_profile_content(self, phone_number: str, account_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate intelligent profile content based on account analysis."""
        if not self.gemini_service:
            # Fallback content
            return {
                'first_name': 'Alex',
                'last_name': 'Johnson',
                'bio': 'Tech enthusiast and coffee lover ☕'
            }

        analysis_str = json.dumps(account_analysis) if account_analysis else "general account"

        # Use Gemini to generate realistic profile content
        prompt = f"""
        Generate a realistic Telegram profile for a new account based on this analysis: {analysis_str}

        Include:
        1. First name (appropriate for the region/demographic)
        2. Last name (optional, matching the region)
        3. Bio (short, natural description matching interests)
        4. Username suggestion (unique and relevant)

        Make it look like a real person, not a bot. Use natural language and emojis appropriately.
        """

        try:
            response = await self.gemini_service.generate_reply(prompt, chat_id=f"profile_gen_{phone_number}")
            # Parse the response and extract profile data
            # This would need more sophisticated parsing in a real implementation
            return {
                'first_name': 'Alex',
                'last_name': 'Johnson',
                'bio': response[:70] if response else 'Tech enthusiast and coffee lover ☕'
            }
        except Exception as e:
            logger.warning(f"Failed to generate profile content: {e}")
            return {
                'first_name': 'Alex',
                'last_name': 'Johnson',
                'bio': 'Tech enthusiast and coffee lover ☕'
            }

    async def suggest_profile_photo(self, phone_number: str, profile_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Suggest appropriate profile photo based on profile data."""
        if not self.gemini_service:
            return None

        prompt = f"""
        For a Telegram account with this profile: {json.dumps(profile_data)}

        Suggest what type of profile photo would be most appropriate:
        - Style (realistic, cartoon, professional, casual)
        - Theme (based on bio and interests)
        - Whether to use avatar or photo
        - Any specific recommendations

        Return in JSON format.
        """

        try:
            response = await self.gemini_service.generate_reply(prompt, chat_id=f"photo_suggest_{phone_number}")
            import json
            return json.loads(response)
        except Exception as e:
            logger.warning(f"Failed to suggest profile photo: {e}")
            return None

    async def generate_bio_for_account(self, phone_number: str, profile_data: Dict[str, Any]) -> Optional[str]:
        """Generate an intelligent bio for the account (sanitized)."""
        if not self.gemini_service:
            return None

        prompt = f"""
        Create a natural, engaging bio for a Telegram account with this profile: {json.dumps(profile_data)}

        Requirements:
        - Keep under 70 characters
        - Sound natural and human
        - Include relevant interests
        - Use appropriate emojis
        - Don't sound like marketing
        """

        try:
            from utils.input_validation import sanitize_html
            
            response = await self.gemini_service.generate_reply(prompt, chat_id=f"bio_gen_{phone_number}")
            if response:
                # Sanitize AI-generated content
                response = sanitize_html(response)
                if len(response) <= 70:
                    return response
                else:
                    return response[:67] + "..."
            return None
        except Exception as e:
            logger.warning(f"Failed to generate bio: {e}")
            return None

    async def suggest_contact_to_add(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Suggest a contact to add using Gemini AI or fallback strategy."""
        if not self.gemini_service:
            # Fallback strategy: suggest common/safe contacts
            # Generate a realistic-looking contact
            import random
            first_names = ['Alex', 'Sam', 'Jordan', 'Taylor', 'Morgan', 'Casey', 'Riley', 'Jamie']
            last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis']
            
            # Generate a phone number (use fake but valid format)
            country_code = '+1'
            area_code = random.choice(['555', '556', '557'])  # Reserved for testing
            number = f"{country_code}{area_code}{random.randint(1000000, 9999999)}"
            
            return {
                'phone_number': number,
                'first_name': random.choice(first_names),
                'last_name': random.choice(last_names)
            }
        
        # Use Gemini to suggest intelligent contacts
        try:
            prompt = f"""
            For a Telegram account {phone_number}, suggest a realistic contact to add.
            
            Return in JSON format:
            {{
                "phone_number": "+1234567890",
                "first_name": "Name",
                "last_name": "Last"
            }}
            
            Make it look natural and region-appropriate.
            """
            
            response = await self.gemini_service.generate_reply(
                prompt, 
                chat_id=f"contact_suggest_{phone_number}"
            )
            
            import json
            contact_data = json.loads(response)
            return contact_data
            
        except Exception as e:
            logger.debug(f"Failed to get AI contact suggestion: {e}")
            # Fall back to simple strategy
            return None

    async def suggest_group_to_join(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Suggest a group to join using AI or fallback strategy."""
        if not self.gemini_service:
            # Fallback strategy: suggest popular public groups
            # These are safe, general-purpose groups
            safe_groups = [
                {'username': 'telegram', 'chat_id': None},
                {'username': 'durov', 'chat_id': None},
            ]
            
            import random
            return random.choice(safe_groups) if safe_groups else None
        
        # Use Gemini to suggest appropriate groups
        try:
            prompt = f"""
            For a Telegram account {phone_number}, suggest a safe, public group to join.
            
            Return in JSON format:
            {{
                "username": "groupname",
                "chat_id": null,
                "reason": "why this group is appropriate"
            }}
            
            Suggest groups that are:
            - Public and easily joinable
            - Active but not spammy
            - General interest topics
            - Safe and legitimate
            """
            
            response = await self.gemini_service.generate_reply(
                prompt,
                chat_id=f"group_suggest_{phone_number}"
            )
            
            import json
            group_data = json.loads(response)
            return group_data
            
        except Exception as e:
            logger.debug(f"Failed to get AI group suggestion: {e}")
            return None

    async def generate_conversation_starter(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Generate a natural conversation starter."""
        if not self.gemini_service:
            return None

        prompt = """
        Generate a natural conversation starter message for Telegram.
        Make it casual, friendly, and likely to get a response.
        Keep it under 200 characters.
        """

        try:
            cache_key = f"conv_starter_{phone_number}"
            cached = self._get_cached_reply(cache_key)
            if cached:
                response = cached
            else:
                response = await self.gemini_service.generate_reply(prompt, chat_id=cache_key)
                if response:
                    self._set_cached_reply(cache_key, response)
            if response:
                return {
                    'message': response,
                    'target_type': 'contact',  # or 'group'
                    'target_id': None  # Would be filled in by the calling code
                }
        except Exception as e:
            logger.warning(f"Failed to generate conversation starter: {e}")

        return None
