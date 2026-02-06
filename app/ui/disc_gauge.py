from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox,
    QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QFont

from app.core.capacity import (
    usage_summary, DISC_CAPACITIES, format_bytes,
)
from app.ui.theme import (
    BG_DARK, BG_MID, BG_LIGHTER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    GAUGE_GREEN, GAUGE_YELLOW, GAUGE_RED, ACCENT_RED,
    SPACING_SM, SPACING_MD, SPACING_LG,
)


class CapacityBar(QWidget):
    """Custom painted capacity bar with color transitions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self.setMinimumWidth(200)
        self._percentage = 0.0
        self._over = False
        self._pulse_state = False
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._toggle_pulse)

    def set_percentage(self, pct: float):
        self._percentage = pct
        self._over = pct > 100

        if self._over and not self._pulse_timer.isActive():
            self._pulse_timer.start(500)
        elif not self._over and self._pulse_timer.isActive():
            self._pulse_timer.stop()
            self._pulse_state = False

        self.update()

    def _toggle_pulse(self):
        self._pulse_state = not self._pulse_state
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        radius = h // 2

        # Background
        painter.setBrush(QColor(BG_LIGHTER))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, w, h, radius, radius)

        # Fill
        fill_pct = min(self._percentage, 100) / 100
        fill_w = int(w * fill_pct)
        if fill_w < 1:
            painter.end()
            return

        # Color based on percentage
        if self._over:
            color = QColor(ACCENT_RED) if not self._pulse_state else QColor(GAUGE_RED)
        elif self._percentage > 85:
            color = QColor(GAUGE_RED)
        elif self._percentage > 65:
            color = QColor(GAUGE_YELLOW)
        else:
            color = QColor(GAUGE_GREEN)

        painter.setBrush(color)
        painter.drawRoundedRect(0, 0, fill_w, h, radius, radius)
        painter.end()


class DiscGauge(QWidget):
    """Horizontal capacity gauge with disc type selector."""

    disc_type_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {BG_DARK}; border-top: 1px solid {BG_LIGHTER};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(12)

        # Disc type selector
        self._disc_combo = QComboBox()
        self._disc_combo.addItems(list(DISC_CAPACITIES.keys()))
        self._disc_combo.setFixedWidth(90)
        self._disc_combo.currentTextChanged.connect(self.disc_type_changed.emit)
        layout.addWidget(self._disc_combo)

        # Capacity bar
        bar_layout = QVBoxLayout()
        bar_layout.setSpacing(2)

        self._bar = CapacityBar()
        bar_layout.addWidget(self._bar)

        layout.addLayout(bar_layout, 1)

        # Usage text
        self._usage_label = QLabel("0 MB / 4.7 GB")
        self._usage_label.setStyleSheet(f"font-size: 11px; color: {TEXT_SECONDARY};")
        self._usage_label.setMinimumWidth(130)
        self._usage_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._usage_label)

        # Percentage
        self._pct_label = QLabel("0%")
        self._pct_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {TEXT_SECONDARY};")
        self._pct_label.setFixedWidth(45)
        self._pct_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._pct_label)

    def update_usage(self, groups, disc_type: str = None):
        if disc_type:
            idx = self._disc_combo.findText(disc_type)
            if idx >= 0:
                self._disc_combo.blockSignals(True)
                self._disc_combo.setCurrentIndex(idx)
                self._disc_combo.blockSignals(False)

        dt = disc_type or self._disc_combo.currentText()
        summary = usage_summary(groups, dt)

        self._bar.set_percentage(summary["percentage"])

        used_str = format_bytes(summary["used_bytes"])
        cap_str = format_bytes(summary["capacity_bytes"])
        self._usage_label.setText(f"{used_str} / {cap_str}")

        pct = summary["percentage"]
        self._pct_label.setText(f"{pct:.0f}%")

        if summary["over_capacity"]:
            self._pct_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {ACCENT_RED};")
        elif pct > 85:
            self._pct_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {GAUGE_RED};")
        elif pct > 65:
            self._pct_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {GAUGE_YELLOW};")
        else:
            self._pct_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {TEXT_SECONDARY};")

    def current_disc_type(self) -> str:
        return self._disc_combo.currentText()
