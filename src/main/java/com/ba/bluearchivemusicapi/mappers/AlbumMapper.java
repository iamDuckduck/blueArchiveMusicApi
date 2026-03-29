package com.ba.bluearchivemusicapi.mappers;

import com.ba.bluearchivemusicapi.dtos.album.AlbumDTO;
import com.ba.bluearchivemusicapi.entities.Album;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

@Mapper(componentModel = "spring")
public interface AlbumMapper {

    @Mapping(source = "category.category", target = "category")
    AlbumDTO albumToAlbumDTO(Album album);
}
