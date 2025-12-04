#!/usr/bin/env python3
"""Media support for messages - video, audio, stickers, GIFs."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class MediaSupport:
    """Handles various media types in messages."""
    
    SUPPORTED_VIDEO = ['.mp4', '.mov', '.avi', '.mkv']
    SUPPORTED_AUDIO = ['.mp3', '.wav', '.ogg', '.m4a']
    SUPPORTED_IMAGES = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    
    MAX_VIDEO_SIZE_MB = 50
    MAX_AUDIO_SIZE_MB = 50
    MAX_IMAGE_SIZE_MB = 10
    
    @staticmethod
    def validate_media(file_path: str, media_type: str) -> tuple[bool, Optional[str]]:
        """Validate media file."""
        path = Path(file_path)
        
        if not path.exists():
            return False, "File does not exist"
        
        # Check extension
        ext = path.suffix.lower()
        
        if media_type == 'video' and ext not in MediaSupport.SUPPORTED_VIDEO:
            return False, f"Unsupported video format: {ext}"
        
        if media_type == 'audio' and ext not in MediaSupport.SUPPORTED_AUDIO:
            return False, f"Unsupported audio format: {ext}"
        
        if media_type == 'image' and ext not in MediaSupport.SUPPORTED_IMAGES:
            return False, f"Unsupported image format: {ext}"
        
        # Check file size
        size_mb = path.stat().st_size / (1024 * 1024)
        
        max_size = {
            'video': MediaSupport.MAX_VIDEO_SIZE_MB,
            'audio': MediaSupport.MAX_AUDIO_SIZE_MB,
            'image': MediaSupport.MAX_IMAGE_SIZE_MB
        }.get(media_type, 10)
        
        if size_mb > max_size:
            return False, f"File too large: {size_mb:.1f}MB (max {max_size}MB)"
        
        return True, None
    
    @staticmethod
    async def send_video(client, chat_id: str, video_path: str, caption: str = None):
        """Send video message."""
        valid, error = MediaSupport.validate_media(video_path, 'video')
        
        if not valid:
            logger.error(f"Video validation failed: {error}")
            raise ValueError(error)
        
        try:
            await client.send_video(
                chat_id=chat_id,
                video=video_path,
                caption=caption
            )
            logger.info(f"Sent video to {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send video: {e}")
            raise
    
    @staticmethod
    async def send_audio(client, chat_id: str, audio_path: str, caption: str = None):
        """Send audio message."""
        valid, error = MediaSupport.validate_media(audio_path, 'audio')
        
        if not valid:
            logger.error(f"Audio validation failed: {error}")
            raise ValueError(error)
        
        try:
            await client.send_audio(
                chat_id=chat_id,
                audio=audio_path,
                caption=caption
            )
            logger.info(f"Sent audio to {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")
            raise
    
    @staticmethod
    async def send_sticker(client, chat_id: str, sticker_id: str):
        """Send sticker."""
        try:
            await client.send_sticker(
                chat_id=chat_id,
                sticker=sticker_id
            )
            logger.info(f"Sent sticker to {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send sticker: {e}")
            raise
    
    @staticmethod
    async def send_animation(client, chat_id: str, animation_path: str):
        """Send GIF/animation."""
        try:
            await client.send_animation(
                chat_id=chat_id,
                animation=animation_path
            )
            logger.info(f"Sent animation to {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send animation: {e}")
            raise


async def send_media(client, chat_id: str, media_path: str, media_type: str):
    """Send media of specified type."""
    if media_type == 'video':
        await MediaSupport.send_video(client, chat_id, media_path)
    elif media_type == 'audio':
        await MediaSupport.send_audio(client, chat_id, media_path)
    elif media_type == 'gif':
        await MediaSupport.send_animation(client, chat_id, media_path)
    else:
        raise ValueError(f"Unsupported media type: {media_type}")



