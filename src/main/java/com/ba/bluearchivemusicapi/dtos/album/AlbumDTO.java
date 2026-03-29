package com.ba.bluearchivemusicapi.dtos.album;

import lombok.Data;
import java.time.LocalDate;

@Data
public class AlbumDTO {
    private String title;

    private String coverImagePath;

    private String releaseDate;

    private String description;

    private String category;

    private LocalDate createdDate;

    private LocalDate updatedDate;
}
