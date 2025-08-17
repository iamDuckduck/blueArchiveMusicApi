package com.ba.bluearchivemusicapi.dtos;

import jakarta.validation.constraints.*;
import lombok.Data;
import org.springframework.web.multipart.MultipartFile;


// for editing Ost DTO
@Data
public class OstEditDTO {
    @Min(value = 1, message = "ostNumber should at least be 1")
    private int ostNumber;

    @NotBlank(message = "name is required and cannot be empty")
    private String name;

    @NotBlank(message = "author is required and cannot be empty")
    private String author;

    @NotNull(message = "image_path is required")
    private String image_path;

    @NotNull(message = "audio_path is required")
    private String audio_path;

    @NotNull(message = "ostTypeName is required")
    private String ostTypeName;

    private MultipartFile audio;

    private MultipartFile image;
}
