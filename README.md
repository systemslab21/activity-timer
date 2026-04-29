# Activity Timer

Pomodoro-style sit/stand reminder. Counts down a configurable sitting period, then prompts you to move, then cycles back.

Default: **30 min sitting → 5 min active**, repeating.

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- **Linux / WSL2:** `paplay` for sound (`pulseaudio-utils` package)
- **Windows:** Python with uv installed; sound uses `paplay` if available

## Install

```bash
./install.sh
```

This installs uv (if missing), syncs Python dependencies, and installs `paplay` on Linux/WSL2.

## Run

```bash
./run.sh
```

On WSL2 the script sets `DISPLAY=:0` automatically if no display is configured.

## Usage

| Control | Action |
|---|---|
| **Start / Stop** | Begin or pause the countdown |
| **Reset** | Return to the start of the sitting period |
| **Settings** | Change sit/active durations and toggle sound |
| `Space` | Start / Stop |
| `R` or `Esc` | Reset |

When a period ends the window raises to the front, the title flashes, and two tones play (high = time to move, low = back to sitting).
