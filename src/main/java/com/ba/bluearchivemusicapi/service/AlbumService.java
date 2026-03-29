package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.common.constant.UploadResourceType;
import com.ba.bluearchivemusicapi.common.exception.ResourceNotFoundException;
import com.ba.bluearchivemusicapi.common.utils.CloudflareUtil;
import com.ba.bluearchivemusicapi.dtos.album.AlbumDTO;
import com.ba.bluearchivemusicapi.dtos.album.AlbumUploadDTO;
import com.ba.bluearchivemusicapi.entities.Album;
import com.ba.bluearchivemusicapi.entities.Category;
import com.ba.bluearchivemusicapi.mappers.AlbumMapper;
import com.ba.bluearchivemusicapi.repositories.AlbumRepository;
import com.ba.bluearchivemusicapi.repositories.CategoryRepository;
import lombok.AllArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@AllArgsConstructor
@Service
public class AlbumService {

    private final CloudflareUtil cloudflareUtil;

    private final AlbumRepository albumRepository;

    private final CategoryRepository categoryRepository;

    private final AlbumMapper albumMapper;

    @Transactional(rollbackFor = Exception.class)
    public AlbumDTO uploadAlbum(AlbumUploadDTO albumUploadDTO) {
        Category category = categoryRepository.findById(albumUploadDTO.getCategoryId())
                .orElseThrow(
                        ()->new ResourceNotFoundException("Category not found")
                );

        String coverImagePath = cloudflareUtil.uploadFileToBucket(albumUploadDTO.getCoverImage(), UploadResourceType.ALBUM);

        Album album = Album.builder()
                .title(albumUploadDTO.getTitle())
                .coverImagePath(coverImagePath)
                .releaseDate(albumUploadDTO.getReleaseDate())
                .description(albumUploadDTO.getDescription())
                .category(category)
                .build();


        albumRepository.save(album);
        return albumMapper.albumToAlbumDTO(album);
    }
}
