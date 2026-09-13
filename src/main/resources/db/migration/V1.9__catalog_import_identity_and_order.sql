ALTER TABLE album
    ADD COLUMN cover_original_path VARCHAR(255),
    ADD COLUMN cover_400_path VARCHAR(255),
    ADD COLUMN cover_800_path VARCHAR(255),
    ADD COLUMN import_source VARCHAR(64),
    ADD COLUMN source_album_id VARCHAR(255);

ALTER TABLE album ALTER COLUMN description TYPE TEXT;

CREATE UNIQUE INDEX uq_album_import_identity
    ON album (import_source, source_album_id)
    WHERE import_source IS NOT NULL AND source_album_id IS NOT NULL;

ALTER TABLE song
    ADD COLUMN disc_number INTEGER,
    ADD COLUMN track_number INTEGER,
    ADD COLUMN import_source VARCHAR(64),
    ADD COLUMN source_track_id VARCHAR(255),
    ADD COLUMN music_kind VARCHAR(32);

ALTER TABLE song ALTER COLUMN description TYPE TEXT;

CREATE UNIQUE INDEX uq_song_import_identity
    ON song (album_id, import_source, source_track_id)
    WHERE import_source IS NOT NULL AND source_track_id IS NOT NULL;

ALTER TABLE song_artist DROP CONSTRAINT IF EXISTS song_artist_type_check;
