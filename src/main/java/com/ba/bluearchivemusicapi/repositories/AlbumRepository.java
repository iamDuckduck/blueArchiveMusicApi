package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.Album;
import com.ba.bluearchivemusicapi.repositories.projection.AlbumSearchProjection;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface AlbumRepository extends JpaRepository<Album,Long> {
    Optional<Album> findById(Long id);
    Optional<Album> findByImportSourceAndSourceAlbumId(String importSource, String sourceAlbumId);

    @org.springframework.data.jpa.repository.Lock(jakarta.persistence.LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT a FROM Album a WHERE a.importSource = :source AND a.sourceAlbumId = :identity")
    Optional<Album> findImportForUpdate(String source, String identity);

    @Query("SELECT DISTINCT a FROM Album a " +
           "LEFT JOIN FETCH a.category " +
           "LEFT JOIN FETCH a.songList")
    List<Album> findAllWithCategoryAndSongs();

    @Query("SELECT a FROM Album a " +
           "LEFT JOIN FETCH a.category " +
           "LEFT JOIN FETCH a.songList " +
           "WHERE a.id = :albumId")
    Album findAlbumWithSongListById(Long albumId);

    // An album matches a credited identity only through one of its own songs.
    @Query(value = """
            SELECT
                a.id,
                a.title,
                a.cover_image_path AS "coverImagePath"
            FROM album a
            WHERE a.title ILIKE :query || '%'
               OR a.title % :query
               OR EXISTS (
                   SELECT 1
                   FROM song s
                   JOIN song_artist sa ON sa.song_id = s.id
                   JOIN artist ar ON ar.id = sa.artist_id
                   WHERE s.album_id = a.id
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
                CASE WHEN a.title ILIKE :query || '%' THEN 0 WHEN a.title % :query THEN 1 ELSE 2 END,
                similarity(a.title, :query) DESC,
                a.id
            LIMIT :limit
            """, nativeQuery = true)
    List<AlbumSearchProjection> searchCatalog(
            @Param("query") String query,
            @Param("limit") int limit);
}
