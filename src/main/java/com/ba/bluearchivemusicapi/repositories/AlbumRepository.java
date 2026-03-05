package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.Album;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface AlbumRepository extends JpaRepository<Album,String> {
    Optional<Album> findById(Long id);
}
