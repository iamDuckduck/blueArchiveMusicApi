package com.ba.bluearchivemusicapi.dtos.song;

import lombok.Data;

import java.util.List;

@Data
public class SongDTO {
    private Long id;

    private String title;

    private String albumTitle;

    private List<String> artists;

    private List<String> composers;

    private String audioPath;

    private String imagePath;

    private String description;

    private Long playCount;
}
