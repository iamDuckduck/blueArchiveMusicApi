package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.common.constant.UploadResourceType;
import com.ba.bluearchivemusicapi.common.exception.ResourceNotFoundException;
import com.ba.bluearchivemusicapi.common.utils.CloudflareUtil;
import com.ba.bluearchivemusicapi.dtos.song.SongDTO;
import com.ba.bluearchivemusicapi.dtos.song.SongUploadDTO;
import com.ba.bluearchivemusicapi.entities.Album;
import com.ba.bluearchivemusicapi.entities.Song;
import com.ba.bluearchivemusicapi.mappers.SongMapper;
import com.ba.bluearchivemusicapi.repositories.AlbumRepository;
import com.ba.bluearchivemusicapi.repositories.SongRepository;
import lombok.AllArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@AllArgsConstructor
public class SongService {

	private final AlbumRepository albumRepository;

    private final SongRepository songRepository;

    private final CloudflareUtil cloudflareUtil;

    private final SongMapper songMapper;

	public SongDTO uploadSong(SongUploadDTO songUploadDTO) {
		Album album = albumRepository.findById(songUploadDTO.getAlbumId()).orElseThrow(
				() -> new ResourceNotFoundException("Album not found with id: " + songUploadDTO.getAlbumId()));


        String songFilePath = cloudflareUtil.uploadFileToBucket(songUploadDTO.getAudioFile(), UploadResourceType.SONG);
        String coverImagePath = cloudflareUtil.uploadFileToBucket(songUploadDTO.getImageFile(), UploadResourceType.SONG);

        Song song = Song.builder()
                .title(songUploadDTO.getTitle())
                .artist(songUploadDTO.getArtist())
                .composer(songUploadDTO.getComposer())
                .audioPath(songFilePath)
                .imagePath(coverImagePath)
                .description(songUploadDTO.getDescription())
                .playCount(0L)
                .album(album)
                .build();

        songRepository.save(song);

        return songMapper.songToSongDTO(song);
    }
}
