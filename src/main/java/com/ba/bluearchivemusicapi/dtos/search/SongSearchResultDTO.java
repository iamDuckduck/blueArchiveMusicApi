package com.ba.bluearchivemusicapi.dtos.search;

import lombok.Data;

@Data
public class SongSearchResultDTO {
    private Long id;

    private String title;

    private Long albumId;

    private String albumTitle;

    private String imagePath;

    private String audioPath;
}
