package com.ba.bluearchivemusicapi.repositories.projection;

public interface SongSearchProjection {
    Long getId();

    String getTitle();

    Long getAlbumId();

    String getAlbumTitle();

    String getImagePath();
}
