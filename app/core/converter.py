import os
import subprocess
import shutil
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

log = logging.getLogger("hootie.converter")


class QualityPreset(Enum):
    CAR_STEREO = ("CAR_STEREO", 44100, 16, "Car Stereo (16-bit/44.1 kHz)")
    HIFI = ("HIFI", 96000, 24, "Hi-Fi (24-bit/96 kHz)")
    MAXIMUM = ("MAXIMUM", 192000, 24, "Maximum (24-bit/192 kHz)")
    KEEP_ORIGINAL = ("KEEP_ORIGINAL", 0, 0, "Keep Original")

    def __init__(self, key: str, sample_rate: int, bit_depth: int, label: str):
        self.key = key
        self.target_sample_rate = sample_rate
        self.target_bit_depth = bit_depth
        self.label = label

    @classmethod
    def from_key(cls, key: str) -> "QualityPreset":
        for p in cls:
            if p.key == key:
                return p
        return cls.KEEP_ORIGINAL


def convert_to_wav(
    input_path: str,
    output_path: str,
    target_sample_rate: int = 0,
    target_bit_depth: int = 0,
) -> str:
    """Convert an audio file to WAV using SoX (preferred) or ffmpeg.

    Returns the output path on success, raises on failure.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    input_ext = Path(input_path).suffix.lower()

    # Try SoX for WAV/FLAC/AIFF (best quality resampling)
    use_sox = shutil.which("sox") and input_ext in (".wav", ".flac", ".aiff", ".aif")

    if use_sox:
        cmd = ["sox", input_path]
        if target_bit_depth:
            cmd.extend(["-b", str(target_bit_depth)])
        cmd.append(output_path)
        if target_sample_rate:
            cmd.extend(["rate", "-v", str(target_sample_rate)])
    else:
        # Use ffmpeg
        cmd = ["ffmpeg", "-v", "quiet", "-y", "-i", input_path]
        if target_sample_rate:
            cmd.extend(["-ar", str(target_sample_rate)])
        if target_bit_depth:
            codec = f"pcm_s{target_bit_depth}le"
            cmd.extend(["-acodec", codec])
        else:
            cmd.extend(["-acodec", "pcm_s16le"])
        cmd.append(output_path)

    log.info(f"Converting: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Conversion failed for {input_path}: {error}")

    return output_path


class ConversionJob:
    def __init__(self, input_path: str, output_path: str,
                 target_sample_rate: int = 0, target_bit_depth: int = 0,
                 track_id: str = ""):
        self.input_path = input_path
        self.output_path = output_path
        self.target_sample_rate = target_sample_rate
        self.target_bit_depth = target_bit_depth
        self.track_id = track_id
        self.success = False
        self.error: Optional[str] = None


class ConversionWorker(QThread):
    """Runs conversions in a background thread with progress signals."""

    progress = pyqtSignal(int, int, str)  # current, total, current_file_name
    job_complete = pyqtSignal(object)  # ConversionJob
    all_complete = pyqtSignal(list)  # list of ConversionJob
    error = pyqtSignal(str)

    def __init__(self, jobs: list[ConversionJob]):
        super().__init__()
        self._jobs = jobs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        completed = []
        total = len(self._jobs)
        for i, job in enumerate(self._jobs):
            if self._cancelled:
                break
            self.progress.emit(i, total, Path(job.input_path).name)
            try:
                convert_to_wav(
                    job.input_path, job.output_path,
                    job.target_sample_rate, job.target_bit_depth,
                )
                job.success = True
            except Exception as e:
                job.success = False
                job.error = str(e)
                log.error(f"Conversion failed: {e}")
            completed.append(job)
            self.job_complete.emit(job)

        self.progress.emit(total, total, "")
        self.all_complete.emit(completed)
