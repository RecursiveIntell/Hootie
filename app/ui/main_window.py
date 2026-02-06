import os
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QToolBar, QPushButton, QFileDialog, QMenuBar,
    QStatusBar, QFrame, QScrollArea, QSizePolicy, QMessageBox,
    QApplication,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QAction, QFont, QKeySequence, QDragEnterEvent, QDropEvent

from app.models.project import Project, MAX_GROUPS, MAX_TRACKS_PER_GROUP
from app.models.track import Track
from app.models.group import Group
from app.core.audio_probe import probe_file, probe_files, is_supported, SUPPORTED_EXTENSIONS
from app.ui.group_panel import GroupPanel, ALL_TRACKS_ID
from app.ui.track_table import TrackTable
from app.ui.disc_gauge import DiscGauge
from app.ui.theme import (
    BG_DARKEST, BG_DARK, BG_MID, BG_LIGHT, BG_LIGHTER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT_BLUE, ACCENT_ORANGE,
    GROUP_COLORS, SPACING_SM, SPACING_MD, SPACING_LG,
)

log = logging.getLogger("hootie.main_window")


class ProbeWorker(QThread):
    """Background thread for probing audio files."""
    progress = pyqtSignal(int, int)  # current, total
    track_ready = pyqtSignal(object)  # Track
    finished = pyqtSignal(list)  # list of Tracks
    error = pyqtSignal(str)

    def __init__(self, paths: list[str]):
        super().__init__()
        self._paths = paths

    def run(self):
        tracks = []
        total = len(self._paths)
        for i, path in enumerate(self._paths):
            try:
                if is_supported(path):
                    track = probe_file(path)
                    tracks.append(track)
                    self.track_ready.emit(track)
            except Exception as e:
                log.warning(f"Failed to probe {path}: {e}")
            self.progress.emit(i + 1, total)
        self.finished.emit(tracks)


