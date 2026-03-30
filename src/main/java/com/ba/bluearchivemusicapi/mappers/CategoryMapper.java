package com.ba.bluearchivemusicapi.mappers;

import com.ba.bluearchivemusicapi.dtos.category.CategoryDTO;
import com.ba.bluearchivemusicapi.dtos.category.CategoryWithAlbumInfoDTO;
import com.ba.bluearchivemusicapi.entities.Category;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

@Mapper(componentModel = "spring", uses = AlbumMapper.class)
public interface CategoryMapper {

    @Mapping(source = "id", target = "id")
    CategoryDTO categoryToCategoryDTO(Category category);

    @Mapping(source = "albumList", target = "albumList")
    CategoryWithAlbumInfoDTO categoryToCategoryWithAlbumInfoDTO(Category category);
}
