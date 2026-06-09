# 🎵 iPod Manager

A local web app for managing your 2008-era iPod Classic / Nano / Mini over USB.

## What it does
- Detects mounted iPods automatically (or set the path manually)
- Browses your full track library — sortable, searchable
- Drag-drop new audio files to add them
- Auto-converts non-native formats (FLAC, OGG, WMA, OPUS → AAC via FFmpeg)
- Removes tracks from the iPod
- Preserves all existing library data

---

## Requirements

### System packages

**Linux (Debian/Ubuntu):**
```bash
sudo apt install libgpod-dev libgpod4 ffmpeg python3-dev libsgutils2-dev
pip install gpod mutagen flask
```

**macOS (Homebrew):**
```bash
brew install libgpod ffmpeg
pip install gpod mutagen flask
```

**Windows:** libgpod is not well-supported on Windows. Recommend running in WSL2 (Ubuntu).

---

## Running the app

```bash
cd ipod-manager
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5050** in your browser.

---

## Connecting your iPod

1. Plug in the iPod via USB
2. On Linux: it should auto-mount under `/media/<username>/iPod` — check with `lsblk` or `df -h`
3. On macOS: it mounts at `/Volumes/iPod` (or whatever the iPod is named)
4. Click **Detect iPod** in the app, or paste the mount path manually

> ⚠️ Always **eject the iPod safely** after making changes (before unplugging).
> The app writes the iTunesDB on each add/delete — but the OS may still have disk writes cached.

---

## Supported input formats

| Format | Action |
|--------|--------|
| MP3    | Added as-is |
| M4A / AAC | Added as-is |
| WAV / AIFF | Added as-is |
| FLAC   | Converted to AAC 192k |
| OGG    | Converted to AAC 192k |
| WMA    | Converted to AAC 192k |
| OPUS   | Converted to AAC 192k |

---

## Troubleshooting

**"No iPod found"** — Check the mount path with `df -h` or `lsblk`. The iPod_Control folder must exist at the root.

**"Could not open iPod database"** — The iPod may need to be reset/restored via iTunes first if the database is corrupt.

**"gpod not found"** — You need `libgpod-dev` installed system-wide before `pip install gpod`.

**Conversion fails** — Make sure `ffmpeg` is installed: `ffmpeg -version`
