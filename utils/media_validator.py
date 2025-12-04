#!/usr/bin/env python3
"""Media validation - Images, files, size limits."""

import logging
from pathlib import Path
from typing import Optional, tuple
from PIL import Image
import io

logger = logging.getLogger(__name__)


class MediaValidator:
    """Validates media files before processing."""
    
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_IMAGE_DIMENSIONS = (4096, 4096)
    
    ALLOWED_IMAGE_FORMATS = {'PNG', 'JPEG', 'JPG', 'GIF', 'WEBP'}
    
    @staticmethod
    def validate_file_size(file_path: str, max_size: Optional[int] = None) -> tuple:
        """Validate file size."""
        max_size = max_size or MediaValidator.MAX_FILE_SIZE
        
        try:
            size = Path(file_path).stat().st_size
            
            if size > max_size:
                return False, f"File too large ({size} > {max_size} bytes)"
            
            return True, "OK"
            
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def validate_image(image_path: str) -> tuple:
        """Validate image file."""
        try:
            # Check size first
            valid, msg = MediaValidator.validate_file_size(image_path, MediaValidator.MAX_IMAGE_SIZE)
            if not valid:
                return False, msg
            
            # Open and validate image
            with Image.open(image_path) as img:
                # Check format
                if img.format not in MediaValidator.ALLOWED_IMAGE_FORMATS:
                    return False, f"Invalid image format: {img.format}"
                
                # Check dimensions
                if img.width > MediaValidator.MAX_IMAGE_DIMENSIONS[0] or \
                   img.height > MediaValidator.MAX_IMAGE_DIMENSIONS[1]:
                    return False, f"Image too large: {img.width}x{img.height}"
                
                # Verify image is not corrupted
                img.verify()
            
            return True, "OK"
            
        except Exception as e:
            return False, f"Image validation failed: {e}"
    
    @staticmethod
    def safe_load_image(image_path: str, max_size: Optional[int] = None) -> Optional[Image.Image]:
        """Safely load image with size limit."""
        max_size = max_size or MediaValidator.MAX_IMAGE_SIZE
        
        try:
            # Check file size first
            file_size = Path(image_path).stat().st_size
            if file_size > max_size:
                logger.error(f"Image too large: {file_size} bytes")
                return None
            
            # Load image with memory limit
            with Image.open(image_path) as img:
                # Prevent decompression bomb
                Image.MAX_IMAGE_PIXELS = 89478485  # ~8K x 8K
                
                # Load into memory
                img.load()
                return img.copy()
                
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            return None





