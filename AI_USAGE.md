# AI Usage Log

| Date/commit | Tool | Prompt | Disposition (Accepted/Modified/Rejected) | What changed & why (if modified) | In my own words, how this works |
|---|---|---|---|---|---|
| 2026-10-06 | Claude Code | "Explain the assignment brief" then "Assess my group karaoke idea" | Modified | Kept the asynchronous-turns version and dropped live/real-time singing, since WebRTC/WebSockets would be too complex. Chose client-side finale playback over server-side ffmpeg rendering. | _TODO: write in your own words_ |
| 2026-10-06 | Claude Code | "Scaffold the project and write the first ADR" | _TODO_ | _TODO_ | _TODO: e.g. how `load_settings()` reads `PORT`/`DATA_DIR`, how `create_app()` calls `init_db()` and mounts the two routers, how `db.DOMAIN_SCHEMAS` lets each domain own its tables_ |
| 2026-10-08 (577aa55) | Claude Code | "Start the project": sessions schema + repository + tests, ADR-2 | _TODO_ | _TODO_ | _TODO: e.g. why `turns.participant_id` is nullable, what `UNIQUE (session_id, segment_id)` prevents, why queries use `?` placeholders_ |
| 2026-10-08 | Claude Code | Sessions business logic (`service.py`), routes and song catalog | _TODO_ | _TODO_ | _TODO: e.g. how `create_session()` builds one turn per segment inside one `with conn:` transaction, how `mark_turn_recorded()` completes the session, how `_call()` maps `NotFound`/`Conflict` to 404/409_ |
