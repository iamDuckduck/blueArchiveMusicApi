package com.ba.bluearchivemusicapi.dtos;

import lombok.Data;

@Data
public class OstPageDTO {
    private Long id;

    private int ostNumber;

    private String name;

    private String author;

    private String image_path;

    private String audio_path;

    private Long ostTypeId;

    private String VolumeName;

    private int volume;

    private Integer playCount;
}




