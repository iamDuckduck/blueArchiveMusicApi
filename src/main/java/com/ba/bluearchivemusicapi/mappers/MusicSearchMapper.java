package com.ba.bluearchivemusicapi.mappers;

import com.ba.bluearchivemusicapi.dtos.search.AlbumSearchResultDTO;
import com.ba.bluearchivemusicapi.dtos.search.SongSearchResultDTO;
import com.ba.bluearchivemusicapi.repositories.projection.AlbumSearchProjection;
import com.ba.bluearchivemusicapi.repositories.projection.SongSearchProjection;
import org.mapstruct.Mapper;

import java.util.List;

@Mapper(componentModel = "spring")
public interface MusicSearchMapper {
    List<AlbumSearchResultDTO> toAlbumSearchResults(List<AlbumSearchProjection> albums);

    List<SongSearchResultDTO> toSongSearchResults(List<SongSearchProjection> songs);
}
