-- V001: the recordings domain's table (the same one the SQLite schema had in Assignment 1).
-- turn_id and session_id point at the sessions service's data but deliberately have no
-- FOREIGN KEY: that data lives in another database (ADR-3). session_id uses the same
-- case-sensitive collation as sessions.id there.

CREATE TABLE recordings (
    id           INT IDENTITY(1, 1) PRIMARY KEY,
    turn_id      INT NOT NULL CONSTRAINT uq_recordings_turn UNIQUE,
    session_id   VARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL,
    file_name    NVARCHAR(100) NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    size_bytes   INT NOT NULL,
    created_at   DATETIME2(0) NOT NULL  -- UTC
);

CREATE INDEX idx_recordings_session ON recordings (session_id);
