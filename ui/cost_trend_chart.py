"""
Cost Trend Chart Widget - Visualizes cost trends over time.
"""

import logging
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
import sqlite3

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QGroupBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("matplotlib not available, cost charts will be disabled")

logger = logging.getLogger(__name__)


class CostTrendChart(QWidget):
    """Widget displaying cost trends over time."""
    
    def __init__(self, audit_db_path: str = "accounts_audit.db", parent=None):
        super().__init__(parent)
        self.audit_db_path = audit_db_path
        self.setup_ui()
        
        # Auto-refresh every 60 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_chart)
        self.refresh_timer.start(60000)
        
        # Initial load
        self.refresh_chart()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("💰 Cost Trends")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Time period selector
        period_label = QLabel("Period:")
        period_label.setStyleSheet("color: #b5bac1;")
        header_layout.addWidget(period_label)
        
        self.period_combo = QComboBox()
        self.period_combo.addItems(["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"])
        self.period_combo.setCurrentIndex(1)  # Default to 30 days
        self.period_combo.currentIndexChanged.connect(self.refresh_chart)
        self.period_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2d31;
                color: #b5bac1;
                border: 1px solid #3f4147;
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 120px;
            }
            QComboBox:hover {
                border-color: #5865f2;
            }
        """)
        header_layout.addWidget(self.period_combo)
        
        layout.addLayout(header_layout)
        
        # Chart container
        chart_group = QGroupBox()
        chart_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #2b2d31;
                border-radius: 8px;
                background-color: #1e1f22;
            }
        """)
        chart_layout = QVBoxLayout(chart_group)
        chart_layout.setContentsMargins(12, 12, 12, 12)
        
        if MATPLOTLIB_AVAILABLE:
            # Create matplotlib figure
            self.figure = Figure(figsize=(10, 6), facecolor='#1e1f22')
            self.canvas = FigureCanvas(self.figure)
            self.canvas.setStyleSheet("background-color: #1e1f22;")
            chart_layout.addWidget(self.canvas)
        else:
            # Fallback message
            no_chart_label = QLabel("📊 Cost trend charts require matplotlib.\nInstall with: pip install matplotlib")
            no_chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_chart_label.setStyleSheet("color: #949ba4; padding: 40px;")
            chart_layout.addWidget(no_chart_label)
        
        layout.addWidget(chart_group)
        
        # Summary stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        
        self.total_cost_label = QLabel("Total: $0.00")
        self.total_cost_label.setStyleSheet("color: #b5bac1; font-size: 14px; font-weight: 500;")
        stats_layout.addWidget(self.total_cost_label)
        
        self.avg_daily_label = QLabel("Avg Daily: $0.00")
        self.avg_daily_label.setStyleSheet("color: #b5bac1; font-size: 14px; font-weight: 500;")
        stats_layout.addWidget(self.avg_daily_label)
        
        self.trend_label = QLabel("Trend: →")
        self.trend_label.setStyleSheet("color: #b5bac1; font-size: 14px; font-weight: 500;")
        stats_layout.addWidget(self.trend_label)
        
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
    
    def get_cost_data(self, days: Optional[int] = None) -> List[Tuple[datetime, float]]:
        """
        Get cost data from audit database.
        
        Args:
            days: Number of days to look back (None = all time)
            
        Returns:
            List of (timestamp, cost) tuples
        """
        try:
            with sqlite3.connect(self.audit_db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if days:
                    cutoff = datetime.now() - timedelta(days=days)
                    query = '''
                        SELECT DATE(timestamp) as date, SUM(sms_cost) as daily_cost
                        FROM audit_events
                        WHERE sms_cost IS NOT NULL AND sms_cost > 0
                          AND timestamp >= ?
                        GROUP BY DATE(timestamp)
                        ORDER BY date ASC
                    '''
                    cursor = conn.execute(query, (cutoff,))
                else:
                    query = '''
                        SELECT DATE(timestamp) as date, SUM(sms_cost) as daily_cost
                        FROM audit_events
                        WHERE sms_cost IS NOT NULL AND sms_cost > 0
                        GROUP BY DATE(timestamp)
                        ORDER BY date ASC
                    '''
                    cursor = conn.execute(query)
                
                data = []
                for row in cursor:
                    date_str = row['date']
                    cost = row['daily_cost'] or 0.0
                    try:
                        date = datetime.strptime(date_str, '%Y-%m-%d')
                        data.append((date, float(cost)))
                    except ValueError:
                        continue
                
                return data
                
        except Exception as e:
            logger.error(f"Failed to get cost data: {e}")
            return []
    
    def refresh_chart(self):
        """Refresh the chart with latest data."""
        if not MATPLOTLIB_AVAILABLE:
            return
        
        try:
            # Get selected period
            period_index = self.period_combo.currentIndex()
            days_map = {0: 7, 1: 30, 2: 90, 3: None}
            days = days_map[period_index]
            
            # Get data
            data = self.get_cost_data(days)
            
            if not data:
                # Show empty state
                self.figure.clear()
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 'No cost data available', 
                       ha='center', va='center', 
                       transform=ax.transAxes,
                       color='#949ba4', fontsize=14)
                ax.set_facecolor('#1e1f22')
                ax.spines['bottom'].set_color('#2b2d31')
                ax.spines['top'].set_color('#2b2d31')
                ax.spines['right'].set_color('#2b2d31')
                ax.spines['left'].set_color('#2b2d31')
                ax.tick_params(colors='#949ba4')
                self.canvas.draw()
                return
            
            # Extract dates and costs
            dates = [d[0] for d in data]
            costs = [d[1] for d in data]
            
            # Calculate stats
            total_cost = sum(costs)
            avg_daily = total_cost / len(costs) if costs else 0
            
            # Calculate trend (comparing first half vs second half)
            trend = "→"
            trend_color = "#b5bac1"
            if len(costs) >= 2:
                mid = len(costs) // 2
                first_half_avg = sum(costs[:mid]) / mid if mid > 0 else 0
                second_half_avg = sum(costs[mid:]) / (len(costs) - mid) if len(costs) > mid else 0
                
                if second_half_avg > first_half_avg * 1.1:
                    trend = "↗️ Increasing"
                    trend_color = "#f23f42"
                elif second_half_avg < first_half_avg * 0.9:
                    trend = "↘️ Decreasing"
                    trend_color = "#23a55a"
            
            # Update summary labels
            self.total_cost_label.setText(f"Total: ${total_cost:.2f}")
            self.avg_daily_label.setText(f"Avg Daily: ${avg_daily:.2f}")
            self.trend_label.setText(f"Trend: {trend}")
            self.trend_label.setStyleSheet(f"color: {trend_color}; font-size: 14px; font-weight: 500;")
            
            # Plot chart
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            
            # Plot line
            ax.plot(dates, costs, color='#5865f2', linewidth=2, marker='o', markersize=4)
            
            # Fill area under curve
            ax.fill_between(dates, costs, alpha=0.3, color='#5865f2')
            
            # Formatting
            ax.set_facecolor('#1e1f22')
            ax.spines['bottom'].set_color('#2b2d31')
            ax.spines['top'].set_color('#2b2d31')
            ax.spines['right'].set_color('#2b2d31')
            ax.spines['left'].set_color('#2b2d31')
            ax.tick_params(colors='#949ba4')
            ax.set_xlabel('Date', color='#b5bac1')
            ax.set_ylabel('Daily Cost ($)', color='#b5bac1')
            ax.set_title('Cost Trend Over Time', color='#ffffff', fontsize=14, fontweight='bold')
            
            # Format x-axis dates
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
            self.figure.autofmt_xdate()
            
            # Grid
            ax.grid(True, alpha=0.2, color='#2b2d31')
            
            self.canvas.draw()
            
        except Exception as e:
            logger.error(f"Failed to refresh cost chart: {e}", exc_info=True)




