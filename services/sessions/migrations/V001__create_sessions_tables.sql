-- V001: the sessions domain's tables (the same ones the SQLite schema had in Assignment 1).
-- Session ids are random and case-sensitive ("aB3x" and "ab3X" are different sessions), so
-- they use a binary collation; SQL Server's default collation ignores case.

CREATE TABLE songs (
    id          INT IDENTITY(1, 1) PRIMARY KEY,
    title       NVARCHAR(200) NOT NULL,
    artist      NVARCHAR(200) NOT NULL,
    audio_file  NVARCHAR(200) NOT NULL,
    duration_ms INT NOT NULL
);

CREATE TABLE song_segments (
    id       INT IDENTITY(1, 1) PRIMARY KEY,
    song_id  INT NOT NULL REFERENCES songs (id),
    position INT NOT NULL,
    start_ms INT NOT NULL,
    end_ms   INT NOT NULL,
    lyrics   NVARCHAR(MAX) NOT NULL,
    CONSTRAINT uq_song_segments_position UNIQUE (song_id, position)
);

CREATE TABLE sessions (
    id         VARCHAR(16) COLLATE Latin1_General_100_BIN2 PRIMARY KEY,
    song_id    INT NOT NULL REFERENCES songs (id),
    host_name  NVARCHAR(30) NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'open'
               CONSTRAINT ck_sessions_status CHECK (status IN ('open', 'complete')),
    created_at DATETIME2(0) NOT NULL  -- UTC
);

CREATE TABLE participants (
    id           INT IDENTITY(1, 1) PRIMARY KEY,
    session_id   VARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL REFERENCES sessions (id),
    display_name NVARCHAR(30) NOT NULL,
    joined_at    DATETIME2(0) NOT NULL,  -- UTC
    CONSTRAINT uq_participants_name UNIQUE (session_id, display_name)
);

CREATE TABLE turns (
    id             INT IDENTITY(1, 1) PRIMARY KEY,
    session_id     VARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL REFERENCES sessions (id),
    segment_id     INT NOT NULL REFERENCES song_segments (id),
    participant_id INT NULL REFERENCES participants (id),
    status         VARCHAR(20) NOT NULL DEFAULT 'pending'
                   CONSTRAINT ck_turns_status CHECK (status IN ('pending', 'assigned', 'recorded')),
    CONSTRAINT uq_turns_segment UNIQUE (session_id, segment_id)
);
