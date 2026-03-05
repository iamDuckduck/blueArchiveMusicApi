package com.ba.bluearchivemusicapi.dtos.song;

import lombok.Data;

@Data
public class SongDTO {
    private String title;

    private String albumTitle;

    private String artist;

    private String composer;

    private String audioPath;

    private String imagePath;

    private String description;

    private Long playCount;
}
