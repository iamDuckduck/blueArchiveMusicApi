package com.ba.bluearchivemusicapi.common.utils;

import com.ba.bluearchivemusicapi.dtos.album.AlbumDTO;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

class AlbumTitleVolumeOrderTest {

    @Test
    void sortsAlbumsByNumericVolumeThenPlacesUnnumberedTitlesLast() {
        List<AlbumDTO> albums = new ArrayList<>(List.of(
                album(1L, "Blue Archive OST Vol. 10"),
                album(2L, "Zeta Collection"),
                album(3L, "Blue Archive OST vol 3"),
                album(4L, "Blue Archive OST VOL.4"),
                album(5L, "Blue Archive OST VOL. 2"),
                album(6L, "Another Collection")
        ));

        AlbumTitleVolumeOrder.sort(albums);

        assertEquals(
                List.of(5L, 3L, 4L, 1L, 6L, 2L),
                albums.stream().map(AlbumDTO::getId).toList()
        );
    }

    private AlbumDTO album(Long id, String title) {
        AlbumDTO album = new AlbumDTO();
        album.setId(id);
        album.setTitle(title);
        return album;
    }
}
