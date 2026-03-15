package com.ba.bluearchivemusicapi.mappers;

import com.ba.bluearchivemusicapi.dtos.song.SongDTO;
import com.ba.bluearchivemusicapi.entities.Song;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

@Mapper(componentModel = "spring")
public interface SongMapper {

    @Mapping(source = "album.title", target = "albumTitle")
    @Mapping(source = "artist.name", target = "artist")
    @Mapping(source = "composer.name", target = "composer")
    SongDTO songToSongDTO(Song song);
}
