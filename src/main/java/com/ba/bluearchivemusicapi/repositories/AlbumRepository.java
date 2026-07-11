package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.Album;
import com.ba.bluearchivemusicapi.repositories.projection.AlbumSearchProjection;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface AlbumRepository extends JpaRepository<Album,String> {
    Optional<Album> findById(Long id);

    @Query("SELECT DISTINCT a FROM Album a " +
           "LEFT JOIN FETCH a.category " +
           "LEFT JOIN FETCH a.songList")
    List<Album> findAllWithCategoryAndSongs();

    @Query("SELECT a FROM Album a " +
           "LEFT JOIN FETCH a.category " +
           "LEFT JOIN FETCH a.songList " +
           "WHERE a.id = :albumId")
    Album findAlbumWithSongListById(Long albumId);

    @Query(value = """
            SELECT
                a.id,
                a.title,
                a.cover_image_path AS "coverImagePath"
            FROM album a
            WHERE a.title ILIKE :query || '%'
               OR a.title % :query
            ORDER BY
                CASE WHEN a.title ILIKE :query || '%' THEN 0 ELSE 1 END,
                similarity(a.title, :query) DESC
            LIMIT :limit
            """, nativeQuery = true)
    List<AlbumSearchProjection> searchByTitle(
            @Param("query") String query,
            @Param("limit") int limit);
}
