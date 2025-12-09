import asyncio
import logging
import random
import json
import os
import time
import hashlib
import base64
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
import aiofiles
import requests
import aiohttp

from pyrogram import Client
from pyrogram.types import User, Chat
from ai.gemini_service import GeminiService
from anti_detection.anti_detection_system import AntiDetectionSystem
from accounts.username_generator import UsernameGenerator

if TYPE_CHECKING:
    from accounts.account_creator import AccountCreator, DeviceFingerprint
    from accounts.account_manager import AccountManager

logger = logging.getLogger(__name__)


class CloneSafetyLevel(Enum):
    """Safety levels for cloning operations."""

    ULTRA_SAFE = "ultra_safe"  # Maximum delays, minimal changes
    SAFE = "safe"  # Balanced safety and speed
    MODERATE = "moderate"  # Faster but still cautious
    AGGRESSIVE = "aggressive"  # Fast cloning, higher risk


class CloneComponent(Enum):
    """Components that can be cloned."""

    PROFILE_INFO = "profile_info"
    PROFILE_PHOTO = "profile_photo"
    BIO = "bio"
    USERNAME = "username"
    CONTACTS = "contacts"
    CHATS = "chats"
    GROUPS = "groups"
    CHANNELS = "channels"
    MEDIA = "media"
    SETTINGS = "settings"


@dataclass
class CloneJob:
    """Represents a cloning job."""

    job_id: str
    source_username: str
    target_phone_number: str
    components: List[CloneComponent]
    safety_level: CloneSafetyLevel
    created_at: datetime
    progress: float = 0.0
    status: str = "queued"
    error_message: Optional[str] = None
    cloned_data: Dict[str, Any] = None
    task: Optional[asyncio.Task] = None

    def __post_init__(self):
        if self.cloned_data is None:
            self.cloned_data = {}


@dataclass
class CloneConfig:
    """Configuration for cloning operations."""

    # Timing configurations
    min_delay_between_components: int = 300  # 5 minutes
    max_delay_between_components: int = 1800  # 30 minutes
    photo_download_delay: int = 60  # 1 minute
    profile_update_delay: int = 120  # 2 minutes

    # Safety configurations
    randomize_order: bool = True
    add_noise_to_data: bool = True
    use_different_device: bool = True
    respect_rate_limits: bool = True

    # Component-specific settings
    max_contacts_to_clone: int = 50
    max_groups_to_clone: int = 20
    max_channels_to_clone: int = 10
    bio_max_length: int = 70


