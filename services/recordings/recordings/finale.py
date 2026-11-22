"""Builds the finale playlist: which clip plays at which moment of the song.

Pure logic, no database or HTTP: it only receives plain lists of dicts, so it is easy to test.
"""


def build_finale(turns: list[dict], recordings: list[dict]) -> list[dict]:
    """Combine the song's turns with the uploaded clips into a playlist in song order.

    turns:      one dict per turn, from the sessions domain, in ANY order, e.g.
                {"turn_id": 12, "position": 2, "start_ms": 6000, "end_ms": 12000}
    recordings: one dict per uploaded clip, from the recordings table, e.g.
                {"id": 5, "turn_id": 12, "has_audio": True, ...}
                Not every turn has a recording yet.

    Returns one dict per turn, sorted by "position" (1, 2, 3, ...), each shaped like:
        {"turn_id": 12, "position": 2, "start_ms": 6000, "end_ms": 12000,
         "clip_url": "/api/recordings/5/audio"}
    If a turn has no recording yet (or one saved before clips were kept in the database,
    so with no audio), its "clip_url" is None.
    """
    # Step 1: lookup from turn_id -> recording id, so each turn finds its clip in one step
    clips = {}
    for rec in recordings:
        if rec["has_audio"]:
            clips[rec["turn_id"]] = rec["id"]

    # Step 2: go through the turns in song order, building one output dict each
    result = []
    for turn in sorted(turns, key=lambda t: t["position"]):
        clip_id = clips.get(turn["turn_id"])  # None if this turn has no clip yet

        # Step 3: build the output dict and add it to the list
        result.append({
            "turn_id": turn["turn_id"],
            "position": turn["position"],
            "start_ms": turn["start_ms"],
            "end_ms": turn["end_ms"],
            "clip_url": f"/api/recordings/{clip_id}/audio" if clip_id else None,
        })
    return result
