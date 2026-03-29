package com.ba.bluearchivemusicapi.dtos.song;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@Data
public class SongUploadDTO {

    @NotNull(message = "title is required")
    @NotBlank(message = "title cannot be blank")
    private String title;

    @NotNull(message = "albumId is required")
    private Long albumId;

    private List<Long> artistIds;

    private List<Long> composerIds;

    private String description;

    // TODO: validate file type and size
    @NotNull(message = "image file is required")
    private MultipartFile imageFile;

    // TODO: validate file type and size
    @NotNull(message = "audio file is required")
    private MultipartFile audioFile;
}
