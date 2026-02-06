from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QComboBox, QListWidget, QListWidgetItem,
    QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal

from app.models.track import Track
from app.models.group import Group
from app.core.converter import (
    ConversionJob, ConversionWorker, QualityPreset,
)
from app.ui.theme import (
    BG_DARKEST, BG_DARK, BG_MID, BG_LIGHTER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED, ACCENT_BLUE,
    SPACING_MD, SPACING_LG,
)


class ConversionDialog(QDialog):
    """Dialog for converting tracks to a target format."""

    tracks_converted = pyqtSignal(list)  # list of (track_id, new_path) tuples

    def __init__(self, tracks: list[Track], output_dir: str = "",
                 target_sample_rate: int = 44100, target_bit_depth: int = 16,
                 parent=None):
        super().__init__(parent)
        self._tracks = tracks
        self._output_dir = output_dir or str(Path.home() / ".cache" / "hootie" / "converted")
        self._target_sr = target_sample_rate
        self._target_bd = target_bit_depth
        self._worker: Optional[ConversionWorker] = None

        self.setWindowTitle("Convert Tracks")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Convert Tracks")
        title.setObjectName("headingLabel")
        layout.addWidget(title)

        desc = QLabel(f"{len(self._tracks)} track(s) need conversion to WAV for DVD-Audio compatibility.")
        desc.setObjectName("secondaryLabel")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Target format
        fmt_layout = QHBoxLayout()
        fmt_layout.setSpacing(12)

        fmt_label = QLabel("Target Format:")
        fmt_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        fmt_layout.addWidget(fmt_label)

        self._preset_combo = QComboBox()
        for preset in QualityPreset:
            self._preset_combo.addItem(preset.label, preset.key)
        self._preset_combo.setCurrentIndex(0)  # CAR_STEREO
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        fmt_layout.addWidget(self._preset_combo, 1)

        layout.addLayout(fmt_layout)

        # Target info
        self._format_info = QLabel()
        self._format_info.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED};")
        layout.addWidget(self._format_info)
        self._update_format_info()

        # Track list
        self._track_list = QListWidget()
        self._track_list.setStyleSheet(f"background-color: {BG_DARKEST};")
        for track in self._tracks:
            item = QListWidgetItem(
                f"{track.display_title}  ({track.codec.upper()}, "
                f"{track.formatted_sample_rate()}, {track.bit_depth}-bit)"
            )
            item.setData(Qt.ItemDataRole.UserRole, track.id)
            self._track_list.addItem(item)
        layout.addWidget(self._track_list, 1)

        # Progress (hidden initially)
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        self._progress_label.hide()
        layout.addWidget(self._progress_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self._cancel_btn)

        self._convert_btn = QPushButton("Convert")
        self._convert_btn.setObjectName("primaryButton")
        self._convert_btn.clicked.connect(self._start_conversion)
        btn_layout.addWidget(self._convert_btn)

        layout.addLayout(btn_layout)

    def _on_preset_changed(self, index: int):
        self._update_format_info()

    def _update_format_info(self):
        key = self._preset_combo.currentData()
        preset = QualityPreset.from_key(key)
        if preset == QualityPreset.KEEP_ORIGINAL:
            self._format_info.setText("Files will be converted to WAV keeping original sample rate and bit depth")
        else:
            self._format_info.setText(
                f"Target: {preset.target_bit_depth}-bit / "
                f"{preset.target_sample_rate / 1000:.1f} kHz WAV"
            )
        self._target_sr = preset.target_sample_rate
        self._target_bd = preset.target_bit_depth

    def _start_conversion(self):
        Path(self._output_dir).mkdir(parents=True, exist_ok=True)

        jobs = []
        for track in self._tracks:
            output = Path(self._output_dir) / f"{track.id}.wav"
            jobs.append(ConversionJob(
                input_path=track.file_path,
                output_path=str(output),
                target_sample_rate=self._target_sr if self._target_sr else track.sample_rate,
                target_bit_depth=self._target_bd if self._target_bd else track.bit_depth,
                track_id=track.id,
            ))

        self._convert_btn.setEnabled(False)
        self._progress_bar.setMaximum(len(jobs))
        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._progress_label.show()

        self._worker = ConversionWorker(jobs)
        self._worker.progress.connect(self._on_progress)
        self._worker.all_complete.connect(self._on_complete)
        self._worker.start()

    def _on_progress(self, current: int, total: int, name: str):
        self._progress_bar.setValue(current)
        self._progress_label.setText(f"Converting: {name}")

    def _on_complete(self, jobs: list[ConversionJob]):
        successful = [(j.track_id, j.output_path) for j in jobs if j.success]
        failed = [j for j in jobs if not j.success]

        if failed:
            self._progress_label.setText(
                f"Done. {len(successful)} converted, {len(failed)} failed."
            )
            self._progress_label.setStyleSheet(f"font-size: 12px; color: {ACCENT_YELLOW};")
        else:
            self._progress_label.setText(f"All {len(successful)} tracks converted successfully!")
            self._progress_label.setStyleSheet(f"font-size: 12px; color: {ACCENT_GREEN};")

        self.tracks_converted.emit(successful)
        self._convert_btn.setText("Done")
        self._convert_btn.setEnabled(True)
        self._convert_btn.clicked.disconnect()
        self._convert_btn.clicked.connect(self.accept)

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
        self.reject()