class TrackDetailsPanel(QScrollArea):
    """Right panel showing selected track details."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Album art placeholder
        self._art_label = QLabel()
        self._art_label.setFixedSize(200, 200)
        self._art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._art_label.setStyleSheet(
            f"background-color: {BG_MID}; border: 1px solid {BG_LIGHTER}; "
            f"border-radius: 8px; color: {TEXT_MUTED}; font-size: 36px;"
        )
        self._art_label.setText("\u266B")
        self._layout.addWidget(self._art_label, 0, Qt.AlignmentFlag.AlignHCenter)

        # Title
        self._title_label = QLabel("No track selected")
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {TEXT_PRIMARY};")
        self._layout.addWidget(self._title_label)

        self._artist_label = QLabel()
        self._artist_label.setWordWrap(True)
        self._artist_label.setStyleSheet(f"font-size: 13px; color: {TEXT_SECONDARY};")
        self._layout.addWidget(self._artist_label)

        self._album_label = QLabel()
        self._album_label.setWordWrap(True)
        self._album_label.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED};")
        self._layout.addWidget(self._album_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BG_LIGHTER};")
        self._layout.addWidget(sep)

        # Technical details
        self._details_label = QLabel()
        self._details_label.setWordWrap(True)
        self._details_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; line-height: 1.6;")
        self._layout.addWidget(self._details_label)

        # File path
        self._path_label = QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._layout.addWidget(self._path_label)

        self._layout.addStretch()
        self.setWidget(self._container)

        self.clear()

    def show_track(self, track: Track):
        if track is None:
            self.clear()
            return

        self._title_label.setText(track.display_title)
        self._artist_label.setText(track.artist or "Unknown Artist")
        self._album_label.setText(track.album or "")
        self._album_label.setVisible(bool(track.album))

        # Technical details
        lines = []
        lines.append(f"<b>Codec:</b> {track.codec.upper()}")
        lines.append(f"<b>Sample Rate:</b> {track.formatted_sample_rate()}")
        if track.bit_depth:
            lines.append(f"<b>Bit Depth:</b> {track.bit_depth}-bit")
        lines.append(f"<b>Channels:</b> {track.channels}")
        lines.append(f"<b>Duration:</b> {track.formatted_duration()}")
        lines.append(f"<b>File Size:</b> {track.formatted_size()}")
        if track.needs_conversion:
            lines.append(f"<span style='color: {ACCENT_ORANGE};'><b>Needs conversion to WAV</b></span>")

        self._details_label.setText("<br>".join(lines))
        self._path_label.setText(track.file_path)

    def clear(self):
        self._title_label.setText("No track selected")
        self._artist_label.setText("")
        self._album_label.setText("")
        self._details_label.setText("")
        self._path_label.setText("")
        self._art_label.setText("\u266B")


class MainWindow(QMainWindow):
    """Main application window with three-panel layout."""

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self._project = project
        self._current_group_id: str = ALL_TRACKS_ID
        self._probe_worker: Optional[ProbeWorker] = None

        self.setWindowTitle(self._window_title())
        self.setMinimumSize(1100, 750)
        self.resize(1280, 800)
        self.setAcceptDrops(True)

        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_shortcuts()
        self._refresh()

    def _window_title(self) -> str:
        name = self._project.name
        mod = " *" if self._project.is_modified else ""
        return f"{name}{mod} \u2014 Hootie"

    # ── Menu Bar ──

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        # File
        file_menu = menu_bar.addMenu("File")

        new_act = QAction("New Project", self)
        new_act.setShortcut(QKeySequence.StandardKey.New)
        new_act.triggered.connect(self._new_project)
        file_menu.addAction(new_act)

        open_act = QAction("Open Project...", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._open_project)
        file_menu.addAction(open_act)

        file_menu.addSeparator()

        save_act = QAction("Save", self)
        save_act.setShortcut(QKeySequence.StandardKey.Save)
        save_act.triggered.connect(self._save_project)
        file_menu.addAction(save_act)

        save_as_act = QAction("Save As...", self)
        save_as_act.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_act.triggered.connect(self._save_project_as)
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()

        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        # Edit
        edit_menu = menu_bar.addMenu("Edit")

        add_files_act = QAction("Add Files...", self)
        add_files_act.setShortcut(QKeySequence("Ctrl+I"))
        add_files_act.triggered.connect(self._add_files)
        edit_menu.addAction(add_files_act)

        add_folder_act = QAction("Add Folder...", self)
        add_folder_act.setShortcut(QKeySequence("Ctrl+Shift+I"))
        add_folder_act.triggered.connect(self._add_folder)
        edit_menu.addAction(add_folder_act)

        edit_menu.addSeparator()

        add_group_act = QAction("Add Group", self)
        add_group_act.setShortcut(QKeySequence("Ctrl+G"))
        add_group_act.triggered.connect(self._add_group)
        edit_menu.addAction(add_group_act)

        edit_menu.addSeparator()

        remove_act = QAction("Remove Selected Tracks", self)
        remove_act.setShortcut(QKeySequence.StandardKey.Delete)
        remove_act.triggered.connect(self._remove_selected_tracks)
        edit_menu.addAction(remove_act)

        select_all_act = QAction("Select All", self)
        select_all_act.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_act.triggered.connect(lambda: None)  # handled by table
        edit_menu.addAction(select_all_act)

        # Tools
        tools_menu = menu_bar.addMenu("Tools")

        build_act = QAction("Build DVD-Audio...", self)
        build_act.setShortcut(QKeySequence("Ctrl+B"))
        build_act.triggered.connect(self._build)
        tools_menu.addAction(build_act)

        tools_menu.addSeparator()

        settings_act = QAction("Settings...", self)
        settings_act.setShortcut(QKeySequence("Ctrl+,"))
        settings_act.triggered.connect(self._show_settings)
        tools_menu.addAction(settings_act)

        deps_act = QAction("Check Dependencies...", self)
        deps_act.triggered.connect(self._show_deps)
        tools_menu.addAction(deps_act)

        # Help
        help_menu = menu_bar.addMenu("Help")

        about_act = QAction("About Hootie", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    # ── Toolbar ──

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)

        new_btn = QAction("New", self)
        new_btn.setToolTip("New Project (Ctrl+N)")
        new_btn.triggered.connect(self._new_project)
        toolbar.addAction(new_btn)

        open_btn = QAction("Open", self)
        open_btn.setToolTip("Open Project (Ctrl+O)")
        open_btn.triggered.connect(self._open_project)
        toolbar.addAction(open_btn)

        save_btn = QAction("Save", self)
        save_btn.setToolTip("Save Project (Ctrl+S)")
        save_btn.triggered.connect(self._save_project)
        toolbar.addAction(save_btn)

        toolbar.addSeparator()

        add_files_btn = QAction("Add Files", self)
        add_files_btn.setToolTip("Add Audio Files (Ctrl+I)")
        add_files_btn.triggered.connect(self._add_files)
        toolbar.addAction(add_files_btn)

        add_folder_btn = QAction("Add Folder", self)
        add_folder_btn.setToolTip("Add Folder (Ctrl+Shift+I)")
        add_folder_btn.triggered.connect(self._add_folder)
        toolbar.addAction(add_folder_btn)

        toolbar.addSeparator()

        add_group_btn = QAction("Add Group", self)
        add_group_btn.setToolTip("Add Group (Ctrl+G)")
        add_group_btn.triggered.connect(self._add_group)
        toolbar.addAction(add_group_btn)

        toolbar.addSeparator()

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        build_btn = QAction("Build", self)
        build_btn.setToolTip("Build DVD-Audio (Ctrl+B)")
        build_btn.triggered.connect(self._build)
        toolbar.addAction(build_btn)

    # ── Central UI ──

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Three-panel splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Left: Group panel
        self._group_panel = GroupPanel()
        self._group_panel.group_selected.connect(self._on_group_selected)
        self._group_panel.group_added.connect(self._add_group)
        self._group_panel.group_renamed.connect(self._rename_group)
        self._group_panel.group_deleted.connect(self._delete_group)
        self._group_panel.group_color_changed.connect(self._change_group_color)
        splitter.addWidget(self._group_panel)

        # Center: Track table
        self._track_table = TrackTable()
        self._track_table.files_dropped.connect(self._on_files_dropped)
        self._track_table.track_selected.connect(self._on_track_selected)
        self._track_table.tracks_removed.connect(self._remove_tracks)
        self._track_table.tracks_moved_to_group.connect(self._move_tracks_to_group)
        splitter.addWidget(self._track_table)

        # Right: Track details
        self._details_panel = TrackDetailsPanel()
        splitter.addWidget(self._details_panel)

        # Splitter proportions
        splitter.setSizes([220, 600, 260])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        main_layout.addWidget(splitter, 1)

        # Bottom: Disc gauge
        self._disc_gauge = DiscGauge()
        self._disc_gauge.disc_type_changed.connect(self._on_disc_type_changed)
        main_layout.addWidget(self._disc_gauge)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    def _setup_shortcuts(self):
        pass  # shortcuts are set up via menu actions

    # ── Refresh ──

    def _refresh(self):
        """Refresh all UI from project state."""
        self.setWindowTitle(self._window_title())
        self._group_panel.set_groups(self._project.groups, self._project.total_tracks())
        self._track_table.set_groups_for_context_menu(self._project.groups)
        self._refresh_track_table()
        self._disc_gauge.update_usage(self._project.groups, self._project.disc_type)
        self._update_status()

    def _refresh_track_table(self):
        """Refresh the track table based on current group selection."""
        if self._current_group_id == ALL_TRACKS_ID:
            self._track_table.set_tracks(self._project.all_tracks())
        else:
            group = self._project.get_group(self._current_group_id)
            if group:
                self._track_table.set_tracks(group.tracks)
            else:
                self._track_table.set_tracks([])

    def _update_status(self):
        total = self._project.total_tracks()
        groups = len(self._project.groups)
        self._status_bar.showMessage(
            f"{total} track{'s' if total != 1 else ''} in {groups} group{'s' if groups != 1 else ''}"
        )

    # ── Group actions ──

    def _on_group_selected(self, group_id: str):
        self._current_group_id = group_id
        self._refresh_track_table()
        self._details_panel.clear()

    def _add_group(self):
        if len(self._project.groups) >= MAX_GROUPS:
            self._show_toast(f"Maximum {MAX_GROUPS} groups allowed", "warning")
            return
        color_idx = len(self._project.groups) % len(GROUP_COLORS)
        group = self._project.add_group(color=GROUP_COLORS[color_idx])
        if group:
            self._refresh()
            self._group_panel.select_group(group.id)

    def _rename_group(self, group_id: str, new_name: str):
        group = self._project.get_group(group_id)
        if group:
            group.name = new_name
            self._project.mark_modified()
            self._refresh()

    def _delete_group(self, group_id: str):
        group = self._project.get_group(group_id)
        if not group:
            return
        if group.tracks:
            reply = QMessageBox.question(
                self, "Delete Group",
                f"Delete group \"{group.name}\" and its {group.track_count} tracks?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._project.remove_group(group_id)
        self._current_group_id = ALL_TRACKS_ID
        self._refresh()

    def _change_group_color(self, group_id: str, color: str):
        group = self._project.get_group(group_id)
        if group:
            group.color_tag = color
            self._project.mark_modified()
            self._refresh()

    # ── File import ──

    def _add_files(self):
        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Audio Files", str(Path.home()),
            f"Audio Files ({exts});;All Files (*)",
        )
        if paths:
            self._import_files(paths)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Add Folder", str(Path.home()),
        )
        if folder:
            paths = []
            for root, dirs, files in os.walk(folder):
                for f in sorted(files):
                    fp = os.path.join(root, f)
                    if is_supported(fp):
                        paths.append(fp)
            if paths:
                self._import_files(paths)
            else:
                self._show_toast("No supported audio files found in folder", "warning")

    def _on_files_dropped(self, paths: list[str]):
        # Expand directories
        file_paths = []
        for p in paths:
            if os.path.isdir(p):
                for root, dirs, files in os.walk(p):
                    for f in sorted(files):
                        fp = os.path.join(root, f)
                        if is_supported(fp):
                            file_paths.append(fp)
            elif is_supported(p):
                file_paths.append(p)
        if file_paths:
            self._import_files(file_paths)

    def _import_files(self, paths: list[str]):
        """Import audio files, probing them in a background thread."""
        target_group = self._get_target_group()
        if not target_group:
            self._show_toast("No group available. Add a group first.", "warning")
            return

        if len(target_group.tracks) + len(paths) > MAX_TRACKS_PER_GROUP:
            self._show_toast(
                f"Too many tracks. Max {MAX_TRACKS_PER_GROUP} per group.", "warning"
            )
            return

        self._status_bar.showMessage(f"Importing {len(paths)} file(s)...")

        self._probe_worker = ProbeWorker(paths)
        self._probe_worker.finished.connect(
            lambda tracks: self._on_probe_finished(tracks, target_group.id)
        )
        self._probe_worker.start()

    def _on_probe_finished(self, tracks: list[Track], group_id: str):
        if not tracks:
            self._status_bar.showMessage("No valid audio files found")
            return

        self._project.add_tracks_to_group(group_id, tracks)
        self._refresh()
        self._status_bar.showMessage(f"Added {len(tracks)} track(s)")
        self._probe_worker = None

    def _get_target_group(self) -> Optional[Group]:
        """Get the group to add tracks to."""
        if self._current_group_id != ALL_TRACKS_ID:
            group = self._project.get_group(self._current_group_id)
            if group:
                return group
        # Fall back to first group
        if self._project.groups:
            return self._project.groups[0]
        # Auto-create first group
        return self._project.add_group("Group 1")

    # ── Track actions ──

    def _on_track_selected(self, track):
        self._details_panel.show_track(track)

    def _remove_tracks(self, track_ids: list[str]):
        for group in self._project.groups:
            group.tracks = [t for t in group.tracks if t.id not in track_ids]
        self._project.mark_modified()
        self._details_panel.clear()
        self._refresh()

    def _remove_selected_tracks(self):
        ids = self._track_table.get_selected_track_ids()
        if ids:
            self._remove_tracks(ids)

    def _move_tracks_to_group(self, track_ids: list[str], target_group_id: str):
        # Find and move each track
        for tid in track_ids:
            for group in self._project.groups:
                for i, t in enumerate(group.tracks):
                    if t.id == tid and group.id != target_group_id:
                        self._project.move_track(tid, group.id, target_group_id)
                        break
        self._refresh()

    # ── Project actions ──

    def _new_project(self):
        if self._project.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Save current project before creating a new one?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save_project()
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self._project = Project()
        self._project.add_group("Group 1")
        self._current_group_id = ALL_TRACKS_ID
        self._refresh()

    def _open_project(self):
        if self._project.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Save current project before opening another?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save_project()
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", str(Path.home()),
            "Hootie Projects (*.hoot);;All Files (*)",
        )
        if path:
            try:
                self._project = Project.load(path)
                self._current_group_id = ALL_TRACKS_ID
                self._refresh()
                from app.ui.welcome_screen import save_recent_project
                save_recent_project(path, self._project.name)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")

    def _save_project(self):
        if self._project.file_path:
            try:
                self._project.save()
                self._refresh()
                self._status_bar.showMessage("Project saved", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
        else:
            self._save_project_as()

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", str(Path.home() / f"{self._project.name}.hoot"),
            "Hootie Projects (*.hoot)",
        )
        if path:
            try:
                self._project.save(path)
                self._refresh()
                self._status_bar.showMessage("Project saved", 3000)
                from app.ui.welcome_screen import save_recent_project
                save_recent_project(path, self._project.name)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    # ── Disc type ──

    def _on_disc_type_changed(self, disc_type: str):
        self._project.disc_type = disc_type
        self._project.mark_modified()
        self._disc_gauge.update_usage(self._project.groups, disc_type)
        self.setWindowTitle(self._window_title())

    # ── Build / Burn ──

    def _build(self):
        if not self._project.groups or self._project.total_tracks() == 0:
            QMessageBox.information(self, "No Tracks", "Add some tracks before building.")
            return
        try:
            from app.ui.burn_wizard import BurnWizard
            wizard = BurnWizard(self._project, self)
            wizard.exec()
        except ImportError:
            QMessageBox.information(
                self, "Build",
                "Build wizard not yet available. Coming soon!",
            )

    # ── Settings / Deps / About ──

    def _show_settings(self):
        try:
            from app.ui.settings_dialog import SettingsDialog
            dialog = SettingsDialog(self)
            dialog.exec()
        except ImportError:
            pass

    def _show_deps(self):
        from app.ui.dependency_check import DependencyCheckScreen
        from PyQt6.QtWidgets import QDialog, QVBoxLayout
        dialog = QDialog(self)
        dialog.setWindowTitle("System Check")
        dialog.setMinimumSize(600, 500)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        dep_screen = DependencyCheckScreen(on_continue=dialog.accept)
        layout.addWidget(dep_screen)
        dialog.exec()

    def _show_about(self):
        QMessageBox.about(
            self, "About Hootie",
            "<h2>Hootie</h2>"
            "<p>DVD-Audio Creator</p>"
            "<p>Create and burn DVD-Audio discs from your music library.</p>"
            "<p>Wraps <code>dvda-author</code> for DVD-Audio authoring.</p>",
        )

    # ── Toast (simple status bar message for now) ──

    def _show_toast(self, message: str, level: str = "info"):
        self._status_bar.showMessage(message, 5000)

    # ── Drag and drop ──

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
        if paths:
            self._on_files_dropped(paths)
            event.acceptProposedAction()

    # ── Close event ──

    def closeEvent(self, event):
        if self._project.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Save project before quitting?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save_project()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
