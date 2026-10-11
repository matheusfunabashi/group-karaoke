from karaoke.recordings.finale import build_finale

TURNS = [
    {"turn_id": 12, "position": 2, "start_ms": 6000, "end_ms": 12000},
    {"turn_id": 11, "position": 1, "start_ms": 0, "end_ms": 6000},
    {"turn_id": 13, "position": 3, "start_ms": 12000, "end_ms": 18000},
]


def test_playlist_is_in_song_order():
    playlist = build_finale(TURNS, [])
    assert [item["position"] for item in playlist] == [1, 2, 3]
    assert [item["turn_id"] for item in playlist] == [11, 12, 13]


def test_each_item_keeps_its_timing():
    first = build_finale(TURNS, [])[0]
    assert (first["start_ms"], first["end_ms"]) == (0, 6000)


def test_recorded_turns_get_a_clip_url_and_missing_ones_get_none():
    recordings = [
        {"turn_id": 13, "file_name": "abc_13.webm"},
        {"turn_id": 11, "file_name": "abc_11.m4a"},
    ]
    playlist = build_finale(TURNS, recordings)
    assert [item["clip_url"] for item in playlist] == [
        "/media/abc_11.m4a",
        None,
        "/media/abc_13.webm",
    ]


def test_output_has_exactly_these_keys():
    item = build_finale(TURNS, [])[0]
    assert set(item) == {"turn_id", "position", "start_ms", "end_ms", "clip_url"}


def test_empty_song_gives_empty_playlist():
    assert build_finale([], []) == []
