#!/bin/bash

# ── iPod Manager Installer ─────────────────────────────────────────────────
# Double-click this file to install everything needed to run iPod Manager.
# This installs: Homebrew, Python 3, FFmpeg, and all required packages.
# Nothing is sent to the internet except to download these free tools.
# ──────────────────────────────────────────────────────────────────────────

clear
echo ""
echo "  🎵  iPod Manager — Installer"
echo "  ─────────────────────────────────────────────"
echo ""
echo "  This will install:"
echo "    • Homebrew (free Mac package manager)"
echo "    • Python 3 (free)"
echo "    • FFmpeg (free audio converter)"
echo "    • Flask, Mutagen, yt-dlp (free Python tools)"
echo ""
echo "  Your Mac password may be required once."
echo "  This takes about 3–5 minutes."
echo ""
read -p "  Press Enter to start, or Ctrl+C to cancel..."
echo ""

# ── Step 1: Homebrew ───────────────────────────────────────────────────────
echo "  [1/4] Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

if ! command -v brew &>/dev/null; then
    echo "  → Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add to PATH for Apple Silicon
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    fi
else
    echo "  ✓ Homebrew already installed"
fi

# ── Step 2: Python ─────────────────────────────────────────────────────────
echo ""
echo "  [2/4] Checking Python 3..."
if ! command -v python3 &>/dev/null || [ "$(/usr/bin/python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f2)" -lt 10 ]; then
    echo "  → Installing Python 3..."
    brew install python3
    # Refresh PATH
    export PATH="/opt/homebrew/bin:$PATH"
else
    echo "  ✓ Python 3 already installed"
fi

PYTHON=$(command -v python3 || echo /opt/homebrew/bin/python3)
PIP="$PYTHON -m pip"

# ── Step 3: FFmpeg ─────────────────────────────────────────────────────────
echo ""
echo "  [3/4] Checking FFmpeg..."
if ! command -v ffmpeg &>/dev/null; then
    echo "  → Installing FFmpeg (this may take a few minutes)..."
    brew install ffmpeg
else
    echo "  ✓ FFmpeg already installed"
fi

# ── Step 4: Python packages ────────────────────────────────────────────────
echo ""
echo "  [4/4] Installing Python packages..."
$PIP install --upgrade flask mutagen yt-dlp --break-system-packages -q
echo "  ✓ Packages installed"

# ── Done ───────────────────────────────────────────────────────────────────
echo ""
echo "  ─────────────────────────────────────────────"
echo "  ✅  Installation complete!"
echo ""
echo "  To use iPod Manager:"
echo "    1. Plug in your iPod via USB"
echo "    2. Double-click 'iPod Manager.app'"
echo "    3. Your browser will open automatically"
echo "    4. Click 'Detect iPod' or enter /Volumes/YourIpodName"
echo ""
echo "  Press Enter to close this window."
read
