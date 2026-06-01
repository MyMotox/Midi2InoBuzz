"""Convert a MIDI file into an Arduino sketch (.ino) for a passive buzzer.

Usage:
    python3 MidiConvert.py -i song.mid --list-tracks
    python3 MidiConvert.py -i song.mid -o song.ino --track 1
    python3 MidiConvert.py -i song.mid -o song.ino --per-line 24
"""

import argparse
import mido


GM_INSTRUMENTS = [
    "Acoustic Grand Piano", "Bright Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba", "Xylophone",
    "Tubular Bells", "Dulcimer", "Drawbar Organ", "Percussive Organ", "Rock Organ",
    "Church Organ", "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    "Nylon Guitar", "Steel Guitar", "Jazz Guitar", "Clean Electric Guitar",
    "Muted Electric Guitar", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    "Acoustic Bass", "Fingered Bass", "Picked Bass", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    "Violin", "Viola", "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings",
    "Orchestral Harp", "Timpani", "String Ensemble 1", "String Ensemble 2",
    "Synth Strings 1", "Synth Strings 2", "Choir Aahs", "Voice Oohs",
    "Synth Voice", "Orchestra Hit", "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
    "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
    "Oboe", "English Horn", "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi",
    "Whistle", "Ocarina", "Square Lead", "Saw Lead", "Calliope Lead", "Chiff Lead",
    "Charang Lead", "Voice Lead", "Fifths Lead", "Bass + Lead",
    "New Age Pad", "Warm Pad", "Polysynth Pad", "Choir Pad", "Bowed Pad",
    "Metallic Pad", "Halo Pad", "Sweep Pad", "Rain FX", "Soundtrack FX",
    "Crystal FX", "Atmosphere FX", "Brightness FX", "Goblins FX", "Echoes FX",
    "Sci-fi FX", "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bagpipe",
    "Fiddle", "Shanai", "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
    "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal", "Guitar Fret Noise",
    "Breath Noise", "Seashore", "Bird Tweet", "Telephone Ring", "Helicopter",
    "Applause", "Gunshot",
]


def midi_to_freq(note: int) -> int:
    return int(round(440.0 * (2.0 ** ((note - 69) / 12.0))))


def analyze_tracks(midi_path: str):
    """Renvoie une liste de dicts decrivant chaque piste."""
    mid = mido.MidiFile(midi_path)
    infos = []
    for idx, track in enumerate(mid.tracks):
        name = ""
        program = None
        notes = []
        channels = set()
        is_drums = False
        for msg in track:
            if msg.type == "track_name":
                name = msg.name
            elif msg.type == "program_change":
                program = msg.program
            elif msg.type == "note_on" and msg.velocity > 0:
                notes.append(msg.note)
                channels.add(msg.channel)
                if msg.channel == 9:
                    is_drums = True
        infos.append({
            "index": idx,
            "name": name,
            "program": program,
            "instrument": GM_INSTRUMENTS[program] if program is not None and program < 128 else "",
            "note_count": len(notes),
            "mean_pitch": sum(notes) / len(notes) if notes else 0.0,
            "min_pitch": min(notes) if notes else None,
            "max_pitch": max(notes) if notes else None,
            "channels": sorted(channels),
            "is_drums": is_drums,
        })
    return infos


def list_tracks(midi_path: str):
    infos = analyze_tracks(midi_path)
    print(f"Pistes de {midi_path} :")
    print(f"{'#':>2}  {'Notes':>6}  {'Moy':>4}  {'Min':>4}  {'Max':>4}  Nom / Instrument")
    print("-" * 70)
    for info in infos:
        flag = " [DRUMS]" if info["is_drums"] else ""
        label = info["name"] or info["instrument"] or "(sans nom)"
        if info["note_count"] == 0:
            print(f"{info['index']:>2}  {'-':>6}  {'-':>4}  {'-':>4}  {'-':>4}  {label} (vide / meta)")
        else:
            print(f"{info['index']:>2}  {info['note_count']:>6}  "
                  f"{info['mean_pitch']:>4.0f}  {info['min_pitch']:>4}  {info['max_pitch']:>4}  "
                  f"{label}{flag}")


