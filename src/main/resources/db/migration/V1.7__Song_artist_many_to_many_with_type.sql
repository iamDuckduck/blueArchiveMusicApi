-- Migrate existing artist_id / composer_id data into the new join table,
-- then drop the old FK columns.

-- 1. Create join table
CREATE TABLE song_artist (
    song_id    INTEGER NOT NULL,
    artist_id  INTEGER NOT NULL,
    type       VARCHAR(20) NOT NULL,  -- 'ARTIST' or 'COMPOSER'
    created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (song_id, artist_id, type),
    FOREIGN KEY (song_id)   REFERENCES song(id)   ON DELETE CASCADE,
    FOREIGN KEY (artist_id) REFERENCES artist(id)  ON DELETE CASCADE
);

-- 2. Migrate existing rows (skip NULLs)
INSERT INTO song_artist (song_id, artist_id, type)
SELECT id, artist_id, 'ARTIST'
FROM song
WHERE artist_id IS NOT NULL;

INSERT INTO song_artist (song_id, artist_id, type)
SELECT id, composer_id, 'COMPOSER'
FROM song
WHERE composer_id IS NOT NULL
ON CONFLICT DO NOTHING;  -- in case artist_id == composer_id for the same song

-- 3. Drop old FK constraints and columns
ALTER TABLE song DROP CONSTRAINT IF EXISTS fk_song_artist;
ALTER TABLE song DROP CONSTRAINT IF EXISTS fk_song_composer;
ALTER TABLE song DROP COLUMN IF EXISTS artist_id;
ALTER TABLE song DROP COLUMN IF EXISTS composer_id;