class AdvancedCloningSystem:
    """Advanced system for safely cloning Telegram accounts with anti-detection measures."""

    def __init__(
        self,
        gemini_service: Optional[GeminiService] = None,
        account_manager: Optional["AccountManager"] = None,
    ):
        self.gemini_service = gemini_service
        self.account_manager = account_manager
        self.config = CloneConfig()
        self.username_generator = UsernameGenerator()

        # Job management
        self.active_jobs: Dict[str, CloneJob] = {}
        self.completed_jobs: List[CloneJob] = []
        self.failed_jobs: List[CloneJob] = []

        # Anti-detection
        self.anti_detection = AntiDetectionSystem()
        # Import DeviceFingerprint here to avoid circular import
        try:
            from account_creator import DeviceFingerprint

            self.device_fingerprint = DeviceFingerprint()
        except ImportError:
            self.device_fingerprint = None

        # Data storage
        self.cloned_profiles_dir = Path("cloned_profiles")
        self.cloned_profiles_dir.mkdir(exist_ok=True)

        # Session management for source account access
        self.source_sessions: Dict[str, Dict] = {}

    async def clone_account(
        self,
        source_username: str,
        target_phone_number: str,
        components: List[CloneComponent] = None,
        safety_level: CloneSafetyLevel = CloneSafetyLevel.SAFE,
    ) -> str:
        """Start an account cloning job."""
        if components is None:
            components = [
                CloneComponent.PROFILE_INFO,
                CloneComponent.PROFILE_PHOTO,
                CloneComponent.BIO,
                CloneComponent.USERNAME,
            ]

        job_id = f"clone_{source_username}_{target_phone_number}_{int(time.time())}"

        job = CloneJob(
            job_id=job_id,
            source_username=source_username,
            target_phone_number=target_phone_number,
            components=components,
            safety_level=safety_level,
            created_at=datetime.now(),
        )

        self.active_jobs[job_id] = job

        # Start cloning process asynchronously and track the task
        try:
            # Try to get running loop first (preferred in Python 3.10+)
            try:
                loop = asyncio.get_running_loop()
                task = asyncio.create_task(self._execute_clone_job(job))
                job.task = task  # Store task reference to prevent garbage collection
            except RuntimeError:
                # No running loop, create new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                task = loop.create_task(self._execute_clone_job(job))
                job.task = task
        except Exception as e:
            logger.error(f"Failed to start cloning job: {e}")
            raise

        logger.info(f"🧬 Started cloning job {job_id}: {source_username} -> {target_phone_number}")
        return job_id

    async def _execute_clone_job(self, job: CloneJob):
        """Execute a cloning job with safety measures."""
        try:
            job.status = "gathering_source_data"

            # Step 1: Gather source account data safely
            source_data = await self._gather_source_data(job.source_username, job.safety_level)
            if not source_data:
                job.status = "failed"
                job.error_message = "Could not gather source account data"
                self._move_job_to_failed(job)
                return

            job.cloned_data["source_data"] = source_data
            job.progress = 20

            # Step 2: Prepare cloning components
            job.status = "preparing_components"
            clone_components = self._prepare_clone_components(
                source_data, job.components, job.safety_level
            )
            job.progress = 30

            # Step 3: Execute cloning on target account
            job.status = "cloning_to_target"
            success = await self._clone_to_target_account(
                job.target_phone_number, clone_components, job.safety_level
            )

            if success:
                job.status = "completed"
                job.progress = 100
                self._move_job_to_completed(job)
                logger.info(f"✅ Cloning completed successfully: {job.job_id}")
            else:
                job.status = "failed"
                job.error_message = "Cloning to target account failed"
                self._move_job_to_failed(job)

        except Exception as e:
            logger.error(f"Cloning job failed {job.job_id}: {e}")
            job.status = "failed"
            job.error_message = str(e)
            self._move_job_to_failed(job)

    async def _gather_source_data(
        self, username: str, safety_level: CloneSafetyLevel
    ) -> Optional[Dict[str, Any]]:
        """Gather data from source account with anti-detection measures."""
        try:
            # Create a temporary client for data gathering
            temp_client, created_temp_session = await self._create_temp_client_for_scraping()

            if not temp_client:
                logger.error("Could not create temporary client for data gathering")
                return None

            try:
                # Apply safety delays
                await self._apply_safety_delay(safety_level, "data_gathering_start")

                # Get user information
                try:
                    user = await temp_client.get_users(username)
                except Exception as e:
                    logger.error(f"Failed to get user {username}: {e}")
                    return None

                if not user:
                    logger.error(f"Could not find user: {username}")
                    return None

                source_data = {
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "bio": getattr(user, "bio", None),
                    "photo": user.photo,
                    "is_premium": getattr(user, "is_premium", False),
                    "phone_number": getattr(user, "phone_number", None),
                    "collected_at": datetime.now().isoformat(),
                }

                # Gather additional data based on safety level
                if safety_level in [CloneSafetyLevel.MODERATE, CloneSafetyLevel.AGGRESSIVE]:
                    # Get profile photos
                    source_data["profile_photos"] = await self._get_profile_photos_safe(
                        temp_client, user.id
                    )

                    # Get common chats (if accessible)
                    source_data["common_chats"] = await self._get_common_chats_safe(
                        temp_client, user.id
                    )

                # Apply safety delay before finishing
                await self._apply_safety_delay(safety_level, "data_gathering_end")

                logger.info(f"📊 Gathered source data for {username}")
                return source_data

            finally:
                if created_temp_session and temp_client:
                    try:
                        await temp_client.disconnect()
                        logger.info("Temporary scraping client disconnected")
                    except Exception as cleanup_error:
                        logger.warning(
                            f"Failed to disconnect temporary scraping client: {cleanup_error}"
                        )

        except Exception as e:
            logger.error(f"Failed to gather source data for {username}: {e}")
            return None

    def _prepare_clone_components(
        self, source_data: Dict, components: List[CloneComponent], safety_level: CloneSafetyLevel
    ) -> Dict[str, Any]:
        """Prepare cloning components with modifications for safety."""
        clone_components = {}

        for component in components:
            if component == CloneComponent.PROFILE_INFO:
                clone_components["profile_info"] = self._prepare_profile_info(
                    source_data, safety_level
                )

            elif component == CloneComponent.PROFILE_PHOTO:
                clone_components["profile_photo"] = self._prepare_profile_photo(
                    source_data, safety_level
                )

            elif component == CloneComponent.BIO:
                clone_components["bio"] = self._prepare_bio(source_data, safety_level)

            elif component == CloneComponent.USERNAME:
                clone_components["username"] = self._prepare_username(source_data, safety_level)

            # Add other components as needed

        return clone_components

    async def _clone_to_target_account(
        self,
        target_phone_number: str,
        clone_components: Dict[str, Any],
        safety_level: CloneSafetyLevel,
    ) -> bool:
        """Clone prepared components to target account."""
        try:
            # Get target account client
            target_client, created_temp_session = await self._get_target_client(target_phone_number)
            if not target_client:
                logger.error(f"Could not get client for target account: {target_phone_number}")
                return False

            try:
                # Randomize component order if configured
                component_order = list(clone_components.keys())
                if self.config.randomize_order:
                    random.shuffle(component_order)

                total_components = len(component_order)
                completed = 0

                for component_name in component_order:
                    component_data = clone_components[component_name]

                    # Apply safety delay between components
                    await self._apply_safety_delay(safety_level, f"component_{component_name}")

                    # Clone the component
                    success = await self._clone_component(
                        target_client, component_name, component_data, safety_level
                    )

                    if not success:
                        logger.warning(f"Failed to clone component {component_name}")
                        # Continue with other components unless it's critical

                    completed += 1
                    progress = completed / total_components * 70 + 30  # 30-100% range

                logger.info(f"🎯 Cloning completed for {target_phone_number}")
                return True

            finally:
                if created_temp_session and target_client:
                    try:
                        await target_client.disconnect()
                        logger.info(
                            f"Disconnected temporary target client for {target_phone_number}"
                        )
                    except Exception as cleanup_error:
                        logger.warning(
                            f"Failed to disconnect target client {target_phone_number}: {cleanup_error}"
                        )

        except Exception as e:
            logger.error(f"Failed to clone to target account {target_phone_number}: {e}")
            return False

    async def _clone_component(
        self,
        client: Client,
        component_name: str,
        component_data: Any,
        safety_level: CloneSafetyLevel,
    ) -> bool:
        """Clone a specific component to the target account."""
        try:
            if component_name == "profile_info":
                return await self._clone_profile_info(client, component_data, safety_level)

            elif component_name == "profile_photo":
                return await self._clone_profile_photo(client, component_data, safety_level)

            elif component_name == "bio":
                return await self._clone_bio(client, component_data, safety_level)

            elif component_name == "username":
                return await self._clone_username(client, component_data, safety_level)

            else:
                logger.warning(f"Unknown component: {component_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to clone component {component_name}: {e}")
            return False

    def _prepare_profile_info(
        self, source_data: Dict, safety_level: CloneSafetyLevel
    ) -> Dict[str, Any]:
        """Prepare profile info for cloning with modifications."""
        profile_info = {
            "first_name": source_data.get("first_name"),
            "last_name": source_data.get("last_name"),
        }

        # Apply modifications based on safety level
        if safety_level == CloneSafetyLevel.ULTRA_SAFE:
            # Make significant changes to avoid exact matches
            profile_info["first_name"] = self._modify_name_for_safety(
                profile_info["first_name"], safety_level
            )
            if profile_info["last_name"]:
                profile_info["last_name"] = self._modify_name_for_safety(
                    profile_info["last_name"], safety_level
                )

        elif safety_level == CloneSafetyLevel.SAFE:
            # Make minor modifications
            profile_info["first_name"] = self._add_noise_to_name(profile_info["first_name"])

        # For MODERATE and AGGRESSIVE, use names as-is

        return profile_info

    def _prepare_profile_photo(
        self, source_data: Dict, safety_level: CloneSafetyLevel
    ) -> Dict[str, Any]:
        """Prepare profile photo for cloning."""
        photo_data = {"photo": source_data.get("photo"), "photo_path": None}

        return photo_data

    def _prepare_bio(self, source_data: Dict, safety_level: CloneSafetyLevel) -> Dict[str, Any]:
        """Prepare bio for cloning with AI modifications."""
        bio = source_data.get("bio", "")

        if not bio:
            return {"bio": None}

        # For now, use bio as-is (AI modification would need async context)
        # This will be handled during cloning if needed
        modified_bio = bio

        # Ensure bio length is within limits
        if len(modified_bio) > self.config.bio_max_length:
            modified_bio = modified_bio[: self.config.bio_max_length - 3] + "..."

        return {
            "bio": modified_bio,
            "needs_ai_modification": safety_level
            in [CloneSafetyLevel.ULTRA_SAFE, CloneSafetyLevel.SAFE]
            and self.gemini_service,
        }

    def _prepare_username(
        self, source_data: Dict, safety_level: CloneSafetyLevel
    ) -> Dict[str, Any]:
        """Prepare username for cloning with visually similar generation."""
        username = source_data.get("username")

        if not username:
            return {"username": None}

        # Use advanced username generator for visually similar usernames
        # This will be checked for availability during cloning
        return {"username": username, "source_username": username}

    async def _clone_profile_info(
        self, client: Client, profile_data: Dict, safety_level: CloneSafetyLevel
    ) -> bool:
        """Clone profile info to target account."""
        try:
            await client.update_profile(
                first_name=profile_data.get("first_name"), last_name=profile_data.get("last_name")
            )
            logger.info("✅ Cloned profile info")
            return True
        except Exception as e:
            logger.error(f"Failed to clone profile info: {e}")
            return False

    async def _clone_profile_photo(
        self, client: Client, photo_data: Dict, safety_level: CloneSafetyLevel
    ) -> bool:
        """Clone profile photo to target account."""
        try:
            photo = photo_data.get("photo")
            if not photo:
                return True  # No photo to clone

            # Download photo first
            photo_path = await self._download_profile_photo_safe(client, photo)

            if photo_path and os.path.exists(photo_path):
                # Use stealth photo update to avoid "updated 1 day ago" message
                await self._set_profile_photo_stealth(client, photo_path)

                # Clean up downloaded file
                os.remove(photo_path)

                logger.info("✅ Cloned profile photo")
                return True
            else:
                logger.warning("Could not download profile photo")
                return False

        except Exception as e:
            logger.error(f"Failed to clone profile photo: {e}")
            return False

    async def _clone_bio(
        self, client: Client, bio_data: Dict, safety_level: CloneSafetyLevel
    ) -> bool:
        """Clone bio to target account."""
        try:
            bio = bio_data.get("bio")
            needs_ai_mod = bio_data.get("needs_ai_modification", False)

            # Apply AI modification if needed (now in async context)
            if needs_ai_mod and self.gemini_service and bio:
                bio = await self._modify_bio_with_ai(bio, safety_level)

            if bio:
                await client.update_profile(bio=bio)
                logger.info("✅ Cloned bio")
            return True
        except Exception as e:
            logger.error(f"Failed to clone bio: {e}")
            return False

    async def _clone_username(
        self, client: Client, username_data: Dict, safety_level: CloneSafetyLevel
    ) -> bool:
        """Clone username to target account with availability checking."""
        try:
            source_username = username_data.get("source_username") or username_data.get("username")
            if not source_username:
                return True  # No username to set is not an error

            # Generate visually similar username and check availability
            available_username = await self.username_generator.find_available_similar_username(
                client, source_username, max_attempts=100
            )

            if available_username:
                await client.set_username(available_username)
                logger.info(
                    f"✅ Set visually similar username: {available_username} (from {source_username})"
                )
                return True
            else:
                logger.warning(f"Could not find available similar username for {source_username}")
                # Try the original username as fallback
                try:
                    is_available, _ = await self.username_generator.check_username_availability(
                        client, source_username
                    )
                    if is_available:
                        await client.set_username(source_username)
                        logger.info(f"✅ Set original username: {source_username}")
                        return True
                except (ValueError, RuntimeError, Exception) as e:
                    logger.debug(f"Error setting username {source_username}: {e}")

                return False  # Failed to set any username
        except Exception as e:
            logger.error(f"Failed to clone username: {e}")
            return False

    async def _create_temp_client_for_scraping(self) -> Tuple[Optional[Client], bool]:
        """Create a temporary client for scraping source data."""
        try:
            # Prefer using an existing connected account from AccountManager to avoid new session flags
            if self.account_manager:
                online_accounts = self.account_manager.get_online_accounts()
                if online_accounts:
                    # Pick a random online account to distribute load
                    phone = random.choice(online_accounts)
                    try:
                        client = self.account_manager.active_clients.get(phone)
                        if client and hasattr(client, "client"):
                            # Ensure it's connected
                            if not client.client.is_connected:
                                await client.client.connect()
                            logger.info(f"Using existing account {phone} for scraping")
                            return client.client, False
                    except Exception as e:
                        logger.warning(f"Failed to reuse account {phone} for scraping: {e}")

            # Fallback: Create a new session (discouraged but necessary if no accounts)
            logger.warning("Creating new temporary session for scraping (not recommended)")

            session_name = f"scraper_{int(time.time())}_{random.randint(1000, 9999)}"
            api_id = os.getenv("TELEGRAM_API_ID", "")
            api_hash = os.getenv("TELEGRAM_API_HASH", "")

            if not api_id or not api_hash:
                logger.error("Missing Telegram API credentials.")
                return None, False

            client = Client(session_name, api_id=api_id, api_hash=api_hash)
            await client.connect()
            return client, True

        except Exception as e:
            logger.error(f"Failed to create scraping client: {e}")
            return None, False

    async def _get_target_client(self, phone_number: str) -> Tuple[Optional[Client], bool]:
        """Get client for target account."""
        try:
            # Try to get client from AccountManager if available
            if hasattr(self, "account_manager") and self.account_manager:
                # Check active clients first
                if phone_number in self.account_manager.active_clients:
                    client_wrapper = self.account_manager.active_clients[phone_number]
                    if hasattr(client_wrapper, "client"):
                        return client_wrapper.client, False

            # Fallback: Try to load from session file directly if not active
            session_name = f"account_{phone_number.replace('+', '')}"
            try:
                client = Client(session_name)
                await client.connect()
                return client, True
            except (ConnectionError, RuntimeError, Exception) as e:
                logger.debug(f"Error loading client from session {session_name}: {e}")

            logger.warning(f"Could not get client for target account: {phone_number}")
            return None, False
        except Exception as e:
            logger.error(f"Failed to get target client for {phone_number}: {e}")
            return None, False

    async def _download_profile_photo_safe(self, client: Client, photo_object) -> Optional[str]:
        """Download profile photo with safety measures."""
        try:
            if not photo_object:
                return None

            # Apply download delay
            await asyncio.sleep(self.config.photo_download_delay)

            # Create download directory
            download_path = Path("downloads/cloned_photos")
            download_path.mkdir(parents=True, exist_ok=True)

            # Use Pyrogram's download_media
            # photo_object can be a Photo object or File ID
            # We need a client instance to download
            if not client:
                logger.error("Client required to download media")
                return None

            file_path = await client.download_media(
                message=photo_object.big_file_id,
                file_name=str(download_path / f"photo_{int(time.time())}.jpg"),
            )

            if file_path:
                logger.debug(f"Profile photo downloaded to: {file_path}")
                return file_path

            return None
        except Exception as e:
            logger.error(f"Failed to download profile photo: {e}")
            return None

    async def _get_profile_photos_safe(self, client: Client, user_id: int) -> List[Dict]:
        """Get profile photos safely."""
        try:
            photos = await client.get_chat_photos(user_id, limit=5)
            # photos is async generator or list? get_chat_photos returns async generator
            photo_list = []
            async for photo in photos:
                photo_list.append({"photo": photo})
            return photo_list
        except Exception as e:
            logger.warning(f"Failed to get profile photos: {e}")
            return []

    async def _get_common_chats_safe(self, client: Client, user_id: int) -> List[Dict]:
        """Get common chats safely."""
        try:
            common = await client.get_common_chats(user_id)
            return [{"id": chat.id, "title": chat.title} for chat in common]
        except Exception as e:
            logger.warning(f"Failed to get common chats: {e}")
            return []

    async def _apply_safety_delay(self, safety_level: CloneSafetyLevel, operation: str):
        """Apply safety delay based on safety level."""
        base_delay = random.uniform(
            self.config.min_delay_between_components, self.config.max_delay_between_components
        )

        # Adjust delay based on safety level
        if safety_level == CloneSafetyLevel.ULTRA_SAFE:
            base_delay *= 2.0
        elif safety_level == CloneSafetyLevel.SAFE:
            base_delay *= 1.5
        elif safety_level == CloneSafetyLevel.MODERATE:
            base_delay *= 1.0
        elif safety_level == CloneSafetyLevel.AGGRESSIVE:
            base_delay *= 0.5

        await asyncio.sleep(base_delay)

    def _modify_name_for_safety(self, name: str, safety_level: CloneSafetyLevel) -> str:
        """Modify name to avoid detection."""
        if not name:
            return name

        if safety_level == CloneSafetyLevel.ULTRA_SAFE:
            # More significant changes
            if len(name) > 3:
                # Change middle characters
                chars = list(name)
                for i in range(1, len(chars) - 1):
                    if random.random() < 0.3:  # 30% chance
                        chars[i] = self._get_similar_char(chars[i])
                return "".join(chars)

        return name

    def _add_noise_to_name(self, name: str) -> str:
        """Add small noise to name."""
        if not name or len(name) < 3:
            return name

        # Occasionally add a middle initial or modify slightly
        if random.random() < 0.2:  # 20% chance
            return name + " Jr."

        return name

    async def _modify_bio_with_ai(self, bio: str, safety_level: CloneSafetyLevel) -> str:
        """Modify bio using AI for safety."""
        if not self.gemini_service or not bio:
            return bio

        try:
            prompt = f"""Modify this Telegram bio to make it unique while keeping the same general meaning and style. 
            Keep it under 70 characters. Return only the modified bio, nothing else.
            
            Original bio: {bio}
            
            Modified bio:"""

            modified_bio = await self.gemini_service.generate_reply(
                prompt, chat_id="bio_modification"
            )

            # Clean up the response
            if modified_bio:
                modified_bio = modified_bio.strip().strip('"').strip("'")
                if len(modified_bio) > 70:
                    modified_bio = modified_bio[:67] + "..."

            logger.debug(f"AI modified bio: {bio} -> {modified_bio}")
            return modified_bio if modified_bio else bio
        except Exception as e:
            logger.warning(f"Failed to modify bio with AI: {e}")
            return bio

    async def _set_profile_photo_stealth(self, client: Client, photo_path: str):
        """
        Set profile photo in a way that avoids showing "updated 1 day ago" message.
        Strategy: Set photo, then immediately update profile with a minor change to reset timestamp.
        """
        try:
            # First, set the profile photo
            await client.set_profile_photo(photo=photo_path)

            # Wait a moment for the update to process
            await asyncio.sleep(2)

            # Get current profile to make a minimal update
            me = await client.get_me()
            current_bio = getattr(me, "bio", "") or ""

            # Make a tiny, invisible change to bio (add/remove a space at end, or add invisible char)
            # This resets the "last updated" timestamp without being noticeable
            if current_bio:
                # Add a zero-width space at the end (invisible)
                new_bio = current_bio + "\u200B"  # Zero-width space
            else:
                # If no bio, set a minimal one
                new_bio = " "  # Single space (minimal)

            # Update profile with the modified bio
            # This will reset the "last updated" timestamp
            await client.update_profile(bio=new_bio)

            # Wait a moment
            await asyncio.sleep(1)

            # Restore original bio (if it existed)
            if current_bio and current_bio != new_bio:
                await client.update_profile(bio=current_bio)

            logger.debug("Profile photo set with stealth update to avoid timestamp detection")

        except Exception as e:
            logger.warning(f"Stealth photo update failed, falling back to normal: {e}")
            # Fallback to normal photo setting
            await client.set_profile_photo(photo=photo_path)

    def _get_similar_char(self, char: str) -> str:
        """Get a similar character for name modification."""
        similar_chars = {
            "a": ["a", "á", "ä"],
            "e": ["e", "é", "ë"],
            "i": ["i", "í", "ï"],
            "o": ["o", "ó", "ö"],
            "u": ["u", "ú", "ü"],
            "s": ["s", "š"],
            "c": ["c", "ç"],
            "n": ["n", "ñ"],
        }

        char_lower = char.lower()
        if char_lower in similar_chars:
            similar = similar_chars[char_lower]
            replacement = random.choice(similar)
            return replacement if char.islower() else replacement.upper()

        return char

    def _move_job_to_completed(self, job: CloneJob):
        """Move job to completed list."""
        if job.job_id in self.active_jobs:
            del self.active_jobs[job.job_id]
        self.completed_jobs.append(job)

    def _move_job_to_failed(self, job: CloneJob):
        """Move job to failed list."""
        if job.job_id in self.active_jobs:
            del self.active_jobs[job.job_id]
        self.failed_jobs.append(job)

    def get_job_status(self, job_id: str) -> Optional[CloneJob]:
        """Get status of a cloning job."""
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]

        for job in self.completed_jobs:
            if job.job_id == job_id:
                return job

        for job in self.failed_jobs:
            if job.job_id == job_id:
                return job

        return None

    def get_all_jobs(self) -> List[CloneJob]:
        """Get all cloning jobs."""
        return list(self.active_jobs.values()) + self.completed_jobs + self.failed_jobs
