#!/bin/zsh
# One-time setup. Double-click this once, then use start.command from then on.
cd "$(dirname "$0")" || exit 1

echo ""
echo "  Setting up the Tamil transcriber."
echo "  This runs once and needs an internet connection."
echo ""

PY=$(command -v python3)
if [ -z "$PY" ]; then
  echo "  ERROR: python3 was not found on this Mac."
  echo "  Install it from python.org, then run this again."
  echo ""
  read "?  Press Return to close."
  exit 1
fi

echo "  [1/3] Creating a private Python environment..."
"$PY" -m venv .venv || { echo "  Could not create the environment."; read "?  Press Return."; exit 1; }

echo "  [2/3] Installing yt-dlp and Whisper (about 250 MB)..."
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet faster-whisper yt-dlp || {
  echo "  Install failed. Check your internet connection and try again."
  read "?  Press Return."; exit 1
}

# The xet transfer backend stalls on this machine; force plain HTTP.
export HF_HUB_DISABLE_XET=1

echo "  [3/3] Downloading the Whisper medium model (about 1.5 GB)."
echo "        This is the slow part. Leave it running."
./.venv/bin/python -c "
from faster_whisper import WhisperModel
WhisperModel('medium', device='cpu', compute_type='int8')
print('        Model ready.')
" || { echo "  Model download failed."; read "?  Press Return."; exit 1; }

echo ""
echo "  Done. From now on, double-click start.command."
echo ""
read "?  Press Return to close."
