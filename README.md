# Hootie

Hootie is a desktop app for authoring DVD-Audio projects from music files.

It provides a PyQt6 interface on top of `dvda-author`, plus conversion, project management, capacity estimation, and optional disc burning.

## What It Does

- Imports audio via file picker, folder scan, or drag-and-drop.
- Supports FLAC, WAV, AIFF, MP3, OGG, Opus, M4A, AAC, WMA, and ALAC.
- Organizes tracks into groups (DVD-A title groups).
- Probes metadata with `ffprobe`.
- Converts non-native formats to WAV before authoring.
- Applies quality presets during build:
  - `KEEP_ORIGINAL`
  - `CAR_STEREO` (16-bit / 44.1 kHz)
  - `HIFI` (24-bit / 96 kHz)
  - `MAXIMUM` (24-bit / 192 kHz)
- Estimates disc usage for `DVD-5`, `DVD-9`, and `DVD-10`.
- Builds DVD-Audio structure and optional ISO through `dvda-author`.
- Burns ISO with `growisofs` or `wodim`.
- Saves/loads project files as `.hoot`.

## Platform Notes

- Primary target: Linux desktop.
- Burning and optical-drive detection rely on Linux tools (`lsblk`, `/dev/sr*`, `growisofs`/`wodim`).
- You can still build ISO files without burn tools.

## Dependencies

### Required

| Dependency | Why it is needed |
|---|---|
| Python 3.10+ | Runtime |
| PyQt6 | GUI |
| `dvda-author` | DVD-Audio authoring engine |
| `ffmpeg` | Conversion and media operations |
| `ffprobe` | Audio metadata probing |

### Optional

| Dependency | Why it is needed |
|---|---|
| `sox` | Higher-quality resampling path (used when possible) |
| `growisofs` | Burning ISO to DVD |
| `wodim` | Burning fallback tool |
| `eject` | Auto-eject support after successful burn |

## Install

### 1) Clone and set up Python env

```bash
git clone https://github.com/RecursiveIntell/Hootie.git
cd Hootie
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Install system tools

Example packages (Fedora/RHEL-family):

```bash
sudo dnf install ffmpeg sox dvd+rw-tools wodim util-linux eject
```

Example packages (Debian/Ubuntu-family):

```bash
sudo apt update
sudo apt install ffmpeg sox dvd+rw-tools wodim util-linux eject
```

Notes:
- `ffprobe` is usually bundled with `ffmpeg`.
- `util-linux` provides `lsblk` used for drive detection.

### 3) Install `dvda-author`

Hootie calls `dvda-author` directly from your `PATH`.

You have two common options:

1. Build/install from the upstream `dvda-author` source.
2. Build from a local `dvda-author` checkout and place the resulting binary on `PATH`.

Verify:

```bash
which dvda-author
dvda-author --version
```

If your build does not support `--version`, `which dvda-author` confirms only that an executable is on `PATH`. Use the app's preflight and a disposable ISO build to check authoring compatibility.

## Run

```bash
source .venv/bin/activate
python main.py
```

Open an existing project directly:

```bash
python main.py /path/to/project.hoot
```

## First Launch and Dependency Check

On first launch, Hootie shows a dependency screen and checks tool availability.

You can re-run this any time from:

- `Tools` -> `Check Dependencies...`

## Typical Workflow

1. Create a project or open an existing `.hoot` file.
2. Add tracks or folders.
3. Organize tracks into groups.
4. Choose disc type at the bottom gauge (`DVD-5`, `DVD-9`, `DVD-10`).
5. Build via `Tools` -> `Build DVD-Audio...` or `Ctrl+B`.
6. In the build wizard:
   - run preflight checks,
   - build structure/ISO,
   - optionally burn ISO to disc.

## Build and Conversion Behavior

- Non-native inputs are converted to WAV before authoring.
- Resampling/bit-depth conversion is applied based on project quality preset.
- Converted temporary files are cleaned automatically unless `keep_converted_files` is enabled in settings.
- Build cancel/close now stops workers and restores original track paths safely.

## Burning Behavior

- Burn tool priority: `growisofs` first, then `wodim`.
- Drive list is detected from `/dev/sr*`.
- Read-only drives are shown and blocked from start.
- Preferred drive and default speed are persisted.
- `verify_after_burn` is passed through when `wodim` is the active burn tool.
- Auto-eject after successful burn is supported when enabled and `eject` exists.

## Settings

Settings are stored at:

- `~/.config/hootie/settings.json`

Recent projects are stored at:

- `~/.config/hootie/recent.json`

Dependency check completion flag:

- `~/.config/hootie/deps_checked`

Key settings used by the app:

- `general.quality_preset`
- `general.temp_dir`
- `burning.default_speed`
- `burning.preferred_device`
- `burning.auto_eject`
- `conversion.sox_quality`
- `conversion.keep_converted_files`

## Project Files

Hootie project files use `.hoot` JSON format and include:

- project metadata,
- disc type,
- quality preset,
- groups,
- track metadata and source file paths.

## Keyboard Shortcuts

- `Ctrl+N`: New project
- `Ctrl+O`: Open project
- `Ctrl+S`: Save
- `Ctrl+Shift+S`: Save As
- `Ctrl+I`: Add files
- `Ctrl+Shift+I`: Add folder
- `Ctrl+G`: Add group
- `Ctrl+B`: Build DVD-Audio
- `Delete`: Remove selected tracks

## Development

### Quick validation

```bash
python -m compileall -q main.py app
```

There is currently no bundled automated test suite or pytest dependency. `compileall` checks Python syntax only. Validate conversion and ISO authoring using copies of your audio files; an optical burn and playback test are separate hardware checks. Higher-resolution presets cannot restore information missing from the source audio.

## Troubleshooting

### `dvda-author not found`

- Confirm binary is installed and executable.
- Ensure directory containing `dvda-author` is on `PATH`.
- Restart terminal/session after changing `PATH`.

### Import finds no valid tracks

- Confirm extensions are supported.
- Confirm `ffprobe` is installed and works:

```bash
ffprobe -version
```

### Conversion errors

- Confirm `ffmpeg` works:

```bash
ffmpeg -version
```

- If using SoX path, also verify:

```bash
sox --version
```

### Burn options disabled

- No writable optical drive detected, or
- Neither `growisofs` nor `wodim` is installed.

Check:

```bash
which growisofs
which wodim
ls /dev/sr*
```

### Permission issues during burn

- Ensure your user has permission to access optical devices.
- Depending on distro rules, you may need proper group membership or udev policy.

## License

This checkout does not contain a `LICENSE` file or a package manifest declaring a license.
