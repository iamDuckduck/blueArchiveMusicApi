package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.Artist;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface ArtistRepository extends JpaRepository<Artist,String> {
    Optional<Artist> findById(Long id);
}
