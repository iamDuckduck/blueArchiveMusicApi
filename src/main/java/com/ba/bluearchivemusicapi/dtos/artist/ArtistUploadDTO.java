package com.ba.bluearchivemusicapi.dtos.artist;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class ArtistUploadDTO {

    @NotNull(message = "Artist name is required")
    @NotBlank(message = "Artist name cannot be blank")
    private String name;
}
