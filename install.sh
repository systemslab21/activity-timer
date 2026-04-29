#!/usr/bin/env bash
set -e

echo "=== Activity Timer installer ==="

# uv
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Python deps
echo "Installing Python dependencies..."
uv sync

# paplay (Linux / WSL2 only — needed for sound alerts)
if [[ "$OSTYPE" == "linux"* ]] && ! command -v paplay &>/dev/null; then
    echo "Installing paplay for audio support..."
    sudo apt-get install -y pulseaudio-utils
fi

echo ""
echo "Done. Run the app with:  ./run.sh"
