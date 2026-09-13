package com.ba.bluearchivemusicapi.dtos.catalog;

import java.util.Map;

public record CatalogImportStateDTO(boolean exists, Long albumId, Long songId, String revision,
                                    Map<String, Object> metadata, Map<String, String> media) {
    public static CatalogImportStateDTO missing() {
        return new CatalogImportStateDTO(false, null, null, null, Map.of(), Map.of());
    }
}
