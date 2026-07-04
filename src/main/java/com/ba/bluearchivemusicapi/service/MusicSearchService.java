package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.dtos.search.MusicSearchResponseDTO;
import com.ba.bluearchivemusicapi.mappers.MusicSearchMapper;
import com.ba.bluearchivemusicapi.repositories.AlbumRepository;
import com.ba.bluearchivemusicapi.repositories.SongRepository;
import lombok.AllArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@AllArgsConstructor
public class MusicSearchService {
    private static final int RESULT_LIMIT = 5;

    private final AlbumRepository albumRepository;

    private final SongRepository songRepository;

    private final MusicSearchMapper musicSearchMapper;

    public MusicSearchResponseDTO search(String searchQuery) {
        String query = searchQuery.trim();
        MusicSearchResponseDTO response = new MusicSearchResponseDTO();

        if (query.isEmpty()) {
            response.setAlbums(List.of());
            response.setSongs(List.of());
            return response;
        }

        response.setAlbums(musicSearchMapper.toAlbumSearchResults(
                albumRepository.searchByTitle(query, RESULT_LIMIT)));
        response.setSongs(musicSearchMapper.toSongSearchResults(
                songRepository.searchByTitle(query, RESULT_LIMIT)));
        return response;
    }
}
