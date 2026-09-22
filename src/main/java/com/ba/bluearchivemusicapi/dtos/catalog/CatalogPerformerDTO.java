package com.ba.bluearchivemusicapi.dtos.catalog;

public record CatalogPerformerDTO(String character, String voiceActor) {
    public String displayName() {
        if (character != null && !character.isBlank() && voiceActor != null && !voiceActor.isBlank()) {
            return character.strip() + " / " + voiceActor.strip();
        }
        if (character != null && !character.isBlank()) return character.strip();
        return voiceActor == null ? "" : voiceActor.strip();
    }
}
