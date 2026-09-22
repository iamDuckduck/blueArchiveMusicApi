package com.ba.bluearchivemusicapi.dtos.catalog;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.util.List;

public record CatalogTrackImportDTO(
        @NotBlank String title,
        @Min(1) @Max(999) Integer disc,
        @Min(1) @Max(999) Integer position,
        @NotNull @Min(1) @Max(999999) Integer displayOrder,
        @NotBlank String kind,
        String description,
        List<String> artists,
        List<String> composers,
        List<CatalogPerformerDTO> performers) {
}
