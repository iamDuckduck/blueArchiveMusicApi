package com.ba.bluearchivemusicapi.dtos.search;

import lombok.Data;

@Data
public class AlbumSearchResultDTO {
    private Long id;

    private String title;

    private String coverImagePath;
}
