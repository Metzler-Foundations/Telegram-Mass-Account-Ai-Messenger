#!/usr/bin/env python3
"""Toast notifications for user feedback."""

from PyQt6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PyQt6.QtCore import QTimer, QPropertyAnimation, Qt


class ToastNotification(QLabel):
    """Toast notification widget."""
    
    def __init__(self, parent, message: str, duration: int = 3000, variant: str = "info"):
        super().__init__(message, parent)
        
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("toast")
        self.setProperty("variant", variant)
        self.setStyleSheet("")  # Use global QSS
        
        self.adjustSize()
        
        # Center on parent
        parent_rect = parent.geometry()
        x = (parent_rect.width() - self.width()) // 2
        y = parent_rect.height() - 100
        self.move(x, y)
        
        # Fade out animation
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(500)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        
        # Auto-hide timer
        QTimer.singleShot(duration, self.fade_out)
    
    def fade_out(self):
        """Fade out and delete."""
        self.fade_animation.finished.connect(self.deleteLater)
        self.fade_animation.start()


def show_toast(parent, message: str, duration: int = 3000, variant: str = "info"):
    """Show toast notification."""
    toast = ToastNotification(parent, message, duration, variant)
    toast.show()
    return toast





