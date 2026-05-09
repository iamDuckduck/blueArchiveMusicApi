package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.Song;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface SongRepository extends JpaRepository<Song, Long> {
    @Query("SELECT s FROM Song s ORDER BY random()")
    List<Song> findRandomSong(Pageable pageable);
}
