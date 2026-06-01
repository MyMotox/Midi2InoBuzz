# MidiBuzz
Convert MIDI files into Arduino sketches that play on a passive buzzer using `tone()`.

## Features
- Convert a single track or auto-pick a melody track.
- Optional skyline mode (merge all tracks and keep the highest note).
- Compact `.ino` output with configurable line width.

## Requirements
- Python 3.9+
- `mido` (`python -m pip install mido`)

## Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install mido

python MidiConvert.py -i song.mid -o song.ino
```

## Common commands
List tracks:
```bash
python MidiConvert.py -i song.mid --list-tracks
```

Pick a specific track:
```bash
python MidiConvert.py -i song.mid -o song.ino --track 1
```

## Output and wiring
- The sketch uses `tone()` on the buzzer pin (default pin 8).
- Wire the buzzer `+` to the pin and `-` to GND.

## Options
- `--pin`: buzzer pin (default 8)
- `--track`: index of the track to extract
- `--all-tracks`: skyline mode (merge all tracks)
- `--list-tracks`: print track info and exit
- `--per-line`: array values per line in the output (default 16)

## Troubleshooting
- **no sound**: make sure the buzzer is passive and wired to the right pin.
- **sketch too big**: use a shorter MIDI or a simpler track.
