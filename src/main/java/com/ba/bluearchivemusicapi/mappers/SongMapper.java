package com.ba.bluearchivemusicapi.mappers;

import com.ba.bluearchivemusicapi.dtos.song.SongDTO;
import com.ba.bluearchivemusicapi.entities.Song;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

@Mapper(componentModel = "spring")
public interface SongMapper {

    @Mapping(source = "album.title", target = "albumTitle")
    SongDTO songToSongDTO(Song song);
}
