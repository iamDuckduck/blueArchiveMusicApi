package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.common.constant.UploadResourceType;
import com.ba.bluearchivemusicapi.common.exception.ResourceNotFoundException;
import com.ba.bluearchivemusicapi.common.utils.CloudflareUtil;
import com.ba.bluearchivemusicapi.dtos.song.SongDTO;
import com.ba.bluearchivemusicapi.dtos.song.SongUploadDTO;
import com.ba.bluearchivemusicapi.entities.Album;
import com.ba.bluearchivemusicapi.entities.Artist;
import com.ba.bluearchivemusicapi.entities.Song;
import com.ba.bluearchivemusicapi.mappers.SongMapper;
import com.ba.bluearchivemusicapi.repositories.AlbumRepository;
import com.ba.bluearchivemusicapi.repositories.ArtistRepository;
import com.ba.bluearchivemusicapi.repositories.SongRepository;
import lombok.AllArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.Optional;

@Service
@AllArgsConstructor
public class SongService {

	private final AlbumRepository albumRepository;

    private final SongRepository songRepository;

    private final CloudflareUtil cloudflareUtil;

    private final SongMapper songMapper;

    private final ArtistRepository artistRepository;

	public SongDTO uploadSong(SongUploadDTO songUploadDTO) {
		Album album = albumRepository.findById(songUploadDTO.getAlbumId()).orElseThrow(
				() -> new ResourceNotFoundException("Album not found with id: " + songUploadDTO.getAlbumId()));

		Artist composer = Optional.ofNullable(songUploadDTO.getComposerId())
				.map(composerId -> artistRepository.findById(composerId)
						.orElseThrow(() -> new ResourceNotFoundException("Composer not found with id: " + composerId)))
				.orElse(null);

        Artist artist = Optional.ofNullable(songUploadDTO.getArtistId())
                .map(artistId -> artistRepository.findById(artistId)
                        .orElseThrow(() -> new ResourceNotFoundException("Artist not found with id: " + artistId)))
                .orElse(null);


        String songFilePath = cloudflareUtil.uploadFileToBucket(songUploadDTO.getAudioFile(), UploadResourceType.SONG);
        String coverImagePath = cloudflareUtil.uploadFileToBucket(songUploadDTO.getImageFile(), UploadResourceType.SONG);

        Song song = Song.builder()
                .title(songUploadDTO.getTitle())
                .artist(artist)
                .composer(composer)
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
