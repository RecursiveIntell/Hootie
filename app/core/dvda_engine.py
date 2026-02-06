import re
import subprocess
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from PyQt6.QtCore import QThread, pyqtSignal

log = logging.getLogger("hootie.dvda_engine")

# ANSI escape code pattern
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# dvda-author message tag patterns
MSG_RE = re.compile(r"\[(MSG|INF|WAR|ERR)\]\s*(.*)")


@dataclass
class DvdaProgress:
    stage: str  # "MSG", "INF", "WAR", "ERR"
    message: str
    raw: str


def build_command(
    groups: list,
    output_dir: str,
    iso_path: Optional[str] = None,
    dvda_author_path: str = "dvda-author",
) -> list[str]:
    """Construct the dvda-author command line from groups of tracks.

    dvda-author syntax:
        dvda-author -g file1.wav file2.wav -g file3.wav -o output_dir [-W iso_path]
    """
    cmd = [dvda_author_path]

    for group in groups:
        if not group.tracks:
            continue
        cmd.append("-g")
        for track in group.tracks:
            cmd.append(track.file_path)

    cmd.extend(["-o", output_dir])

    if iso_path:
        cmd.extend(["-W", iso_path])

    return cmd


def parse_output_line(line: str) -> Optional[DvdaProgress]:
    """Parse a single line of dvda-author output into structured progress."""
    # Strip ANSI codes
    clean = ANSI_RE.sub("", line).strip()
    if not clean:
        return None

    match = MSG_RE.match(clean)
    if match:
        return DvdaProgress(
            stage=match.group(1),
            message=match.group(2),
            raw=clean,
        )

    # Lines without tags are treated as MSG
    return DvdaProgress(stage="MSG", message=clean, raw=clean)


class DvdaWorker(QThread):
    """Runs dvda-author in a subprocess and emits progress signals."""

    progress = pyqtSignal(object)  # DvdaProgress
    output_line = pyqtSignal(str)  # raw line for log display
    finished_ok = pyqtSignal(str)  # output directory
    finished_error = pyqtSignal(str)  # error message

    def __init__(self, cmd: list[str], cwd: Optional[str] = None):
        super().__init__()
        self._cmd = cmd
        self._cwd = cwd
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if hasattr(self, "_process") and self._process:
            self._process.terminate()

    def run(self):
        log.info(f"Running: {' '.join(self._cmd)}")
        try:
            self._process = subprocess.Popen(
                self._cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self._cwd,
            )

            for line in self._process.stdout:
                if self._cancelled:
                    self._process.terminate()
                    self.finished_error.emit("Cancelled by user")
                    return

                line = line.rstrip()
                self.output_line.emit(line)

                parsed = parse_output_line(line)
                if parsed:
                    self.progress.emit(parsed)

            self._process.wait()

            if self._process.returncode == 0:
                self.finished_ok.emit(self._cmd[self._cmd.index("-o") + 1] if "-o" in self._cmd else "")
            else:
                self.finished_error.emit(f"dvda-author exited with code {self._process.returncode}")

        except FileNotFoundError:
            self.finished_error.emit("dvda-author not found. Please install or compile it.")
        except Exception as e:
            self.finished_error.emit(str(e))
        finally:
            self._process = None