def pick_melody_track(infos):
    """Heuristique pour trouver la melodie principale:
    1) Si un nom de piste evoque la melodie ("melod", "lead", "voice", "vocal",
       "song", "main"), on prend celui-la.
    2) Sinon, parmi les pistes avec assez de notes (>= 20% du max),
       on prend celle de hauteur moyenne la plus elevee.
    """
    candidates = [i for i in infos if i["note_count"] > 0 and not i["is_drums"]]
    if not candidates:
        return None

    KEYWORDS = ("melod", "lead", "voice", "vocal", "song", "main", "chant")
    for info in candidates:
        name_lc = (info["name"] or "").lower()
        if any(kw in name_lc for kw in KEYWORDS):
            return info["index"]

    max_count = max(i["note_count"] for i in candidates)
    threshold = max(20, int(max_count * 0.2))
    substantial = [i for i in candidates if i["note_count"] >= threshold]
    substantial.sort(key=lambda i: i["mean_pitch"], reverse=True)
    return substantial[0]["index"] if substantial else candidates[0]["index"]


def extract_segments(midi_path: str, track_index=None):
    """Renvoie une liste de (frequence_Hz, duree_ms).

    Si `track_index` est fourni, seules les notes de cette piste sont prises
    en compte (le tempo reste partage entre toutes les pistes). Sinon, toutes
    les pistes sont fusionnees et on garde la note la plus aigue (skyline).
    """
    mid = mido.MidiFile(midi_path)
    ticks_per_beat = mid.ticks_per_beat
    tempo = 500000

    events = []  # (time_seconds, type, note)

    if track_index is None:
        # Mode skyline: toutes les pistes fusionnees.
        abs_seconds = 0.0
        for msg in mido.merge_tracks(mid.tracks):
            abs_seconds += mido.tick2second(msg.time, ticks_per_beat, tempo)
            if msg.type == "set_tempo":
                tempo = msg.tempo
            elif msg.type == "note_on" and msg.velocity > 0 and msg.channel != 9:
                events.append((abs_seconds, "on", msg.note))
            elif (msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0)) and msg.channel != 9:
                events.append((abs_seconds, "off", msg.note))
    else:
        # Mode piste unique: parcourt TOUTES les pistes pour suivre le tempo,
        # mais ne retient que les notes de la piste cible.
        # On utilise un parcours synchronise via les ticks absolus.
        per_track = []
        for idx, track in enumerate(mid.tracks):
            t = 0
            track_events = []
            for msg in track:
                t += msg.time
                track_events.append((t, idx, msg))
            per_track.append(track_events)

        # Fusion par tick absolu, stable.
        merged = []
        for evs in per_track:
            merged.extend(evs)
        merged.sort(key=lambda e: e[0])

        cur_tick = 0
        cur_seconds = 0.0
        for tick, idx, msg in merged:
            dt = tick - cur_tick
            cur_seconds += mido.tick2second(dt, ticks_per_beat, tempo)
            cur_tick = tick
            if msg.type == "set_tempo":
                tempo = msg.tempo
                continue
            if idx != track_index:
                continue
            if msg.type == "note_on" and msg.velocity > 0:
                events.append((cur_seconds, "on", msg.note))
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                events.append((cur_seconds, "off", msg.note))

    # Construire les segments (note la plus aigue active).
    segments = []
    active = set()
    last_time = 0.0
    last_freq = 0
    for time, typ, note in events:
        dur_ms = int(round((time - last_time) * 1000))
        if dur_ms > 0:
            segments.append([last_freq, dur_ms])
        if typ == "on":
            active.add(note)
        else:
            active.discard(note)
        last_freq = midi_to_freq(max(active)) if active else 0
        last_time = time

    # Fusion des segments consecutifs identiques.
    merged_seg = []
    for freq, dur in segments:
        if merged_seg and merged_seg[-1][0] == freq:
            merged_seg[-1][1] += dur
        else:
            merged_seg.append([freq, dur])

    while merged_seg and merged_seg[0][0] == 0:
        merged_seg.pop(0)
    while merged_seg and merged_seg[-1][0] == 0:
        merged_seg.pop()

    return merged_seg


