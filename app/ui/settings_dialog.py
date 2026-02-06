import json
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QFormLayout, QComboBox, QSpinBox,
    QCheckBox, QLineEdit, QFileDialog, QFrame,
)
from PyQt6.QtCore import Qt

from app.ui.theme import (
    BG_DARK, BG_MID, BG_LIGHTER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_BLUE,
)

SETTINGS_PATH = Path.home() / ".config" / "hootie" / "settings.json"

DEFAULT_SETTINGS = {
    "general": {
        "quality_preset": "KEEP_ORIGINAL",
        "temp_dir": "",
        "auto_save_interval": 5,
    },
    "burning": {
        "default_speed": "Auto",
        "preferred_device": "",
        "verify_after_burn": False,
        "auto_eject": True,
    },
    "conversion": {
        "sox_quality": "high",
        "keep_converted_files": False,
    },
    "appearance": {
        "theme": "dark",
        "font_size": 13,
    },
}


def load_settings() -> dict:
    try:
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH) as f:
                saved = json.load(f)
            # Merge with defaults
            settings = {}
            for section, defaults in DEFAULT_SETTINGS.items():
                settings[section] = {**defaults, **saved.get(section, {})}
            return settings
    except (json.JSONDecodeError, OSError):
        pass
    return {k: dict(v) for k, v in DEFAULT_SETTINGS.items()}


def save_settings(settings: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        self._settings = load_settings()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabs = QTabWidget()

        # General tab
        general = QWidget()
        gen_layout = QFormLayout(general)
        gen_layout.setContentsMargins(24, 20, 24, 20)
        gen_layout.setSpacing(12)

        self._preset_combo = QComboBox()
        self._preset_combo.addItems(["KEEP_ORIGINAL", "CAR_STEREO", "HIFI", "MAXIMUM"])
        self._preset_combo.setCurrentText(self._settings["general"]["quality_preset"])
        gen_layout.addRow("Default Quality:", self._preset_combo)

        temp_row = QHBoxLayout()
        self._temp_dir = QLineEdit(self._settings["general"]["temp_dir"])
        self._temp_dir.setPlaceholderText("System default")
        temp_row.addWidget(self._temp_dir)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_temp_dir)
        temp_row.addWidget(browse_btn)
        gen_layout.addRow("Temp Directory:", temp_row)

        self._auto_save = QSpinBox()
        self._auto_save.setRange(1, 60)
        self._auto_save.setSuffix(" min")
        self._auto_save.setValue(self._settings["general"]["auto_save_interval"])
        gen_layout.addRow("Auto-save Interval:", self._auto_save)

        tabs.addTab(general, "General")

        # Burning tab
        burning = QWidget()
        burn_layout = QFormLayout(burning)
        burn_layout.setContentsMargins(24, 20, 24, 20)
        burn_layout.setSpacing(12)

        self._speed_combo = QComboBox()
        self._speed_combo.addItems(["Auto", "2x", "4x", "8x"])
        self._speed_combo.setCurrentText(self._settings["burning"]["default_speed"])
        burn_layout.addRow("Default Speed:", self._speed_combo)

        self._verify = QCheckBox("Verify disc after burning")
        self._verify.setChecked(self._settings["burning"]["verify_after_burn"])
        burn_layout.addRow("", self._verify)

        self._auto_eject = QCheckBox("Eject disc when done")
        self._auto_eject.setChecked(self._settings["burning"]["auto_eject"])
        burn_layout.addRow("", self._auto_eject)

        tabs.addTab(burning, "Burning")

        # Conversion tab
        conversion = QWidget()
        conv_layout = QFormLayout(conversion)
        conv_layout.setContentsMargins(24, 20, 24, 20)
        conv_layout.setSpacing(12)

        self._sox_quality = QComboBox()
        self._sox_quality.addItems(["low", "medium", "high", "very high"])
        self._sox_quality.setCurrentText(self._settings["conversion"]["sox_quality"])
        conv_layout.addRow("SoX Quality:", self._sox_quality)

        self._keep_converted = QCheckBox("Keep converted files after build")
        self._keep_converted.setChecked(self._settings["conversion"]["keep_converted_files"])
        conv_layout.addRow("", self._keep_converted)

        tabs.addTab(conversion, "Conversion")

        # Appearance tab
        appearance = QWidget()
        app_layout = QFormLayout(appearance)
        app_layout.setContentsMargins(24, 20, 24, 20)
        app_layout.setSpacing(12)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["dark"])
        self._theme_combo.setCurrentText(self._settings["appearance"]["theme"])
        app_layout.addRow("Theme:", self._theme_combo)

        self._font_size = QSpinBox()
        self._font_size.setRange(10, 20)
        self._font_size.setSuffix(" pt")
        self._font_size.setValue(self._settings["appearance"]["font_size"])
        app_layout.addRow("Font Size:", self._font_size)

        tabs.addTab(appearance, "Appearance")

        layout.addWidget(tabs)

        # Buttons
        btn_frame = QFrame()
        btn_frame.setStyleSheet(f"background-color: {BG_DARK}; border-top: 1px solid {BG_LIGHTER};")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(16, 12, 16, 12)

        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addWidget(btn_frame)

    def _browse_temp_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Temp Directory")
        if path:
            self._temp_dir.setText(path)

    def _save(self):
        self._settings["general"]["quality_preset"] = self._preset_combo.currentText()
        self._settings["general"]["temp_dir"] = self._temp_dir.text()
        self._settings["general"]["auto_save_interval"] = self._auto_save.value()

        self._settings["burning"]["default_speed"] = self._speed_combo.currentText()
        self._settings["burning"]["verify_after_burn"] = self._verify.isChecked()
        self._settings["burning"]["auto_eject"] = self._auto_eject.isChecked()

        self._settings["conversion"]["sox_quality"] = self._sox_quality.currentText()
        self._settings["conversion"]["keep_converted_files"] = self._keep_converted.isChecked()

        self._settings["appearance"]["theme"] = self._theme_combo.currentText()
        self._settings["appearance"]["font_size"] = self._font_size.value()

        save_settings(self._settings)
        self.accept()
