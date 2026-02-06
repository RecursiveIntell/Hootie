#!/usr/bin/env python3
"""Hootie — DVD-Audio Creator"""

import sys
import os
import logging
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication, QStackedWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from app.ui.theme import apply_theme
from app.ui.welcome_screen import WelcomeScreen
from app.ui.dependency_check import DependencyCheckScreen
from app.ui.main_window import MainWindow
from app.models.project import Project

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("hootie")


class HootieApp:
    """Application controller managing screen navigation."""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Hootie")
        self.app.setApplicationDisplayName("Hootie — DVD-Audio Creator")
        self.app.setOrganizationName("Hootie")

        apply_theme(self.app)

        # Check if we should skip dependency check
        config_dir = Path.home() / ".config" / "hootie"
        self._deps_checked_file = config_dir / "deps_checked"

        # Stack widget to switch between screens
        self._stack = QStackedWidget()
        self._stack.setWindowTitle("Hootie — DVD-Audio Creator")
        self._stack.setMinimumSize(1100, 750)

        self._main_window = None
        self._project_file_arg = None

        # Check command-line args
        if len(sys.argv) > 1 and sys.argv[1].endswith(".hoot"):
            self._project_file_arg = sys.argv[1]

        # Decide initial screen
        if self._deps_checked_file.exists():
            self._show_welcome()
        else:
            self._show_dependency_check()

    def _show_dependency_check(self):
        dep_screen = DependencyCheckScreen(on_continue=self._on_deps_continue)
        self._stack.addWidget(dep_screen)
        self._stack.setCurrentWidget(dep_screen)
        self._stack.show()

    def _on_deps_continue(self):
        # Mark deps as checked
        self._deps_checked_file.parent.mkdir(parents=True, exist_ok=True)
        self._deps_checked_file.touch()
        self._show_welcome()

    def _show_welcome(self):
        # If opening a project file directly, skip welcome
        if self._project_file_arg:
            self._open_project(self._project_file_arg)
            return

        welcome = WelcomeScreen()
        welcome.new_project_requested.connect(self._new_project)
        welcome.open_project_requested.connect(self._open_project)
        self._stack.addWidget(welcome)
        self._stack.setCurrentWidget(welcome)
        self._stack.show()

    def _new_project(self):
        project = Project()
        project.add_group("Group 1")
        self._show_main_window(project)

    def _open_project(self, path: str):
        try:
            project = Project.load(path)
            self._show_main_window(project)
        except Exception as e:
            log.error(f"Failed to load project: {e}")
            # Fall back to new project
            self._new_project()

    def _show_main_window(self, project: Project):
        self._stack.hide()
        self._main_window = MainWindow(project)
        self._main_window.show()

    def run(self) -> int:
        return self.app.exec()


def main():
    app = HootieApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
