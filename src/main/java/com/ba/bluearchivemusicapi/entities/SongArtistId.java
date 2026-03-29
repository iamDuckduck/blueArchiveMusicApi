package com.ba.bluearchivemusicapi.entities;

import lombok.*;

import java.io.Serializable;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class SongArtistId implements Serializable {
    private Long song;
    private Long artist;
    private SongArtistType type;
}

