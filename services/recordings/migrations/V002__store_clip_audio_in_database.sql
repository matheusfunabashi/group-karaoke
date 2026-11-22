-- V002: keep each clip's bytes in the database instead of the container's disk (ADR-7).
-- recordings already holds rows when this runs (on Azure it does), so the new column must
-- be NULL-able: rows saved before V002 keep all their details but have no audio here, because
-- their file was on a container disk that is gone once the app scales to zero. The service
-- treats audio IS NULL as "no clip to play" (clip_url null in the finale).
ALTER TABLE recordings ADD audio VARBINARY(MAX) NULL;
