"""Builds the finale playlist: which clip plays at which moment of the song.

Pure logic, no database or HTTP: it only receives plain lists of dicts, so it is easy to test.
"""


def build_finale(turns: list[dict], recordings: list[dict]) -> list[dict]:
    """Combine the song's turns with the uploaded clips into a playlist in song order.

    turns:      one dict per turn, from the sessions domain, in ANY order, e.g.
                {"turn_id": 12, "position": 2, "start_ms": 6000, "end_ms": 12000}
    recordings: one dict per uploaded clip, from the recordings table, e.g.
                {"turn_id": 12, "file_name": "abc_12.webm", ...}
                Not every turn has a recording yet.

    Returns one dict per turn, sorted by "position" (1, 2, 3, ...), each shaped like:
        {"turn_id": 12, "position": 2, "start_ms": 6000, "end_ms": 12000,
         "clip_url": "/media/abc_12.webm"}
    If a turn has no recording yet, its "clip_url" is None.
    """
    # Step 1: lookup from turn_id -> file_name, so each turn finds its clip in one step
    files = {}
    for rec in recordings:
        files[rec["turn_id"]] = rec["file_name"]

    # Step 2: go through the turns in song order, building one output dict each
    result = []
    for turn in sorted(turns, key=lambda t: t["position"]):
        file_name = files.get(turn["turn_id"])  # None if this turn has no clip yet

        # Step 3: build the output dict and add it to the list
        result.append({
            "turn_id": turn["turn_id"],
            "position": turn["position"],
            "start_ms": turn["start_ms"],
            "end_ms": turn["end_ms"],
            "clip_url": "/media/" + file_name if file_name else None,
        })
    return result
