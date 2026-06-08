package com.ba.bluearchivemusicapi.mappers;

import com.ba.bluearchivemusicapi.dtos.song.SongDTO;
import com.ba.bluearchivemusicapi.entities.Artist;
import com.ba.bluearchivemusicapi.entities.Song;
import com.ba.bluearchivemusicapi.entities.SongArtist;
import com.ba.bluearchivemusicapi.entities.SongArtistType;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.Named;

import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

@Mapper(componentModel = "spring")
public interface SongMapper {

    @Mapping(source = "album.title", target = "albumTitle")
    @Mapping(source = "songArtists", target = "artists", qualifiedByName = "toArtistNames")
    @Mapping(source = "songArtists", target = "composers", qualifiedByName = "toComposerNames")
    @Mapping(source = "id", target = "id")
    SongDTO songToSongDTO(Song song);

    List<SongDTO> songsToSongDTOs(List<Song> songs);

    @Named("toArtistNames")
    default List<String> toArtistNames(List<SongArtist> songArtists) {
        if (songArtists == null) return Collections.emptyList();
        return songArtists.stream()
                .filter(sa -> sa.getType() == SongArtistType.ARTIST)
                .map(SongArtist::getArtist)
                .map(Artist::getName)
                .collect(Collectors.toList());
    }

    @Named("toComposerNames")
    default List<String> toComposerNames(List<SongArtist> songArtists) {
        if (songArtists == null) return Collections.emptyList();
        return songArtists.stream()
                .filter(sa -> sa.getType() == SongArtistType.COMPOSER)
                .map(SongArtist::getArtist)
                .map(Artist::getName)
                .collect(Collectors.toList());
    }
}
