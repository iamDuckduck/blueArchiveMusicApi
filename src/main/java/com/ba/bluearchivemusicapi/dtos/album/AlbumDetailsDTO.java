package com.ba.bluearchivemusicapi.dtos.album;

import com.ba.bluearchivemusicapi.dtos.song.SongDTO;
import lombok.Data;

import java.time.LocalDate;
import java.util.List;

@Data
public class AlbumDetailsDTO {
    private Long id;

    private String title;

    private String coverImagePath;

    private String releaseDate;

    private String description;

    private List<SongDTO> songList;

    private LocalDate createdDate;

    private LocalDate updatedDate;
}
