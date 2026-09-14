package com.ba.bluearchivemusicapi.dtos.catalog;

import jakarta.validation.constraints.NotBlank;
import java.time.LocalDate;

public record CatalogAlbumImportDTO(
        @NotBlank String title,
        @NotBlank String category,
        LocalDate releaseDate,
        String description) {
}
