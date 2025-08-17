package com.ba.bluearchivemusicapi.dtos;

import lombok.Data;

// for return DTO data
@Data
public class OstDTO {
    private Long id;

    private int ostNumber;

    private String name;

    private String author;
    
    private String image_path;

    private String audio_path;

    private OstTypeDTO ostType;
}
