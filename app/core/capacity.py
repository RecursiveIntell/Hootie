DVD5_CAPACITY = 4_700_000_000    # 4.7 GB single-layer
DVD9_CAPACITY = 8_500_000_000    # 8.5 GB dual-layer
DVD10_CAPACITY = 9_400_000_000   # 9.4 GB double-sided single-layer

DISC_CAPACITIES = {
    "DVD-5": DVD5_CAPACITY,
    "DVD-9": DVD9_CAPACITY,
    "DVD-10": DVD10_CAPACITY,
}


def calculate_pcm_size(sample_rate: int, bit_depth: int, channels: int, duration_seconds: float) -> int:
    """Calculate raw PCM data size in bytes."""
    bytes_per_sample = bit_depth // 8
    return int(sample_rate * bytes_per_sample * channels * duration_seconds)


def estimate_mlp_size(pcm_size: int) -> int:
    """Estimate MLP (Meridian Lossless Packing) compressed size — roughly 60% of PCM."""
    return int(pcm_size * 0.60)


def calculate_track_pcm_size(track) -> int:
    """Calculate PCM size for a Track object."""
    return calculate_pcm_size(
        track.sample_rate, track.bit_depth, track.channels, track.duration_seconds
    )


def calculate_total_disc_usage(groups, overhead_pct: float = 0.05) -> int:
    """Calculate total disc usage for all groups including filesystem overhead."""
    total = 0
    for group in groups:
        for track in group.tracks:
            total += calculate_track_pcm_size(track)
    # Add overhead for DVD-Audio filesystem structure
    total = int(total * (1 + overhead_pct))
    return total


def get_disc_capacity(disc_type: str) -> int:
    return DISC_CAPACITIES.get(disc_type, DVD5_CAPACITY)


def usage_percentage(groups, disc_type: str = "DVD-5") -> float:
    """Return disc usage as a percentage (0-100+)."""
    capacity = get_disc_capacity(disc_type)
    usage = calculate_total_disc_usage(groups)
    if capacity == 0:
        return 0.0
    return (usage / capacity) * 100


def usage_summary(groups, disc_type: str = "DVD-5") -> dict:
    """Return a summary dict with usage info."""
    capacity = get_disc_capacity(disc_type)
    usage = calculate_total_disc_usage(groups)
    return {
        "used_bytes": usage,
        "capacity_bytes": capacity,
        "percentage": (usage / capacity) * 100 if capacity else 0,
        "remaining_bytes": max(0, capacity - usage),
        "over_capacity": usage > capacity,
        "used_gb": usage / 1_000_000_000,
        "capacity_gb": capacity / 1_000_000_000,
    }


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
