from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Track:
    file_path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    track_number: int = 0
    duration_seconds: float = 0.0
    sample_rate: int = 0
    bit_depth: int = 0
    channels: int = 0
    codec: str = ""
    file_size_bytes: int = 0
    needs_conversion: bool = False
    album_art_path: Optional[str] = None
    id: str = field(default_factory=lambda: __import__("uuid").uuid4().hex)

    def formatted_duration(self) -> str:
        total = int(self.duration_seconds)
        minutes, seconds = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def formatted_size(self) -> str:
        size = self.file_size_bytes
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def formatted_sample_rate(self) -> str:
        if self.sample_rate >= 1000:
            khz = self.sample_rate / 1000
            if khz == int(khz):
                return f"{int(khz)} kHz"
            return f"{khz:.1f} kHz"
        return f"{self.sample_rate} Hz"

    @property
    def filename(self) -> str:
        return Path(self.file_path).name

    @property
    def display_title(self) -> str:
        return self.title if self.title else Path(self.file_path).stem

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "track_number": self.track_number,
            "duration_seconds": self.duration_seconds,
            "sample_rate": self.sample_rate,
            "bit_depth": self.bit_depth,
            "channels": self.channels,
            "codec": self.codec,
            "file_size_bytes": self.file_size_bytes,
            "needs_conversion": self.needs_conversion,
            "album_art_path": self.album_art_path,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Track":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
