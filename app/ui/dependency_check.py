import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from app.ui.theme import (
    BG_DARK, BG_MID, BG_LIGHTER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_GREEN, ACCENT_RED, ACCENT_YELLOW, ACCENT_BLUE,
    FONT_SIZE_SM, FONT_SIZE_LG, FONT_SIZE_XL, SPACING_MD, SPACING_LG, SPACING_XL,
)


@dataclass
class Dependency:
    name: str
    command: str
    description: str
    install_hint: str
    required: bool = True
    found: bool = False
    version: str = ""


def check_dependency(dep: Dependency) -> Dependency:
    """Check if a dependency is available on PATH."""
    path = shutil.which(dep.command)
    if path:
        dep.found = True
        try:
            result = subprocess.run(
                [dep.command, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            output = result.stdout.strip() or result.stderr.strip()
            # Take first line, truncate
            if output:
                dep.version = output.split("\n")[0][:80]
        except (subprocess.TimeoutExpired, OSError):
            dep.version = "installed"
    else:
        dep.found = False
    return dep


def get_all_dependencies() -> list[Dependency]:
    deps = [
        Dependency(
            name="dvda-author",
            command="dvda-author",
            description="Creates DVD-Audio disc structures from audio files",
            install_hint="Build from source at dvda-author/ directory",
            required=True,
        ),
        Dependency(
            name="FFmpeg",
            command="ffmpeg",
            description="Audio/video transcoding and processing",
            install_hint="sudo dnf install ffmpeg",
            required=True,
        ),
        Dependency(
            name="FFprobe",
            command="ffprobe",
            description="Audio file metadata extraction",
            install_hint="Included with FFmpeg",
            required=True,
        ),
        Dependency(
            name="SoX",
            command="sox",
            description="High-quality audio format conversion",
            install_hint="sudo dnf install sox",
            required=False,
        ),
        Dependency(
            name="growisofs",
            command="growisofs",
            description="DVD burning (DVD+R/RW)",
            install_hint="sudo dnf install dvd+rw-tools",
            required=False,
        ),
        Dependency(
            name="cdrecord / wodim",
            command="wodim",
            description="CD/DVD burning (DVD-R/RW)",
            install_hint="sudo dnf install wodim",
            required=False,
        ),
    ]
    return [check_dependency(d) for d in deps]


class DependencyCard(QFrame):
    def __init__(self, dep: Dependency, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Status icon
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        icon_label.setFont(font)

        if dep.found:
            icon_label.setText("\u2713")
            icon_label.setStyleSheet(f"color: {ACCENT_GREEN}; font-weight: bold;")
        elif dep.required:
            icon_label.setText("\u2717")
            icon_label.setStyleSheet(f"color: {ACCENT_RED}; font-weight: bold;")
        else:
            icon_label.setText("\u2014")
            icon_label.setStyleSheet(f"color: {ACCENT_YELLOW}; font-weight: bold;")
        layout.addWidget(icon_label)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_row = QHBoxLayout()
        name_label = QLabel(dep.name)
        name_label.setStyleSheet(f"font-weight: 600; font-size: 14px; color: {TEXT_PRIMARY};")
        name_row.addWidget(name_label)

        if dep.required:
            req_label = QLabel("Required")
            req_label.setStyleSheet(
                f"font-size: 10px; color: {ACCENT_RED}; "
                f"background-color: {ACCENT_RED}22; "
                f"border-radius: 3px; padding: 1px 6px;"
            )
            name_row.addWidget(req_label)
        else:
            opt_label = QLabel("Optional")
            opt_label.setStyleSheet(
                f"font-size: 10px; color: {TEXT_MUTED}; "
                f"background-color: {BG_LIGHTER}; "
                f"border-radius: 3px; padding: 1px 6px;"
            )
            name_row.addWidget(opt_label)
        name_row.addStretch()
        info_layout.addLayout(name_row)

        desc = dep.version if dep.found else dep.description
        desc_label = QLabel(desc)
        desc_label.setStyleSheet(f"font-size: 11px; color: {TEXT_SECONDARY};")
        info_layout.addWidget(desc_label)

        if not dep.found:
            hint_label = QLabel(dep.install_hint)
            hint_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; font-style: italic;")
            info_layout.addWidget(hint_label)

        layout.addLayout(info_layout, 1)


class DependencyCheckScreen(QWidget):
    def __init__(self, on_continue=None, parent=None):
        super().__init__(parent)
        self._on_continue = on_continue
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(SPACING_XL)
        layout.setContentsMargins(60, 40, 60, 40)

        # Title
        title = QLabel("System Check")
        title.setObjectName("headingLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Checking for required tools and dependencies")
        subtitle.setObjectName("secondaryLabel")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumWidth(600)
        scroll.setMinimumWidth(500)

        card_container = QWidget()
        self._card_layout = QVBoxLayout(card_container)
        self._card_layout.setSpacing(8)
        self._card_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(card_container)

        # Center the scroll area
        scroll_wrapper = QHBoxLayout()
        scroll_wrapper.addStretch()
        scroll_wrapper.addWidget(scroll)
        scroll_wrapper.addStretch()
        layout.addLayout(scroll_wrapper, 1)

        # Summary and buttons
        self._summary_label = QLabel()
        self._summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._summary_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        self._recheck_btn = QPushButton("Re-check")
        self._recheck_btn.clicked.connect(self._recheck)
        btn_row.addWidget(self._recheck_btn)

        self._continue_btn = QPushButton("Continue")
        self._continue_btn.setObjectName("primaryButton")
        self._continue_btn.clicked.connect(self._on_continue_clicked)
        btn_row.addWidget(self._continue_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._recheck()

    def _recheck(self):
        # Clear existing cards
        while self._card_layout.count():
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._deps = get_all_dependencies()
        for dep in self._deps:
            self._card_layout.addWidget(DependencyCard(dep))
        self._card_layout.addStretch()

        # Summary
        found = sum(1 for d in self._deps if d.found)
        total = len(self._deps)
        required_missing = [d for d in self._deps if d.required and not d.found]

        if not required_missing:
            self._summary_label.setText(
                f"<span style='color: {ACCENT_GREEN};'>{found}/{total} tools found. Ready to go!</span>"
            )
            self._continue_btn.setEnabled(True)
        else:
            names = ", ".join(d.name for d in required_missing)
            self._summary_label.setText(
                f"<span style='color: {ACCENT_YELLOW};'>"
                f"{found}/{total} tools found. Missing required: {names}"
                f"</span>"
            )
            # Allow continuing even with missing deps — they'll fail gracefully later
            self._continue_btn.setEnabled(True)

    def _on_continue_clicked(self):
        if self._on_continue:
            self._on_continue()
