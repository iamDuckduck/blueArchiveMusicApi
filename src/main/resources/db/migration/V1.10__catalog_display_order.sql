-- Preserve existing album order without inventing official disc/track numbers.
ALTER TABLE song ADD COLUMN display_order INTEGER CHECK (display_order > 0);

WITH ordered AS (
    SELECT id, ROW_NUMBER() OVER (
        PARTITION BY album_id ORDER BY disc_number ASC NULLS LAST, track_number ASC NULLS LAST, id ASC
    ) AS position
    FROM song
)
UPDATE song SET display_order = ordered.position
FROM ordered WHERE song.id = ordered.id;
