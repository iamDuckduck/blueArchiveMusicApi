-- Keep canonical display names and song links intact. Older combined names are
-- not split heuristically; reviewed imports can fill these nullable fields.
ALTER TABLE artist ADD COLUMN character_name VARCHAR(255);
ALTER TABLE artist ADD COLUMN voice_actor_name VARCHAR(255);

CREATE TABLE artist_alias (
    artist_id INTEGER NOT NULL REFERENCES artist(id) ON DELETE CASCADE,
    alias VARCHAR(255) NOT NULL,
    PRIMARY KEY (artist_id, alias)
);
