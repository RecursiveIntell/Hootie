from dataclasses import dataclass, field
from typing import Optional
from collections import Counter
import uuid

from app.models.track import Track


@dataclass
class Group:
    name: str
    tracks: list[Track] = field(default_factory=list)
    color_tag: str = "#5E81AC"
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def total_duration(self) -> float:
        return sum(t.duration_seconds for t in self.tracks)

    @property
    def total_size_bytes(self) -> int:
        return sum(t.file_size_bytes for t in self.tracks)

    @property
    def track_count(self) -> int:
        return len(self.tracks)

    @property
    def dominant_sample_rate(self) -> Optional[int]:
        if not self.tracks:
            return None
        rates = Counter(t.sample_rate for t in self.tracks)
        return rates.most_common(1)[0][0]

    @property
    def dominant_bit_depth(self) -> Optional[int]:
        if not self.tracks:
            return None
        depths = Counter(t.bit_depth for t in self.tracks)
        return depths.most_common(1)[0][0]

    def find_mismatched_tracks(self) -> list[Track]:
        dom_rate = self.dominant_sample_rate
        dom_depth = self.dominant_bit_depth
        if dom_rate is None:
            return []
        return [
            t for t in self.tracks
            if t.sample_rate != dom_rate or t.bit_depth != dom_depth
        ]

    def formatted_duration(self) -> str:
        total = int(self.total_duration)
        minutes, seconds = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "tracks": [t.to_dict() for t in self.tracks],
            "color_tag": self.color_tag,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Group":
        tracks = [Track.from_dict(t) for t in data.get("tracks", [])]
        return cls(
            name=data["name"],
            tracks=tracks,
            color_tag=data.get("color_tag", "#5E81AC"),
            id=data.get("id", uuid.uuid4().hex),
        )
