import json
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from app.ui.theme import (
    BG_DARK, BG_MID, BG_LIGHTER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_BLUE, ACCENT_ORANGE, SPACING_MD, SPACING_LG, SPACING_XL,
    FONT_SIZE_LG, FONT_SIZE_XL, FONT_SIZE_XXL,
)

RECENT_PROJECTS_PATH = Path.home() / ".config" / "hootie" / "recent.json"
MAX_RECENT = 8


def load_recent_projects() -> list[dict]:
    try:
        if RECENT_PROJECTS_PATH.exists():
            with open(RECENT_PROJECTS_PATH) as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_recent_project(path: str, name: str):
    recents = load_recent_projects()
    # Remove duplicate
    recents = [r for r in recents if r.get("path") != path]
    recents.insert(0, {"path": path, "name": name})
    recents = recents[:MAX_RECENT]
    RECENT_PROJECTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RECENT_PROJECTS_PATH, "w") as f:
        json.dump(recents, f, indent=2)


class RecentProjectItem(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, project_info: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._path = project_info["path"]
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # Project icon
        icon = QLabel("\U0001F4BF")
        icon.setFixedWidth(24)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        # Name and path
        info = QVBoxLayout()
        info.setSpacing(0)

        name = QLabel(project_info.get("name", "Untitled"))
        name.setStyleSheet(f"font-weight: 600; color: {TEXT_PRIMARY}; font-size: 13px;")
        info.addWidget(name)

        path_label = QLabel(self._path)
        path_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        info.addWidget(path_label)

        layout.addLayout(info, 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path)
        super().mousePressEvent(event)


class WelcomeScreen(QWidget):
    new_project_requested = pyqtSignal()
    open_project_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(60, 40, 60, 40)

        # Center content
        center = QVBoxLayout()
        center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.setSpacing(8)

        # Logo / Title
        title = QLabel("Hootie")
        title_font = QFont()
        title_font.setPointSize(36)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {ACCENT_ORANGE};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(title)

        subtitle = QLabel("DVD-Audio Creator")
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 16px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(subtitle)

        center.addSpacing(32)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        btn_row.addStretch()

        new_btn = QPushButton("  New Project  ")
        new_btn.setObjectName("primaryButton")
        new_btn.setMinimumSize(180, 48)
        new_font = QFont()
        new_font.setPointSize(14)
        new_btn.setFont(new_font)
        new_btn.clicked.connect(self.new_project_requested.emit)
        btn_row.addWidget(new_btn)

        open_btn = QPushButton("  Open Project  ")
        open_btn.setMinimumSize(180, 48)
        open_btn.setFont(new_font)
        open_btn.clicked.connect(self._open_project)
        btn_row.addWidget(open_btn)

        btn_row.addStretch()
        center.addLayout(btn_row)

        layout.addLayout(center)
        layout.addSpacing(32)

        # Recent projects
        recents = load_recent_projects()
        if recents:
            recent_header = QLabel("Recent Projects")
            recent_header.setObjectName("subheadingLabel")
            recent_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(recent_header)

            layout.addSpacing(8)

            # Center the recent list
            recent_wrapper = QHBoxLayout()
            recent_wrapper.addStretch()

            recent_list = QVBoxLayout()
            recent_list.setSpacing(6)

            for proj in recents:
                if Path(proj.get("path", "")).exists():
                    item = RecentProjectItem(proj)
                    item.setMaximumWidth(500)
                    item.clicked.connect(lambda p: self.open_project_requested.emit(p))
                    recent_list.addWidget(item)

            recent_wrapper.addLayout(recent_list)
            recent_wrapper.addStretch()
            layout.addLayout(recent_wrapper)
        else:
            empty_label = QLabel("No recent projects. Create a new one to get started!")
            empty_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty_label)

        layout.addStretch()

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", str(Path.home()),
            "Hootie Projects (*.hoot);;All Files (*)",
        )
        if path:
            self.open_project_requested.emit(path)
