from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QFont

from app.ui.theme import (
    ACCENT_BLUE, ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED,
    BG_MID, TEXT_PRIMARY,
)

TOAST_COLORS = {
    "info": ACCENT_BLUE,
    "success": ACCENT_GREEN,
    "warning": ACCENT_YELLOW,
    "error": ACCENT_RED,
}

TOAST_TIMEOUT = 4000  # ms


class ToastNotification(QWidget):
    """Non-modal notification that slides in and auto-dismisses."""

    _active_toasts: list = []

    def __init__(self, message: str, level: str = "info", parent=None, timeout: int = TOAST_TIMEOUT):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        color = TOAST_COLORS.get(level, ACCENT_BLUE)

        self.setStyleSheet(
            f"QWidget {{ background-color: {BG_MID}; "
            f"border: 1px solid {color}; "
            f"border-left: 4px solid {color}; "
            f"border-radius: 8px; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)

        label = QLabel(message)
        label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; border: none;")
        label.setWordWrap(True)
        layout.addWidget(label)

        self.setMinimumWidth(300)
        self.setMaximumWidth(500)
        self.adjustSize()

        # Opacity animation
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0)

        # Fade in
        self._fade_in = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0)
        self._fade_in.setEndValue(1)

        # Fade out
        self._fade_out = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_out.setDuration(300)
        self._fade_out.setStartValue(1)
        self._fade_out.setEndValue(0)
        self._fade_out.finished.connect(self._on_fade_out_done)

        # Auto-dismiss timer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dismiss)
        self._timer.setInterval(timeout)

    def show_toast(self):
        ToastNotification._active_toasts.append(self)
        self._position_toast()
        self.show()
        self._fade_in.start()
        self._timer.start()

    def _position_toast(self):
        if self.parent():
            parent = self.parent()
            x = parent.width() - self.width() - 20
            # Stack below existing toasts
            index = len(ToastNotification._active_toasts) - 1
            y = 20 + index * (self.height() + 8)
            self.move(parent.mapToGlobal(QPoint(x, y)))
        else:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = geo.right() - self.width() - 20
                index = len(ToastNotification._active_toasts) - 1
                y = geo.top() + 20 + index * (self.height() + 8)
                self.move(x, y)

    def _dismiss(self):
        self._fade_out.start()

    def _on_fade_out_done(self):
        if self in ToastNotification._active_toasts:
            ToastNotification._active_toasts.remove(self)
        self.close()


def show_toast(message: str, level: str = "info", parent=None, timeout: int = TOAST_TIMEOUT):
    """Convenience function to show a toast notification."""
    toast = ToastNotification(message, level, parent, timeout)
    toast.show_toast()
    return toast
