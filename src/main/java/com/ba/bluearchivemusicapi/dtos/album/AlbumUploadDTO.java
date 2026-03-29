package com.ba.bluearchivemusicapi.dtos.album;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PastOrPresent;
import lombok.Data;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDate;

@Data
public class AlbumUploadDTO {
    @NotNull(message = "title cannot be empty")
    @NotBlank(message = "title is required")
    private String title;

    // TODO: validate file type and size
    @NotNull(message = "coverImage cannot be empty")
    private MultipartFile coverImage;

    @PastOrPresent
    private LocalDate releaseDate;

    private String description;

    @NotNull(message = "categoryId cannot be empty")
    private Long categoryId;
}
