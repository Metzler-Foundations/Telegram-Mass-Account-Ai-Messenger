"""
Media Intelligence - Analyze and optimize media content.

Features:
- Image quality analysis
- Engagement prediction
- Media type optimization
- Metadata analysis
"""

import logging
import sqlite3
import hashlib
from typing import Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MediaAnalysis:
    """Media file analysis results."""
    media_hash: str
    media_type: str  # photo, video, document
    file_size: int
    dimensions: Optional[Tuple[int, int]] = None
    
    # Quality metrics
    estimated_quality: str = "unknown"  # low, medium, high
    predicted_engagement: float = 0.5
    
    # Metadata
    has_faces: bool = False
    dominant_colors: list = None
    text_detected: bool = False
    
    # Performance
    times_used: int = 0
    avg_reactions: float = 0.0
    avg_response_rate: float = 0.0
    
    analyzed_at: datetime = None


class MediaIntelligence:
    """Media analysis and optimization system."""
    
    def __init__(self, db_path: str = "media_intelligence.db"):
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
    
    def _init_database(self):
        """Initialize media database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media_analysis (
                media_hash TEXT PRIMARY KEY,
                media_type TEXT,
                file_size INTEGER,
                width INTEGER,
                height INTEGER,
                estimated_quality TEXT,
                predicted_engagement REAL,
                has_faces INTEGER,
                text_detected INTEGER,
                times_used INTEGER DEFAULT 0,
                avg_reactions REAL,
                avg_response_rate REAL,
                analyzed_at TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_hash TEXT,
                used_in_chat INTEGER,
                reactions_count INTEGER,
                got_response INTEGER,
                timestamp TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def analyze_media(self, file_path: str, media_type: str = "photo") -> MediaAnalysis:
        """Analyze a media file.
        
        Args:
            file_path: Path to media file
            media_type: Type of media
            
        Returns:
            MediaAnalysis object
        """
        path = Path(file_path)
        
        # Calculate hash
        media_hash = self._calculate_hash(file_path)
        
        # Get file size
        file_size = path.stat().st_size
        
        # Basic analysis (would use PIL/OpenCV for real implementation)
        dimensions = None
        estimated_quality = "medium"
        predicted_engagement = 0.5
        
        # Try to get dimensions if image
        if media_type == "photo":
            try:
                from PIL import Image
                with Image.open(file_path) as img:
                    dimensions = img.size
                    # Estimate quality based on resolution
                    if dimensions[0] * dimensions[1] > 2000000:  # 2MP+
                        estimated_quality = "high"
                        predicted_engagement = 0.7
                    elif dimensions[0] * dimensions[1] < 500000:  # <0.5MP
                        estimated_quality = "low"
                        predicted_engagement = 0.3
            except ImportError:
                logger.debug("PIL not available for image analysis")
            except Exception as e:
                logger.debug(f"Error analyzing image: {e}")
        
        analysis = MediaAnalysis(
            media_hash=media_hash,
            media_type=media_type,
            file_size=file_size,
            dimensions=dimensions,
            estimated_quality=estimated_quality,
            predicted_engagement=predicted_engagement,
            analyzed_at=datetime.now()
        )
        
        # Save to database
        self._save_analysis(analysis)
        
        return analysis
    
    def _calculate_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _save_analysis(self, analysis: MediaAnalysis):
        """Save analysis to database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO media_analysis
            (media_hash, media_type, file_size, width, height, estimated_quality,
             predicted_engagement, has_faces, text_detected, times_used,
             avg_reactions, avg_response_rate, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis.media_hash, analysis.media_type, analysis.file_size,
            analysis.dimensions[0] if analysis.dimensions else None,
            analysis.dimensions[1] if analysis.dimensions else None,
            analysis.estimated_quality, analysis.predicted_engagement,
            int(analysis.has_faces), int(analysis.text_detected),
            analysis.times_used, analysis.avg_reactions,
            analysis.avg_response_rate, analysis.analyzed_at
        ))
        conn.commit()
        conn.close()
    
    def track_performance(self, media_hash: str, chat_id: int, 
                         reactions: int = 0, got_response: bool = False):
        """Track media performance.
        
        Args:
            media_hash: Media hash
            chat_id: Chat ID where used
            reactions: Number of reactions received
            got_response: Whether it got a response
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO media_performance
            (media_hash, used_in_chat, reactions_count, got_response, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (media_hash, chat_id, reactions, int(got_response), datetime.now()))
        conn.commit()
        conn.close()
        
        # Update aggregate stats
        self._update_media_stats(media_hash)
    
    def _update_media_stats(self, media_hash: str):
        """Update aggregate media statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Calculate averages
        cursor.execute("""
            SELECT COUNT(*), AVG(reactions_count), 
                   SUM(CASE WHEN got_response = 1 THEN 1 ELSE 0 END) * 1.0 / COUNT(*)
            FROM media_performance
            WHERE media_hash = ?
        """, (media_hash,))
        row = cursor.fetchone()
        
        if row and row[0] > 0:
            times_used, avg_reactions, response_rate = row
            cursor.execute("""
                UPDATE media_analysis
                SET times_used = ?, avg_reactions = ?, avg_response_rate = ?
                WHERE media_hash = ?
            """, (times_used, avg_reactions or 0, response_rate or 0, media_hash))
        
        conn.commit()
        conn.close()
    
    def get_best_performing_media(self, media_type: str = None, 
                                 limit: int = 10) -> list:
        """Get best performing media files.
        
        Args:
            media_type: Filter by media type
            limit: Number to return
            
        Returns:
            List of media analyses
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM media_analysis
            WHERE times_used >= 3
        """
        params = []
        
        if media_type:
            query += " AND media_type = ?"
            params.append(media_type)
        
        query += " ORDER BY avg_response_rate DESC, avg_reactions DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return [self._row_to_analysis(row) for row in results]
    
    def _row_to_analysis(self, row) -> MediaAnalysis:
        """Convert database row to MediaAnalysis."""
        return MediaAnalysis(
            media_hash=row[0],
            media_type=row[1],
            file_size=row[2],
            dimensions=(row[3], row[4]) if row[3] and row[4] else None,
            estimated_quality=row[5],
            predicted_engagement=row[6],
            has_faces=bool(row[7]),
            text_detected=bool(row[8]),
            times_used=row[9],
            avg_reactions=row[10] or 0.0,
            avg_response_rate=row[11] or 0.0,
            analyzed_at=datetime.fromisoformat(row[12]) if row[12] else None
        )

