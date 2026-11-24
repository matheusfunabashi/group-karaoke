"""Built-in song catalog: mostly traditional, public-domain songs, plus Payphone (Maroon 5), which
is copyrighted and included only as a non-commercial class demo track.

Each song is split into one segment per line of lyrics, with the time the line starts and ends in
the backing track. Payphone's line times come from LRCLIB (lrclib.net), a public database of synced
lyrics: only its timestamps were used, matched in order to the lines already in seed.json. They
were timed on the original recording, but the backing track here is an instrumental remake, so
every line is shifted by +2780 ms: +1680 ms to put the first line on the remake's first beat
(1.98 s; both versions play at exactly 110 BPM, and the remake's section changes line up with the
chorus lines all through the song, so one constant shift fits), then +1100 ms more, about two
beats, measured by ear on the live site with the lyrics timing nudge (the singing starts that
much after the beat the first shift matched).

The data lives in seed.json (readable text, not a database file, see brief §7.11) and is loaded
into the database at every start by service.seed_catalog(): a song whose lines changed here is
added again and its old row retired, so sessions already sung keep the times they were sung with.
"""
import json
from pathlib import Path

SEED_FILE = Path(__file__).with_name("seed.json")

SONGS = [
    {**song, "segments": [(s["start_ms"], s["end_ms"], s["lyrics"]) for s in song["segments"]]}
    for song in json.loads(SEED_FILE.read_text())["songs"]
]
