#!/usr/bin/env bash
# One-command launcher: sets up a virtual environment, installs
# dependencies (first run only), and starts the full app.
# Usage:  ./run.sh
set -e
cd "$(dirname "$0")/backend"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment (first run only)..."
  python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies (first run only, this can take a few minutes)..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

if ! command -v ffmpeg &> /dev/null; then
  echo ""
  echo "WARNING: ffmpeg is not installed. Video/audio processing will fail."
  echo "  Ubuntu/Debian: sudo apt install ffmpeg"
  echo "  Mac:           brew install ffmpeg"
  echo ""
fi

echo ""
echo "Starting Nativox — open http://127.0.0.1:8000 in your browser"
echo ""
uvicorn main:app --reload --host 127.0.0.1 --port 8000
