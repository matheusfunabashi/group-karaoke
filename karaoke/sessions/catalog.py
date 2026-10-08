"""Built-in song catalog: traditional, public-domain songs only, so there are no licensing issues.

Each segment is (start_ms, end_ms, lyrics). Audio files live in static/audio/.
"""

SONGS = [
    {
        "title": "Row, Row, Row Your Boat",
        "artist": "Traditional",
        "audio_file": "audio/row-your-boat.mp3",
        "duration_ms": 24000,
        "segments": [
            (0, 6000, "Row, row, row your boat, gently down the stream"),
            (6000, 12000, "Merrily, merrily, merrily, merrily"),
            (12000, 18000, "Life is but a dream"),
            (18000, 24000, "Row, row, row your boat (all together!)"),
        ],
    },
    {
        "title": "Twinkle, Twinkle, Little Star",
        "artist": "Traditional",
        "audio_file": "audio/twinkle-twinkle.mp3",
        "duration_ms": 30000,
        "segments": [
            (0, 7500, "Twinkle, twinkle, little star, how I wonder what you are"),
            (7500, 15000, "Up above the world so high, like a diamond in the sky"),
            (15000, 22500, "Twinkle, twinkle, little star"),
            (22500, 30000, "How I wonder what you are"),
        ],
    },
]
