package com.ba.bluearchivemusicapi.dtos.category;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class CategoryUploadDTO {
    @NotNull(message = "categoryName is required")
    @NotBlank(message = "categoryName cannot be empty")
    private String categoryName;
}
