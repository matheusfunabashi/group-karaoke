"""Built-in song catalog: mostly traditional, public-domain songs, plus Payphone (Maroon 5), which
is copyrighted and included only as a non-commercial class demo track.

Each song is split into one segment per line of lyrics, with the time the line starts and ends in
the backing track. Payphone's line times come from LRCLIB (lrclib.net), a public database of synced
lyrics: only its timestamps were used, matched in order to the lines already in seed.json.

The data lives in seed.json (readable text, not a database file, see brief §7.11) and is
loaded into the database on first boot by service.seed_catalog(), only when the songs table is empty.
"""
import json
from pathlib import Path

SEED_FILE = Path(__file__).with_name("seed.json")

SONGS = [
    {**song, "segments": [(s["start_ms"], s["end_ms"], s["lyrics"]) for s in song["segments"]]}
    for song in json.loads(SEED_FILE.read_text())["songs"]
]
