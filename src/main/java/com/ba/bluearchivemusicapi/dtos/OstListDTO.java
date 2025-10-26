package com.ba.bluearchivemusicapi.dtos;

import lombok.Data;

@Data
public class OstListDTO {
    private Long id;

    private int ostNumber;

    private String name;

    private String author;

    private String image_path;

    private String audio_path;

    private Integer playCount;
}
