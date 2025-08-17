package com.ba.bluearchivemusicapi.dtos;

import jakarta.validation.constraints.*;
import lombok.Data;
import org.springframework.web.multipart.MultipartFile;

// for uploading OST
@Data
public class OstUploadDTO {
    @Min(value = 1, message = "ostNumber should at least be 1")
    private int ostNumber;

    @NotNull(message = "name cannot be null")
    @NotBlank(message = "name is required and cannot be empty")
    private String name;

    @NotNull(message = "name cannot be null")
    @NotBlank(message = "author is required and cannot be empty")
    private String author;

    @NotNull(message = "audio is required")
    private MultipartFile audio;

    @NotNull(message = "image is required")
    private MultipartFile image;

    @NotNull(message = "ostTypeName is required")
    private String ostTypeName;
}
