CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX idx_song_title_trgm
    ON song
    USING GIN (title gin_trgm_ops);

CREATE INDEX idx_album_title_trgm
    ON album
    USING GIN (title gin_trgm_ops);
