package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.Song;
import com.ba.bluearchivemusicapi.repositories.projection.SongSearchProjection;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface SongRepository extends JpaRepository<Song, Long> {
    @Query("SELECT s FROM Song s ORDER BY random()")
    List<Song> findRandomSong(Pageable pageable);

    @Query(value = """
            SELECT
                s.id,
                s.title,
                s.image_path AS "imagePath",
                a.id AS "albumId",
                a.title AS "albumTitle"
            FROM song s
            JOIN album a ON a.id = s.album_id
            WHERE s.title ILIKE :query || '%'
               OR s.title % :query
            ORDER BY
                CASE WHEN s.title ILIKE :query || '%' THEN 0 ELSE 1 END,
                similarity(s.title, :query) DESC
            LIMIT :limit
            """, nativeQuery = true)
    List<SongSearchProjection> searchByTitle(
            @Param("query") String query,
            @Param("limit") int limit);
}
