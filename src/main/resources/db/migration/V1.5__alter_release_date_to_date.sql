ALTER TABLE album
ALTER COLUMN release_date TYPE date
USING release_date::date;