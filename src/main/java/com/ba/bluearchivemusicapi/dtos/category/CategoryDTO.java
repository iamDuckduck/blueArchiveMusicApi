package com.ba.bluearchivemusicapi.dtos.category;

import lombok.Data;

import java.time.LocalDate;

@Data
public class CategoryDTO {
    private Integer id;
    private String category;
    private LocalDate createdDate;
    private LocalDate updatedDate;
}
