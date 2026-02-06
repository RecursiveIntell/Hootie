import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.group import Group
from app.models.track import Track


MAX_GROUPS = 9
MAX_TRACKS_PER_GROUP = 99


@dataclass
class Project:
    name: str = "Untitled Project"
    groups: list[Group] = field(default_factory=list)
    file_path: Optional[str] = None
    disc_type: str = "DVD-5"
    quality_preset: str = "KEEP_ORIGINAL"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    _modified: bool = field(default=False, repr=False)

    def mark_modified(self):
        self.modified_at = datetime.now().isoformat()
        self._modified = True

    @property
    def is_modified(self) -> bool:
        return self._modified

    def total_tracks(self) -> int:
        return sum(g.track_count for g in self.groups)

    def total_size_bytes(self) -> int:
        return sum(g.total_size_bytes for g in self.groups)

    def total_duration(self) -> float:
        return sum(g.total_duration for g in self.groups)

    def all_tracks(self) -> list[Track]:
        tracks = []
        for g in self.groups:
            tracks.extend(g.tracks)
        return tracks

    def add_group(self, name: str = "", color: str = "#5E81AC") -> Optional[Group]:
        if len(self.groups) >= MAX_GROUPS:
            return None
        if not name:
            name = f"Group {len(self.groups) + 1}"
        group = Group(name=name, color_tag=color)
        self.groups.append(group)
        self.mark_modified()
        return group

    def remove_group(self, group_id: str) -> bool:
        for i, g in enumerate(self.groups):
            if g.id == group_id:
                self.groups.pop(i)
                self.mark_modified()
                return True
        return False

    def get_group(self, group_id: str) -> Optional[Group]:
        for g in self.groups:
            if g.id == group_id:
                return g
        return None

    def add_tracks_to_group(self, group_id: str, tracks: list[Track]) -> bool:
        group = self.get_group(group_id)
        if group is None:
            return False
        if len(group.tracks) + len(tracks) > MAX_TRACKS_PER_GROUP:
            return False
        group.tracks.extend(tracks)
        self.mark_modified()
        return True

    def move_track(self, track_id: str, from_group_id: str, to_group_id: str, position: int = -1) -> bool:
        from_group = self.get_group(from_group_id)
        to_group = self.get_group(to_group_id)
        if not from_group or not to_group:
            return False
        if len(to_group.tracks) >= MAX_TRACKS_PER_GROUP:
            return False
        track = None
        for i, t in enumerate(from_group.tracks):
            if t.id == track_id:
                track = from_group.tracks.pop(i)
                break
        if track is None:
            return False
        if position < 0 or position >= len(to_group.tracks):
            to_group.tracks.append(track)
        else:
            to_group.tracks.insert(position, track)
        self.mark_modified()
        return True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "groups": [g.to_dict() for g in self.groups],
            "disc_type": self.disc_type,
            "quality_preset": self.quality_preset,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        groups = [Group.from_dict(g) for g in data.get("groups", [])]
        return cls(
            name=data.get("name", "Untitled Project"),
            groups=groups,
            disc_type=data.get("disc_type", "DVD-5"),
            quality_preset=data.get("quality_preset", "KEEP_ORIGINAL"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            modified_at=data.get("modified_at", datetime.now().isoformat()),
        )

    def save(self, path: Optional[str] = None) -> str:
        save_path = path or self.file_path
        if not save_path:
            raise ValueError("No save path specified")
        if not save_path.endswith(".hoot"):
            save_path += ".hoot"
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        self.file_path = save_path
        self._modified = False
        return save_path

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, "r") as f:
            data = json.load(f)
        project = cls.from_dict(data)
        project.file_path = path
        project._modified = False
        return project
