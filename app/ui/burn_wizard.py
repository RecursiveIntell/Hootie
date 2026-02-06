import tempfile
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QStackedWidget, QTextEdit, QComboBox,
    QFileDialog, QWidget, QSizePolicy, QCheckBox, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCursor

from app.models.project import Project
from app.core.capacity import usage_summary, format_bytes
from app.core.iso_builder import BuildPipeline, BuildStage
from app.core.disc_burner import detect_drives, BurnWorker, get_burn_tool
from app.ui.theme import (
    BG_DARKEST, BG_DARK, BG_MID, BG_LIGHT, BG_LIGHTER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED, ACCENT_BLUE, ACCENT_ORANGE,
    SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
)


class PreflightCard(QFrame):
    """A check item in the preflight checklist."""

    def __init__(self, label: str, ok: bool, detail: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        icon = QLabel("\u2713" if ok else "\u2717")
        icon.setStyleSheet(
            f"color: {ACCENT_GREEN if ok else ACCENT_RED}; font-weight: bold; font-size: 14px;"
        )
        icon.setFixedWidth(20)
        layout.addWidget(icon)

        text = QLabel(label)
        text.setStyleSheet(f"font-size: 13px; color: {TEXT_PRIMARY};")
        layout.addWidget(text, 1)

        if detail:
            det = QLabel(detail)
            det.setStyleSheet(f"font-size: 11px; color: {TEXT_SECONDARY};")
            layout.addWidget(det)


class BurnWizard(QDialog):
    """Multi-stage build and burn wizard."""

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self._project = project
        self._pipeline: Optional[BuildPipeline] = None
        self._burn_worker: Optional[BurnWorker] = None
        self._iso_path: Optional[str] = None
        self._output_dir: Optional[str] = None

        self.setWindowTitle("Build DVD-Audio")
        self.setMinimumSize(650, 500)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._setup_preflight_page()
        self._setup_progress_page()
        self._setup_complete_page()
        self._setup_burn_page()

        self._stack.setCurrentIndex(0)

    # ── Page 0: Preflight ──

    def _setup_preflight_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Pre-flight Check")
        title.setObjectName("headingLabel")
        layout.addWidget(title)

        subtitle = QLabel("Review your project before building")
        subtitle.setObjectName("secondaryLabel")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Summary card
        summary = usage_summary(self._project.groups, self._project.disc_type)
        total_tracks = self._project.total_tracks()
        total_groups = len(self._project.groups)

        summary_frame = QFrame()
        summary_frame.setObjectName("card")
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(16, 12, 16, 12)

        for label, value in [
            ("Groups", str(total_groups)),
            ("Tracks", str(total_tracks)),
            ("Size", format_bytes(summary["used_bytes"])),
            ("Disc", self._project.disc_type),
        ]:
            col = QVBoxLayout()
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {ACCENT_ORANGE};")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(val_lbl)
            key_lbl = QLabel(label)
            key_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
            key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(key_lbl)
            summary_layout.addLayout(col)

        layout.addWidget(summary_frame)

        # Checks
        self._checks_layout = QVBoxLayout()
        self._checks_layout.setSpacing(6)

        checks = []

        # Track count
        checks.append(PreflightCard(
            "Tracks added", total_tracks > 0,
            f"{total_tracks} track(s)",
        ))

        # Capacity
        checks.append(PreflightCard(
            "Disc capacity", not summary["over_capacity"],
            f"{summary['percentage']:.0f}% used",
        ))

        # Format consistency per group
        all_consistent = True
        for group in self._project.groups:
            mismatched = group.find_mismatched_tracks()
            if mismatched:
                all_consistent = False
                checks.append(PreflightCard(
                    f"Group \"{group.name}\" format mismatch", False,
                    f"{len(mismatched)} track(s) differ",
                ))

        if all_consistent:
            checks.append(PreflightCard("Format consistency", True, "All groups consistent"))

        # Conversion needed
        needs_conv = [t for t in self._project.all_tracks() if t.needs_conversion]
        if needs_conv:
            checks.append(PreflightCard(
                "Files needing conversion", True,
                f"{len(needs_conv)} file(s) will be converted to WAV",
            ))

        for card in checks:
            self._checks_layout.addWidget(card)
        self._checks_layout.addStretch()

        layout.addLayout(self._checks_layout, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._build_iso_check = QCheckBox("Create ISO file")
        self._build_iso_check.setChecked(True)
        btn_layout.addWidget(self._build_iso_check)

        build_btn = QPushButton("Build DVD-Audio")
        build_btn.setObjectName("primaryButton")
        build_btn.clicked.connect(self._start_build)
        btn_layout.addWidget(build_btn)

        layout.addLayout(btn_layout)
        self._stack.addWidget(page)

    # ── Page 1: Build Progress ──

    def _setup_progress_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        self._progress_title = QLabel("Building...")
        self._progress_title.setObjectName("headingLabel")
        layout.addWidget(self._progress_title)

        self._progress_stage = QLabel("Preparing...")
        self._progress_stage.setStyleSheet(f"font-size: 14px; color: {TEXT_SECONDARY};")
        layout.addWidget(self._progress_stage)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(0)  # indeterminate by default
        self._progress_bar.setFixedHeight(8)
        layout.addWidget(self._progress_bar)

        self._progress_detail = QLabel("")
        self._progress_detail.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED};")
        layout.addWidget(self._progress_detail)

        # Log output (collapsible)
        self._log_toggle = QPushButton("Show Log")
        self._log_toggle.setFlat(True)
        self._log_toggle.setStyleSheet(f"color: {ACCENT_BLUE}; font-size: 12px; text-align: left;")
        self._log_toggle.clicked.connect(self._toggle_log)
        layout.addWidget(self._log_toggle)

        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)
        self._log_output.setStyleSheet(
            f"background-color: {BG_DARKEST}; border: 1px solid {BG_LIGHTER}; "
            f"border-radius: 6px; font-family: monospace; font-size: 11px; "
            f"color: {TEXT_SECONDARY}; padding: 8px;"
        )
        self._log_output.setMaximumHeight(200)
        self._log_output.hide()
        layout.addWidget(self._log_output)

        layout.addStretch()

        # Cancel button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel_build)
        btn_layout.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout)

        self._stack.addWidget(page)

    # ── Page 2: Complete ──

    def _setup_complete_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._complete_icon = QLabel("\u2713")
        self._complete_icon.setStyleSheet(f"font-size: 48px; color: {ACCENT_GREEN};")
        self._complete_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._complete_icon)

        self._complete_title = QLabel("Build Complete!")
        self._complete_title.setObjectName("headingLabel")
        self._complete_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._complete_title)

        self._complete_detail = QLabel("")
        self._complete_detail.setObjectName("secondaryLabel")
        self._complete_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._complete_detail.setWordWrap(True)
        layout.addWidget(self._complete_detail)

        layout.addSpacing(16)

        # Error details (hidden by default)
        self._error_output = QTextEdit()
        self._error_output.setReadOnly(True)
        self._error_output.setStyleSheet(
            f"background-color: {BG_DARKEST}; border: 1px solid {ACCENT_RED}; "
            f"border-radius: 6px; font-family: monospace; font-size: 11px; "
            f"color: {TEXT_SECONDARY}; padding: 8px;"
        )
        self._error_output.setMaximumHeight(150)
        self._error_output.hide()
        layout.addWidget(self._error_output)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._burn_btn = QPushButton("Burn to Disc...")
        self._burn_btn.setObjectName("accentButton")
        self._burn_btn.clicked.connect(self._show_burn_page)
        btn_layout.addWidget(self._burn_btn)

        self._save_iso_btn = QPushButton("Save ISO...")
        self._save_iso_btn.clicked.connect(self._save_iso)
        btn_layout.addWidget(self._save_iso_btn)

        done_btn = QPushButton("Done")
        done_btn.setObjectName("primaryButton")
        done_btn.clicked.connect(self.accept)
        btn_layout.addWidget(done_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._stack.addWidget(page)

    # ── Page 3: Burn ──

    def _setup_burn_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Burn to Disc")
        title.setObjectName("headingLabel")
        layout.addWidget(title)

        # Drive selection
        drive_label = QLabel("Select Drive:")
        drive_label.setStyleSheet(f"font-size: 13px; color: {TEXT_SECONDARY};")
        layout.addWidget(drive_label)

        self._drive_combo = QComboBox()
        self._drive_combo.setMinimumHeight(36)
        layout.addWidget(self._drive_combo)

        # Speed selection
        speed_layout = QHBoxLayout()
        speed_label = QLabel("Write Speed:")
        speed_label.setStyleSheet(f"font-size: 13px; color: {TEXT_SECONDARY};")
        speed_layout.addWidget(speed_label)

        self._speed_combo = QComboBox()
        self._speed_combo.addItems(["Auto", "2x", "4x", "8x"])
        self._speed_combo.setFixedWidth(100)
        speed_layout.addWidget(self._speed_combo)
        speed_layout.addStretch()
        layout.addLayout(speed_layout)

        layout.addSpacing(8)

        # Burn progress
        self._burn_progress = QProgressBar()
        self._burn_progress.setFixedHeight(8)
        self._burn_progress.setMinimum(0)
        self._burn_progress.setMaximum(100)
        self._burn_progress.hide()
        layout.addWidget(self._burn_progress)

        self._burn_status = QLabel("")
        self._burn_status.setStyleSheet(f"font-size: 13px; color: {TEXT_SECONDARY};")
        layout.addWidget(self._burn_status)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(2))
        btn_layout.addWidget(back_btn)

        self._start_burn_btn = QPushButton("Start Burn")
        self._start_burn_btn.setObjectName("primaryButton")
        self._start_burn_btn.clicked.connect(self._start_burn)
        btn_layout.addWidget(self._start_burn_btn)

        layout.addLayout(btn_layout)
        self._stack.addWidget(page)

    # ── Actions ──

    def _toggle_log(self):
        if self._log_output.isVisible():
            self._log_output.hide()
            self._log_toggle.setText("Show Log")
        else:
            self._log_output.show()
            self._log_toggle.setText("Hide Log")

    def _start_build(self):
        self._stack.setCurrentIndex(1)

        # Set up output directory
        self._output_dir = tempfile.mkdtemp(prefix="hootie_dvda_")
        self._iso_path = None

        if self._build_iso_check.isChecked():
            self._iso_path = str(Path(self._output_dir) / "dvd_audio.iso")

        self._pipeline = BuildPipeline(
            self._project,
            self._output_dir,
            iso_path=self._iso_path,
        )
        self._pipeline.stage_changed.connect(self._on_stage_changed)
        self._pipeline.progress.connect(self._on_progress)
        self._pipeline.log_line.connect(self._on_log_line)
        self._pipeline.finished_ok.connect(self._on_build_ok)
        self._pipeline.finished_error.connect(self._on_build_error)
        self._pipeline.start()

    def _cancel_build(self):
        if self._pipeline:
            self._pipeline.cancel()
        self.reject()

    def _on_stage_changed(self, stage: BuildStage):
        self._progress_stage.setText(stage.value)
        self._progress_title.setText(
            "Building..." if stage != BuildStage.COMPLETE else "Done!"
        )

    def _on_progress(self, current: int, total: int, description: str):
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(current)
        else:
            self._progress_bar.setMaximum(0)  # indeterminate
        self._progress_detail.setText(description)

    def _on_log_line(self, line: str):
        self._log_output.append(line)
        self._log_output.moveCursor(QTextCursor.MoveOperation.End)

    def _on_build_ok(self, output_path: str):
        self._stack.setCurrentIndex(2)
        self._complete_icon.setText("\u2713")
        self._complete_icon.setStyleSheet(f"font-size: 48px; color: {ACCENT_GREEN};")
        self._complete_title.setText("Build Complete!")
        self._complete_detail.setText(f"Output: {output_path}")
        self._error_output.hide()

        has_iso = self._iso_path and Path(self._iso_path).exists()
        self._burn_btn.setVisible(has_iso)
        self._save_iso_btn.setVisible(has_iso)

    def _on_build_error(self, stage: str, error: str):
        self._stack.setCurrentIndex(2)
        self._complete_icon.setText("\u2717")
        self._complete_icon.setStyleSheet(f"font-size: 48px; color: {ACCENT_RED};")
        self._complete_title.setText("Build Failed")
        self._complete_detail.setText(f"Error during: {stage}")
        self._error_output.setPlainText(error)
        self._error_output.show()
        self._burn_btn.hide()
        self._save_iso_btn.hide()

    def _save_iso(self):
        if not self._iso_path or not Path(self._iso_path).exists():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save ISO",
            str(Path.home() / "dvd_audio.iso"),
            "ISO Images (*.iso)",
        )
        if path:
            import shutil
            shutil.copy2(self._iso_path, path)
            self._complete_detail.setText(f"ISO saved to: {path}")

    # ── Burn ──

    def _show_burn_page(self):
        # Refresh drives
        self._drive_combo.clear()
        drives = detect_drives()
        if drives:
            for d in drives:
                self._drive_combo.addItem(d.display_name, d.device)
        else:
            self._drive_combo.addItem("No optical drives found")
            self._start_burn_btn.setEnabled(False)

        tool = get_burn_tool()
        if not tool:
            self._burn_status.setText("No burn tool found (need growisofs or wodim)")
            self._start_burn_btn.setEnabled(False)

        self._stack.setCurrentIndex(3)

    def _start_burn(self):
        device = self._drive_combo.currentData()
        if not device or not self._iso_path:
            return

        speed_text = self._speed_combo.currentText()
        speed = 0  # auto
        if speed_text != "Auto":
            speed = int(speed_text.replace("x", ""))

        self._start_burn_btn.setEnabled(False)
        self._burn_progress.show()
        self._burn_status.setText("Starting burn...")

        self._burn_worker = BurnWorker(self._iso_path, device, speed)
        self._burn_worker.progress.connect(self._on_burn_progress)
        self._burn_worker.finished_ok.connect(self._on_burn_ok)
        self._burn_worker.finished_error.connect(self._on_burn_error)
        self._burn_worker.start()

    def _on_burn_progress(self, pct: float, status: str):
        self._burn_progress.setValue(int(pct))
        self._burn_status.setText(status)

    def _on_burn_ok(self):
        self._burn_status.setText("Burn complete! You can remove the disc.")
        self._burn_status.setStyleSheet(f"font-size: 13px; color: {ACCENT_GREEN};")
        self._start_burn_btn.setText("Burn Another Copy")
        self._start_burn_btn.setEnabled(True)

    def _on_burn_error(self, error: str):
        self._burn_status.setText(f"Burn failed: {error}")
        self._burn_status.setStyleSheet(f"font-size: 13px; color: {ACCENT_RED};")
        self._start_burn_btn.setEnabled(True)

    def closeEvent(self, event):
        if self._pipeline:
            self._pipeline.cleanup()
        super().closeEvent(event)
