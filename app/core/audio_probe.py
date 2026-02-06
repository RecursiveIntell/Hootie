import json
import subprocess
from pathlib import Path
from typing import Optional

from app.models.track import Track


SUPPORTED_EXTENSIONS = {
    ".flac", ".wav", ".aiff", ".aif", ".mp3", ".ogg",
    ".opus", ".m4a", ".aac", ".wma", ".alac",
}

# Formats that dvda-author can handle natively (PCM-based)
NATIVE_FORMATS = {".wav", ".flac", ".aiff", ".aif"}


def is_supported(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def probe_file(path: str) -> Track:
    """Probe an audio file with ffprobe and return a Track model."""
    path = str(Path(path).resolve())

    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        path,
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=15
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr.strip()}")

    data = json.loads(result.stdout)

    audio_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break

    if audio_stream is None:
        raise ValueError(f"No audio stream found in {path}")

    fmt = data.get("format", {})
    tags = {**fmt.get("tags", {}), **audio_stream.get("tags", {})}
    # Normalize tag keys to lowercase
    tags = {k.lower(): v for k, v in tags.items()}

    codec = audio_stream.get("codec_name", "unknown")
    sample_rate = int(audio_stream.get("sample_rate", 0))
    channels = int(audio_stream.get("channels", 0))
    duration = float(fmt.get("duration", audio_stream.get("duration", 0)))
    file_size = int(fmt.get("size", 0))

    # Determine bit depth
    bit_depth = 0
    bits_per_raw = audio_stream.get("bits_per_raw_sample")
    if bits_per_raw and bits_per_raw != "N/A":
        bit_depth = int(bits_per_raw)
    elif audio_stream.get("bits_per_sample"):
        bit_depth = int(audio_stream["bits_per_sample"])
    elif codec in ("flac", "alac"):
        bit_depth = 16  # default assumption
    elif codec in ("pcm_s16le", "pcm_s16be"):
        bit_depth = 16
    elif codec in ("pcm_s24le", "pcm_s24be"):
        bit_depth = 24
    elif codec in ("pcm_s32le", "pcm_s32be"):
        bit_depth = 32

    # Parse track number
    track_number = 0
    raw_track = tags.get("track", "0")
    try:
        track_number = int(str(raw_track).split("/")[0])
    except (ValueError, IndexError):
        pass

    ext = Path(path).suffix.lower()
    needs_conversion = ext not in NATIVE_FORMATS

    return Track(
        file_path=path,
        title=tags.get("title", ""),
        artist=tags.get("artist", tags.get("album_artist", "")),
        album=tags.get("album", ""),
        track_number=track_number,
        duration_seconds=duration,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        channels=channels,
        codec=codec,
        file_size_bytes=file_size,
        needs_conversion=needs_conversion,
    )


def extract_album_art(path: str, dest_dir: str) -> Optional[str]:
    """Extract embedded album art to a temp file. Returns path or None."""
    dest = Path(dest_dir) / f"{Path(path).stem}_cover.jpg"
    cmd = [
        "ffmpeg", "-v", "quiet", "-y",
        "-i", path,
        "-an", "-vcodec", "mjpeg",
        "-frames:v", "1",
        str(dest),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
            return str(dest)
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def probe_files(paths: list[str]) -> list[Track]:
    """Probe multiple files, skipping unsupported ones."""
    tracks = []
    for p in paths:
        if is_supported(p):
            try:
                tracks.append(probe_file(p))
            except (RuntimeError, ValueError):
                continue
    return tracks
