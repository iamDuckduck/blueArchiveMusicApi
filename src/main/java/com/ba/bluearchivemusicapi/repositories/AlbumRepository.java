package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.Album;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

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
}
