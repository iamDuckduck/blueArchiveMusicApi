package com.ba.bluearchivemusicapi.mappers;

import com.ba.bluearchivemusicapi.dtos.album.AlbumDTO;
import com.ba.bluearchivemusicapi.dtos.album.AlbumDetailsDTO;
import com.ba.bluearchivemusicapi.entities.Album;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

@Mapper(componentModel = "spring", uses =  {SongMapper.class})
public interface AlbumMapper {

    @Mapping(source = "category.category", target = "category")
    AlbumDTO albumToAlbumDTO(Album album);

    AlbumDetailsDTO albumToAlbumDetailsDTO(Album album);
}
