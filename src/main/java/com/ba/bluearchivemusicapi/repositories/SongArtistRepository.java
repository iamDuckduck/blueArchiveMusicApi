package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.SongArtist;
import com.ba.bluearchivemusicapi.entities.SongArtistId;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface SongArtistRepository extends JpaRepository<SongArtist, SongArtistId> {
    List<SongArtist> findBySongId(Long songId);
    List<SongArtist> findByArtistId(Long artistId);
}

