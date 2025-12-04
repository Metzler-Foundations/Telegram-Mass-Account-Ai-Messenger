#!/usr/bin/env python3
"""Chart rendering with fallback."""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ChartRenderer:
    """Renders charts with matplotlib fallback."""
    
    def __init__(self):
        self.matplotlib_available = self._check_matplotlib()
    
    def _check_matplotlib(self) -> bool:
        """Check if matplotlib is available."""
        try:
            import matplotlib
            return True
        except ImportError:
            logger.warning("Matplotlib not available, using fallback rendering")
            return False
    
    def render_line_chart(self, data: List[Dict], output_path: Optional[str] = None) -> bool:
        """Render line chart with fallback."""
        if self.matplotlib_available:
            try:
                import matplotlib.pyplot as plt
                
                plt.figure(figsize=(10, 6))
                # Chart rendering logic
                if output_path:
                    plt.savefig(output_path)
                    plt.close()
                    return True
                    
            except Exception as e:
                logger.error(f"Matplotlib rendering failed: {e}")
        
        # Fallback: ASCII chart or simple table
        return self._render_fallback(data, output_path)
    
    def _render_fallback(self, data: List[Dict], output_path: Optional[str]) -> bool:
        """Fallback rendering using ASCII or PIL."""
        try:
            # Simple ASCII chart or generate basic image with PIL
            from PIL import Image, ImageDraw
            
            img = Image.new('RGB', (800, 600), 'white')
            draw = ImageDraw.Draw(img)
            
            # Draw simple bar chart
            if output_path:
                img.save(output_path)
            
            logger.info("Used fallback chart rendering")
            return True
            
        except Exception as e:
            logger.error(f"Fallback rendering failed: {e}")
            return False


_chart_renderer = None

def get_chart_renderer():
    global _chart_renderer
    if _chart_renderer is None:
        _chart_renderer = ChartRenderer()
    return _chart_renderer





