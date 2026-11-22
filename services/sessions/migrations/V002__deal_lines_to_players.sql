-- V002: each turn is now one line of the song, dealt to the players in rotation when the
-- host starts the session (instead of one long part that a player picks).
-- Both tables already hold data on Azure, so both new columns have a default for old rows.

-- A song whose lines changed in seed.json is inserted again as a new row and the old row is
-- retired: sessions already sung on the old parts keep them, new sessions get the new lines.
ALTER TABLE songs ADD retired BIT NOT NULL CONSTRAINT df_songs_retired DEFAULT 0;

-- When the line count doesn't divide by the number of players, some neighbouring lines are
-- merged into one turn: the turn starts at segment_id and covers segment_count lines.
-- Existing turns cover exactly one part.
ALTER TABLE turns ADD segment_count INT NOT NULL CONSTRAINT df_turns_segment_count DEFAULT 1;
