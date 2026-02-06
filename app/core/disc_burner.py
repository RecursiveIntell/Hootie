import re
import shutil
import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

log = logging.getLogger("hootie.disc_burner")


@dataclass
class DriveInfo:
    device: str  # e.g., /dev/sr0
    name: str
    can_write: bool

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.device})" if self.name else self.device


def detect_drives() -> list[DriveInfo]:
    """Detect optical disc drives on the system."""
    drives = []

    # Check /dev/sr* devices
    import glob
    for dev in sorted(glob.glob("/dev/sr*")):
        name = ""
        can_write = False
        try:
            # Get drive info via lsblk
            result = subprocess.run(
                ["lsblk", "-ndo", "MODEL", dev],
                capture_output=True, text=True, timeout=5,
            )
            name = result.stdout.strip()

            # Check write capability
            result = subprocess.run(
                ["lsblk", "-ndo", "RO", dev],
                capture_output=True, text=True, timeout=5,
            )
            can_write = result.stdout.strip() == "0"
        except (subprocess.TimeoutExpired, OSError):
            pass

        drives.append(DriveInfo(device=dev, name=name, can_write=can_write))

    return drives


def get_burn_tool() -> Optional[str]:
    """Detect which burn tool is available."""
    if shutil.which("growisofs"):
        return "growisofs"
    if shutil.which("wodim"):
        return "wodim"
    return None


class BurnWorker(QThread):
    """Burns an ISO to disc in a background thread."""

    progress = pyqtSignal(float, str)  # percentage (0-100), status message
    finished_ok = pyqtSignal()
    finished_error = pyqtSignal(str)

    def __init__(
        self,
        iso_path: str,
        device: str,
        speed: int = 0,
        auto_eject: bool = False,
        verify_after_burn: bool = False,
    ):
        super().__init__()
        self._iso_path = iso_path
        self._device = device
        self._speed = speed
        self._auto_eject = auto_eject
        self._verify_after_burn = verify_after_burn
        self._cancelled = False
        self._process = None

    def cancel(self):
        self._cancelled = True
        if self._process:
            self._process.terminate()

    def run(self):
        tool = get_burn_tool()
        if not tool:
            self.finished_error.emit("No disc burning tool found (growisofs or wodim required)")
            return

        if tool == "growisofs":
            cmd = [
                "growisofs",
                f"-dvd-compat",
                "-Z", f"{self._device}={self._iso_path}",
            ]
            if self._speed:
                cmd.extend(["-speed", str(self._speed)])
        else:
            # wodim
            cmd = [
                "wodim",
                f"dev={self._device}",
                "-v", "-dao",
                self._iso_path,
            ]
            if self._verify_after_burn:
                cmd.append("-verify")
            if self._speed:
                cmd.extend([f"speed={self._speed}"])

        log.info(f"Burning: {' '.join(cmd)}")
        self.progress.emit(0, "Starting burn...")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            progress_re = re.compile(r"(\d+\.?\d*)%")

            for line in self._process.stdout:
                if self._cancelled:
                    self._process.terminate()
                    self.finished_error.emit("Burn cancelled")
                    return

                line = line.strip()
                log.debug(f"burn: {line}")

                # Try to parse progress
                match = progress_re.search(line)
                if match:
                    pct = float(match.group(1))
                    self.progress.emit(pct, f"Burning... {pct:.0f}%")

            self._process.wait()

            if self._process.returncode == 0:
                if self._auto_eject:
                    # Best effort: eject is optional and platform-dependent.
                    try:
                        subprocess.run(
                            ["eject", self._device],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                    except (subprocess.TimeoutExpired, OSError):
                        pass
                self.progress.emit(100, "Burn complete!")
                self.finished_ok.emit()
            else:
                self.finished_error.emit(f"Burn failed (exit code {self._process.returncode})")

        except FileNotFoundError:
            self.finished_error.emit(f"{tool} not found")
        except Exception as e:
            self.finished_error.emit(str(e))
        finally:
            self._process = None
