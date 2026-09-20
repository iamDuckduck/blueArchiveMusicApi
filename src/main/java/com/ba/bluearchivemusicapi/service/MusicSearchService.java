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
    private static final int QUERY_LIMIT = 255;

    private final AlbumRepository albumRepository;

    private final SongRepository songRepository;

    private final MusicSearchMapper musicSearchMapper;

    public MusicSearchResponseDTO search(String searchQuery) {
        String query = searchQuery.strip();
        if (query.length() > QUERY_LIMIT) {
            throw new IllegalArgumentException("Search query must be at most 255 characters.");
        }
        MusicSearchResponseDTO response = new MusicSearchResponseDTO();

        if (query.isEmpty()) {
            response.setAlbums(List.of());
            response.setSongs(List.of());
            return response;
        }

        response.setAlbums(musicSearchMapper.toAlbumSearchResults(
                albumRepository.searchCatalog(query, RESULT_LIMIT)));
        response.setSongs(musicSearchMapper.toSongSearchResults(
                songRepository.searchCatalog(query, RESULT_LIMIT)));
        return response;
    }
}
