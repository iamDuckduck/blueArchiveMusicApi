package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.Album;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AlbumRepository extends JpaRepository<Album,String> {
}
