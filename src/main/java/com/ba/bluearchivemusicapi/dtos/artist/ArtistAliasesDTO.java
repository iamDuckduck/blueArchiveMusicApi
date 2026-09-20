package com.ba.bluearchivemusicapi.dtos.artist;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.List;

public record ArtistAliasesDTO(
        @NotNull @Size(max = 20) List<@NotBlank @Size(max = 255) String> aliases) {
}
