"""
Media Processor - Image/video manipulation and optimization.

Features:
- Image resizing and optimization
- Metadata removal
- Format conversion
- Slight variations to avoid detection
"""

import logging
import hashlib
import random
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class MediaProcessor:
    """Process and manipulate media files."""
    
    @staticmethod
    def clean_metadata(input_path: str, output_path: str) -> bool:
        """Remove metadata from image to prevent linking.
        
        Args:
            input_path: Input file path
            output_path: Output file path
            
        Returns:
            True if successful
        """
        try:
            from PIL import Image
            
            # Open and save without EXIF
            with Image.open(input_path) as img:
                # Remove all metadata
                data = list(img.getdata())
                clean_img = Image.new(img.mode, img.size)
                clean_img.putdata(data)
                clean_img.save(output_path, quality=95)
            
            logger.info(f"Cleaned metadata from {input_path}")
            return True
            
        except ImportError:
            logger.warning("PIL not available for metadata cleaning")
            return False
        except Exception as e:
            logger.error(f"Error cleaning metadata: {e}")
            return False
    
    @staticmethod
    def create_variation(input_path: str, output_path: str, 
                        variation_level: str = "subtle") -> bool:
        """Create a slight variation of image to avoid duplicate detection.
        
        Args:
            input_path: Input file path
            output_path: Output file path
            variation_level: subtle, moderate, or significant
            
        Returns:
            True if successful
        """
        try:
            from PIL import Image, ImageEnhance
            
            with Image.open(input_path) as img:
                # Apply subtle modifications
                if variation_level == "subtle":
                    # Slight brightness adjustment
                    enhancer = ImageEnhance.Brightness(img)
                    img = enhancer.enhance(random.uniform(0.98, 1.02))
                    
                    # Slight contrast adjustment
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(random.uniform(0.98, 1.02))
                    
                elif variation_level == "moderate":
                    # More noticeable changes
                    enhancer = ImageEnhance.Brightness(img)
                    img = enhancer.enhance(random.uniform(0.95, 1.05))
                    
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(random.uniform(0.95, 1.05))
                    
                    # Slight rotation
                    img = img.rotate(random.uniform(-0.5, 0.5))
                
                elif variation_level == "significant":
                    # Significant changes
                    enhancer = ImageEnhance.Brightness(img)
                    img = enhancer.enhance(random.uniform(0.9, 1.1))
                    
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(random.uniform(0.9, 1.1))
                    
                    # Color adjustment
                    enhancer = ImageEnhance.Color(img)
                    img = enhancer.enhance(random.uniform(0.95, 1.05))
                
                img.save(output_path, quality=random.randint(90, 98))
            
            logger.info(f"Created {variation_level} variation: {output_path}")
            return True
            
        except ImportError:
            logger.warning("PIL not available for creating variations")
            return False
        except Exception as e:
            logger.error(f"Error creating variation: {e}")
            return False
    
    @staticmethod
    def optimize_for_telegram(input_path: str, output_path: str,
                             max_size_mb: float = 10.0) -> bool:
        """Optimize media for Telegram upload.
        
        Args:
            input_path: Input file path
            output_path: Output file path
            max_size_mb: Maximum file size in MB
            
        Returns:
            True if successful
        """
        try:
            from PIL import Image
            
            max_bytes = int(max_size_mb * 1024 * 1024)
            
            with Image.open(input_path) as img:
                # Check current size
                current_size = Path(input_path).stat().st_size
                
                if current_size <= max_bytes:
                    # Already small enough, just copy
                    img.save(output_path, quality=95)
                    return True
                
                # Calculate compression needed
                ratio = max_bytes / current_size
                quality = max(60, int(95 * ratio))
                
                # Resize if needed
                if ratio < 0.5:
                    new_size = tuple(int(dim * (ratio ** 0.5)) for dim in img.size)
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                img.save(output_path, quality=quality, optimize=True)
            
            logger.info(f"Optimized media: {output_path}")
            return True
            
        except ImportError:
            logger.warning("PIL not available for optimization")
            return False
        except Exception as e:
            logger.error(f"Error optimizing media: {e}")
            return False
    
    @staticmethod
    def calculate_hash(file_path: str) -> str:
        """Calculate file hash."""
        hash_md5 = hashlib.md5(usedforsecurity=False)  # Used for file identification, not security
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

