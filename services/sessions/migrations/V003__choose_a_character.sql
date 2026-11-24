-- V003: every singer picks one of the six pixel-art characters (ui/characters.js draws them).
-- Their character sits at the table in the karaoke room and stands up with the mic on their lines.
-- participants already holds data on Azure, so the new column has a default for the old rows.
-- (The column is called avatar: CHARACTER is a reserved word in SQL.)
ALTER TABLE participants ADD avatar TINYINT NOT NULL
    CONSTRAINT df_participants_avatar DEFAULT 1
    CONSTRAINT ck_participants_avatar CHECK (avatar BETWEEN 1 AND 6);
GO
-- People who joined before characters existed get them in turn instead of all getting character 1,
-- so an old session's room isn't a row of twins. (Its own batch: SQL Server checks a whole batch
-- before running any of it, and before the ALTER above has run the column doesn't exist.)
UPDATE participants SET avatar = id % 6 + 1;
