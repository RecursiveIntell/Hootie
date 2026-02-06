import logging
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal

from app.models.project import Project
from app.models.group import Group
from app.models.track import Track
from app.core.converter import ConversionJob, ConversionWorker, convert_to_wav
from app.core.dvda_engine import build_command, DvdaWorker
from app.core.audio_probe import NATIVE_FORMATS

log = logging.getLogger("hootie.iso_builder")


class BuildStage(Enum):
    VALIDATING = "Validating project"
    CONVERTING = "Converting audio files"
    AUTHORING = "Creating DVD-Audio structure"
    CREATING_ISO = "Creating ISO image"
    COMPLETE = "Build complete"
    ERROR = "Error"


class BuildPipeline(QObject):
    """Orchestrates the full build workflow:
    1. Validate groups
    2. Convert files that need it
    3. Run dvda-author
    4. Optionally create ISO
    """

    stage_changed = pyqtSignal(object)  # BuildStage
    progress = pyqtSignal(int, int, str)  # current, total, description
    log_line = pyqtSignal(str)
    finished_ok = pyqtSignal(str)  # output path (ISO or directory)
    finished_error = pyqtSignal(str, str)  # stage, error message

    def __init__(self, project: Project, output_dir: str,
                 iso_path: Optional[str] = None,
                 target_sample_rate: int = 0,
                 target_bit_depth: int = 0,
                 dvda_author_path: str = "dvda-author",
                 parent=None):
        super().__init__(parent)
        self._project = project
        self._output_dir = output_dir
        self._iso_path = iso_path
        self._target_sr = target_sample_rate
        self._target_bd = target_bit_depth
        self._dvda_path = dvda_author_path
        self._temp_dir: Optional[str] = None
        self._cancelled = False
        self._conversion_worker: Optional[ConversionWorker] = None
        self._dvda_worker: Optional[DvdaWorker] = None

    def cancel(self):
        self._cancelled = True
        if self._conversion_worker:
            self._conversion_worker.cancel()
        if self._dvda_worker:
            self._dvda_worker.cancel()

    def start(self):
        """Start the build pipeline."""
        self._run_validation()

    def _run_validation(self):
        self.stage_changed.emit(BuildStage.VALIDATING)
        self.log_line.emit("Validating project...")

        errors = []

        if not self._project.groups:
            errors.append("No groups in project")

        if self._project.total_tracks() == 0:
            errors.append("No tracks in project")

        for group in self._project.groups:
            if not group.tracks:
                errors.append(f"Group '{group.name}' has no tracks")

            for track in group.tracks:
                if not Path(track.file_path).exists():
                    errors.append(f"File not found: {track.file_path}")

        if errors:
            self.finished_error.emit("Validation", "\n".join(errors))
            return

        self.log_line.emit("Validation passed")
        self._run_conversion()

    def _run_conversion(self):
        """Convert any files that need conversion to WAV."""
        self._temp_dir = tempfile.mkdtemp(prefix="hootie_build_")
        jobs = []

        for group in self._project.groups:
            for track in group.tracks:
                ext = Path(track.file_path).suffix.lower()
                needs_convert = ext not in NATIVE_FORMATS

                # Also convert if target sample rate/bit depth differs
                needs_resample = (
                    (self._target_sr and track.sample_rate != self._target_sr) or
                    (self._target_bd and track.bit_depth != self._target_bd)
                )

                if needs_convert or needs_resample:
                    output = Path(self._temp_dir) / f"{track.id}.wav"
                    jobs.append(ConversionJob(
                        input_path=track.file_path,
                        output_path=str(output),
                        target_sample_rate=self._target_sr or track.sample_rate,
                        target_bit_depth=self._target_bd or track.bit_depth,
                        track_id=track.id,
                    ))

        if not jobs:
            self.log_line.emit("No conversion needed")
            self._run_authoring()
            return

        self.stage_changed.emit(BuildStage.CONVERTING)
        self.log_line.emit(f"Converting {len(jobs)} file(s)...")

        self._conversion_worker = ConversionWorker(jobs)
        self._conversion_worker.progress.connect(
            lambda cur, tot, name: self.progress.emit(cur, tot, f"Converting: {name}")
        )
        self._conversion_worker.all_complete.connect(self._on_conversion_done)
        self._conversion_worker.start()

    def _on_conversion_done(self, jobs: list[ConversionJob]):
        failed = [j for j in jobs if not j.success]
        if failed:
            errors = "\n".join(f"  {j.input_path}: {j.error}" for j in failed)
            self.finished_error.emit("Conversion", f"Failed to convert:\n{errors}")
            return

        # Update track file paths to converted files
        converted_map = {j.track_id: j.output_path for j in jobs}
        for group in self._project.groups:
            for track in group.tracks:
                if track.id in converted_map:
                    track._original_path = track.file_path
                    track.file_path = converted_map[track.id]

        self.log_line.emit("Conversion complete")
        self._run_authoring()

    def _run_authoring(self):
        self.stage_changed.emit(BuildStage.AUTHORING)
        self.log_line.emit("Running dvda-author...")

        Path(self._output_dir).mkdir(parents=True, exist_ok=True)

        cmd = build_command(
            self._project.groups,
            self._output_dir,
            iso_path=self._iso_path,
            dvda_author_path=self._dvda_path,
        )

        self._dvda_worker = DvdaWorker(cmd)
        self._dvda_worker.output_line.connect(self.log_line.emit)
        self._dvda_worker.progress.connect(
            lambda p: self.progress.emit(0, 0, p.message)
        )
        self._dvda_worker.finished_ok.connect(self._on_authoring_done)
        self._dvda_worker.finished_error.connect(
            lambda err: self.finished_error.emit("Authoring", err)
        )
        self._dvda_worker.start()

    def _on_authoring_done(self, output_dir: str):
        self.log_line.emit("DVD-Audio authoring complete")

        # Restore original file paths
        for group in self._project.groups:
            for track in group.tracks:
                if hasattr(track, "_original_path"):
                    track.file_path = track._original_path
                    del track._original_path

        # Cleanup temp dir
        if self._temp_dir and Path(self._temp_dir).exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

        self.stage_changed.emit(BuildStage.COMPLETE)
        result_path = self._iso_path if self._iso_path else self._output_dir
        self.finished_ok.emit(result_path)

    def cleanup(self):
        """Clean up temporary files."""
        if self._temp_dir and Path(self._temp_dir).exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
