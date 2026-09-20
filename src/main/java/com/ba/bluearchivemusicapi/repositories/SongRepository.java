package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.Song;
import com.ba.bluearchivemusicapi.repositories.projection.SongSearchProjection;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface SongRepository extends JpaRepository<Song, Long> {
    Optional<Song> findByAlbumIdAndImportSourceAndSourceTrackId(
            Long albumId, String importSource, String sourceTrackId);

    @org.springframework.data.jpa.repository.Lock(jakarta.persistence.LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT s FROM Song s WHERE s.album.id = :albumId AND s.importSource = :source AND s.sourceTrackId = :identity")
    Optional<Song> findImportForUpdate(Long albumId, String source, String identity);

    @Modifying
    @Query("UPDATE Song s SET s.playCount = COALESCE(s.playCount, 0) + 1 WHERE s.id = :id")
    int incrementPlayCount(@Param("id") Long id);

    @Query("SELECT s FROM Song s ORDER BY random()")
    List<Song> findRandomSong(Pageable pageable);

    // Credit matches stay attached to this song. EXISTS includes every role without duplicate result rows.
    @Query(value = """
            SELECT
                s.id,
                s.title,
                s.image_path AS "imagePath",
                s.audio_path AS "audioPath",
                a.id AS "albumId",
                a.title AS "albumTitle"
            FROM song s
            JOIN album a ON a.id = s.album_id
            WHERE s.title ILIKE :query || '%'
               OR s.title % :query
               OR a.title ILIKE :query || '%'
               OR a.title % :query
               OR EXISTS (
                   SELECT 1
                   FROM song_artist sa
                   JOIN artist ar ON ar.id = sa.artist_id
                   WHERE sa.song_id = s.id
                     AND (ar.name ILIKE :query || '%' OR ar.name % :query
                       OR ar.character_name ILIKE :query || '%' OR ar.character_name % :query
                       OR ar.voice_actor_name ILIKE :query || '%' OR ar.voice_actor_name % :query
                       OR EXISTS (
                           SELECT 1 FROM artist_alias aa
                           WHERE aa.artist_id = ar.id
                             AND (aa.alias ILIKE :query || '%' OR aa.alias % :query)
                       ))
               )
            ORDER BY
                CASE WHEN s.title ILIKE :query || '%' THEN 0 WHEN s.title % :query THEN 1 ELSE 2 END,
                similarity(s.title, :query) DESC,
                s.id
            LIMIT :limit
            """, nativeQuery = true)
    List<SongSearchProjection> searchCatalog(
            @Param("query") String query,
            @Param("limit") int limit);
}
