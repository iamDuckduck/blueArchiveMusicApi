package com.ba.bluearchivemusicapi.dtos.catalog;

public record CatalogImportResultDTO(Long albumId, Long songId, boolean created, String status) {
}
