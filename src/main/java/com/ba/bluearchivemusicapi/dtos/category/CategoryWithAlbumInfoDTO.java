package com.ba.bluearchivemusicapi.dtos.category;

import com.ba.bluearchivemusicapi.dtos.album.AlbumDTO;
import lombok.Data;

import java.time.LocalDate;
import java.util.List;

@Data
public class CategoryWithAlbumInfoDTO {
    private Integer id;
    private String category;
    private List<AlbumDTO> albumList;
    private LocalDate createdDate;
    private LocalDate updatedDate;
}