def format_array(values, per_line=16):
    if not values:
        return ""
    lines = []
    for i in range(0, len(values), per_line):
        chunk = values[i:i + per_line]
        line = "  " + ", ".join(str(v) for v in chunk)
        if i + per_line < len(values):
            line += ","
        lines.append(line)
    return "\n".join(lines)


def build_sketch(segments, buzzer_pin: int, per_line: int) -> str:
    freqs = [min(s[0], 65535) for s in segments]
    durs = [max(1, min(s[1], 65535)) for s in segments]
    note_count = len(segments)

    lines = []
    lines.append("#ifdef __AVR__")
    lines.append("  #include <avr/pgmspace.h>")
    lines.append("#endif")
    lines.append("")

    lines.append(f"const int buzzerPin = {buzzer_pin};")
    lines.append(f"const int noteCount = {note_count};")
    lines.append("")

    lines.append("const uint16_t notes[noteCount] PROGMEM = {")
    lines.append(format_array(freqs, per_line))
    lines.append("};")
    lines.append("")

    lines.append("const uint16_t durations[noteCount] PROGMEM = {")
    lines.append(format_array(durs, per_line))
    lines.append("};")
    lines.append("")

    lines.append("void setup() {")
    lines.append("  pinMode(buzzerPin, OUTPUT);")
    lines.append("}")
    lines.append("")
    lines.append("void loop() {")
    lines.append("  for (int i = 0; i < noteCount; i++) {")
    lines.append("    uint16_t freq = pgm_read_word(&notes[i]);")
    lines.append("    uint16_t dur = pgm_read_word(&durations[i]);")
    lines.append("    if (freq > 0) {")
    lines.append("      tone(buzzerPin, freq, dur);")
    lines.append("    }")
    lines.append("    delay(dur);")
    lines.append("    noTone(buzzerPin);")
    lines.append("  }")
    lines.append("  delay(1500);")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Convertit un MIDI en sketch Arduino pour buzzer.")
    parser.add_argument("-i", "--input", required=True, help="Fichier MIDI d'entree (.mid)")
    parser.add_argument("-o", "--output", default="song.ino", help="Sketch genere (defaut: song.ino)")
    parser.add_argument("--pin", type=int, default=8, help="Broche du buzzer (defaut: 8)")
    parser.add_argument("--per-line", type=int, default=16, help="Valeurs par ligne dans les tableaux (defaut: 16)")
    parser.add_argument("--list-tracks", action="store_true",
                        help="Affiche les pistes du MIDI et quitte (utile pour choisir --track)")
    parser.add_argument("--track", type=int, default=None,
                        help="Index de la piste a extraire. Sans cette option, choix automatique "
                             "(piste de hauteur moyenne la plus elevee = melodie probable).")
    parser.add_argument("--all-tracks", action="store_true",
                        help="Mode skyline: fusionne toutes les pistes et garde la note la plus aigue.")
    args = parser.parse_args()

    if args.per_line < 1:
        parser.error("--per-line must be >= 1")

    if args.list_tracks:
        list_tracks(args.input)
        return

    # Choix de la piste.
    if args.all_tracks:
        track_index = None
        print("Mode: toutes les pistes fusionnees (skyline)")
    elif args.track is not None:
        track_index = args.track
        print(f"Mode: piste {track_index} uniquement")
    else:
        infos = analyze_tracks(args.input)
        track_index = pick_melody_track(infos)
        if track_index is None:
            print("Aucune piste melodique trouvee, fallback sur skyline.")
        else:
            info = infos[track_index]
            label = info["name"] or info["instrument"] or "(sans nom)"
            print(f"Piste auto: #{track_index} - {label} "
                  f"(moy={info['mean_pitch']:.0f}, {info['note_count']} notes)")

    segments = extract_segments(args.input, track_index=track_index)

    sketch = build_sketch(segments, args.pin, per_line=args.per_line)
    with open(args.output, "w") as f:
        f.write(sketch)

    flash_bytes = len(segments) * 4
    print(f"OK -> {args.output}")
    print(f"   {len(segments)} notes, ~{flash_bytes} octets de flash pour les tableaux")
    if flash_bytes > 28000:
        print("   ATTENTION: depasse la flash de l'Arduino Uno (~30 Ko).")


if __name__ == "__main__":
    main()
