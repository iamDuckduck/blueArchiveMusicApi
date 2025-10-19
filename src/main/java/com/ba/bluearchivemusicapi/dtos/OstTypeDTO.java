package com.ba.bluearchivemusicapi.dtos;

import lombok.Data;

// for returning OstType data
@Data
public class OstTypeDTO {
    private Long id;
    private String name;
    private int volume;
    private String image_path;

}
