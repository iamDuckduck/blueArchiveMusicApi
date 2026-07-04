package com.ba.bluearchivemusicapi.dtos.search;

import lombok.Data;

import java.util.List;

@Data
public class MusicSearchResponseDTO {
    private List<AlbumSearchResultDTO> albums;

    private List<SongSearchResultDTO> songs;
}
