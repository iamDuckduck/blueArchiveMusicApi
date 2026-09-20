package com.ba.bluearchivemusicapi.dtos.artist;

import lombok.Data;
import java.util.List;

@Data
public class ArtistDTO {
    private Long id;
    private String name;
    private String characterName;
    private String voiceActorName;
    private List<String> aliases;
}
