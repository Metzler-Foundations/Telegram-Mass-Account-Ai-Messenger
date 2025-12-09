"""
Risk Distribution Chart Widget - Visualizes account risk distribution.
"""

import logging
from typing import Dict, Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ui.theme_manager import ThemeManager

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("matplotlib not available, risk charts will be disabled")

logger = logging.getLogger(__name__)


class RiskDistributionChart(QWidget):
    """Widget displaying account risk distribution."""
    
    def __init__(self, risk_monitor=None, parent=None):
        super().__init__(parent)
        self.risk_monitor = risk_monitor
        self.setup_ui()
        
        # Auto-refresh every 30 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_chart)
        self.refresh_timer.start(30000)
        
        # Initial load
        self.refresh_chart()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Account Risk Distribution")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Chart container
        chart_colors = ThemeManager.get_chart_colors()
        chart_group = QGroupBox()
        chart_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {chart_colors["border"]};
                border-radius: 8px;
                background-color: {chart_colors["background"]};
            }}
        """)
        chart_layout = QVBoxLayout(chart_group)
        chart_layout.setContentsMargins(12, 12, 12, 12)
        
        if MATPLOTLIB_AVAILABLE:
            # Create matplotlib figure
            self.figure = Figure(figsize=(10, 6), facecolor=chart_colors["background"])
            self.canvas = FigureCanvas(self.figure)
            self.canvas.setStyleSheet(f"background-color: {chart_colors['background']};")
            chart_layout.addWidget(self.canvas)
        else:
            # Fallback message
            no_chart_label = QLabel("Risk distribution charts require matplotlib.\nInstall with: pip install matplotlib")
            no_chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_chart_label.setStyleSheet(f"color: {chart_colors['text_disabled']}; padding: 40px;")
            chart_layout.addWidget(no_chart_label)
        
        layout.addWidget(chart_group)
        
        # Summary stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        
        chart_colors = ThemeManager.get_chart_colors()
        self.total_accounts_label = QLabel("Total: 0")
        self.total_accounts_label.setStyleSheet(f"color: {chart_colors['text_secondary']}; font-size: 14px; font-weight: 500;")
        stats_layout.addWidget(self.total_accounts_label)
        
        self.avg_risk_label = QLabel("Avg Risk: 0.0")
        self.avg_risk_label.setStyleSheet(f"color: {chart_colors['text_secondary']}; font-size: 14px; font-weight: 500;")
        stats_layout.addWidget(self.avg_risk_label)
        
        self.quarantine_label = QLabel("Quarantine: 0")
        self.quarantine_label.setStyleSheet(f"color: {chart_colors['danger']}; font-size: 14px; font-weight: 500;")
        stats_layout.addWidget(self.quarantine_label)
        
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
    
    def get_risk_data(self) -> Optional[Dict]:
        """Get risk distribution data from risk monitor."""
        if not self.risk_monitor:
            return None
        
        try:
            return self.risk_monitor.get_risk_summary()
        except Exception as e:
            logger.error(f"Failed to get risk data: {e}")
            return None
    
    def refresh_chart(self):
        """Refresh the chart with latest data."""
        if not MATPLOTLIB_AVAILABLE:
            return
        
        try:
            # Get data
            data = self.get_risk_data()
            
            chart_colors = ThemeManager.get_chart_colors()
            if not data or data.get('total_accounts', 0) == 0:
                # Show empty state
                self.figure.clear()
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 'No risk data available', 
                       ha='center', va='center', 
                       transform=ax.transAxes,
                       color=chart_colors['text_disabled'], fontsize=14)
                ax.set_facecolor(chart_colors['background'])
                ax.spines['bottom'].set_color(chart_colors['border'])
                ax.spines['top'].set_color(chart_colors['border'])
                ax.spines['right'].set_color(chart_colors['border'])
                ax.spines['left'].set_color(chart_colors['border'])
                ax.tick_params(colors=chart_colors['text_disabled'])
                self.canvas.draw()
                
                # Update labels
                self.total_accounts_label.setText("Total: 0")
                self.avg_risk_label.setText("Avg Risk: 0.0")
                self.quarantine_label.setText("Quarantine: 0")
                return
            
            # Extract data
            total = data.get('total_accounts', 0)
            safe = data.get('safe', 0)
            low = data.get('low', 0)
            medium = data.get('medium', 0)
            high = data.get('high', 0)
            critical = data.get('critical', 0)
            quarantine = data.get('quarantine_candidates', 0)
            avg_risk = data.get('avg_risk_score', 0.0)
            
            # Update summary labels
            self.total_accounts_label.setText(f"Total: {total}")
            self.avg_risk_label.setText(f"Avg Risk: {avg_risk:.1f}")
            self.quarantine_label.setText(f"Quarantine: {quarantine}")
            
            chart_colors = ThemeManager.get_chart_colors()
            # Prepare chart data
            categories = ['Safe', 'Low', 'Medium', 'High', 'Critical']
            counts = [safe, low, medium, high, critical]
            # Use theme colors for risk levels
            colors = [
                chart_colors['success'],
                chart_colors['warning'],
                chart_colors['warning'],  # Medium uses warning color
                chart_colors['danger'],
                chart_colors['danger']  # Critical uses danger color
            ]
            
            # Plot chart
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            
            # Create bar chart
            bars = ax.bar(categories, counts, color=colors, alpha=0.8, edgecolor=chart_colors['border'], linewidth=1.5)
            
            # Add value labels on bars
            for bar, count in zip(bars, counts):
                if count > 0:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{int(count)}',
                           ha='center', va='bottom',
                           color=chart_colors['text'], fontweight='bold', fontsize=11)
            
            # Formatting
            ax.set_facecolor(chart_colors['background'])
            ax.spines['bottom'].set_color(chart_colors['border'])
            ax.spines['top'].set_color(chart_colors['border'])
            ax.spines['right'].set_color(chart_colors['border'])
            ax.spines['left'].set_color(chart_colors['border'])
            ax.tick_params(colors=chart_colors['text_disabled'])
            ax.set_xlabel('Risk Level', color=chart_colors['text_secondary'], fontsize=12)
            ax.set_ylabel('Number of Accounts', color=chart_colors['text_secondary'], fontsize=12)
            ax.set_title('Account Risk Distribution', color=chart_colors['text'], fontsize=14, fontweight='bold')
            
            # Grid
            ax.grid(True, alpha=0.2, color=chart_colors['grid'], axis='y')
            ax.set_axisbelow(True)
            
            # Set y-axis to start at 0
            ax.set_ylim(bottom=0)
            
            self.canvas.draw()
            
        except Exception as e:
            logger.error(f"Failed to refresh risk chart: {e}", exc_info=True)






