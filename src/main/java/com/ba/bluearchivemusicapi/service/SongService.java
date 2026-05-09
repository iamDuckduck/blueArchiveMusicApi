package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.common.constant.UploadResourceType;
import com.ba.bluearchivemusicapi.common.exception.ResourceNotFoundException;
import com.ba.bluearchivemusicapi.common.utils.CloudflareUtil;
import com.ba.bluearchivemusicapi.dtos.song.SongDTO;
import com.ba.bluearchivemusicapi.dtos.song.SongUploadDTO;
import com.ba.bluearchivemusicapi.entities.Album;
import com.ba.bluearchivemusicapi.entities.Artist;
import com.ba.bluearchivemusicapi.entities.Song;
import com.ba.bluearchivemusicapi.entities.SongArtistType;
import com.ba.bluearchivemusicapi.mappers.SongMapper;
import com.ba.bluearchivemusicapi.repositories.AlbumRepository;
import com.ba.bluearchivemusicapi.repositories.ArtistRepository;
import com.ba.bluearchivemusicapi.repositories.SongRepository;
import lombok.AllArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

import static com.ba.bluearchivemusicapi.common.constant.CacheConstants.SONG_PLAYCOUNT_CACHE;

@Service
@AllArgsConstructor
public class SongService {

	private final AlbumRepository albumRepository;

    private final SongRepository songRepository;

    private final CloudflareUtil cloudflareUtil;

    private final SongMapper songMapper;

    private final ArtistRepository artistRepository;

    private final RedisTemplate<String, Integer> integerRedisTemplate;

    @Transactional
	public SongDTO uploadSong(SongUploadDTO songUploadDTO) {
		Album album = albumRepository.findById(songUploadDTO.getAlbumId()).orElseThrow(
				() -> new ResourceNotFoundException("Album not found with id: " + songUploadDTO.getAlbumId()));

        String songFilePath = cloudflareUtil.uploadFileToBucket(songUploadDTO.getAudioFile(), UploadResourceType.SONG);
        String coverImagePath = cloudflareUtil.uploadFileToBucket(songUploadDTO.getImageFile(), UploadResourceType.SONG);

        Song song = Song.builder()
                .title(songUploadDTO.getTitle())
                .audioPath(songFilePath)
                .imagePath(coverImagePath)
                .description(songUploadDTO.getDescription())
                .playCount(0L)
                .album(album)
                .build();

        // Link artists (M:M)
        addArtistsToSong(song, songUploadDTO.getArtistIds(), SongArtistType.ARTIST);
        addArtistsToSong(song, songUploadDTO.getComposerIds(), SongArtistType.COMPOSER);

        songRepository.save(song);

        return songMapper.songToSongDTO(song);
    }

    private void addArtistsToSong(Song song, List<Long> artistIds, SongArtistType type) {
        if (artistIds == null || artistIds.isEmpty()) return;
        for (Long artistId : artistIds) {
            Artist artist = artistRepository.findById(artistId)
                    .orElseThrow(() -> new ResourceNotFoundException(
                            type.name() + " not found with id: " + artistId));
            song.addArtist(artist, type);
        }
    }

    public SongDTO getRandomSong() {
        List<Song> randomSong = songRepository.findRandomSong(PageRequest.of(0, 1));

        if (randomSong.isEmpty()) {
            throw new ResourceNotFoundException("No songs found");
        }

        return songMapper.songToSongDTO(randomSong.get(0));
    }

    public List<SongDTO> getRandomSongList() {
        List<Song> randomSongList = songRepository.findRandomSong(PageRequest.of(0, 10));

        if (randomSongList.isEmpty()) {
            throw new ResourceNotFoundException("No songs found");
        }

        return songMapper.songsToSongDTOs(randomSongList);
    }

    public void incrementSongPlayCount(Long id) {
        String playCountCacheKey = SONG_PLAYCOUNT_CACHE + "::" + id;
        integerRedisTemplate.opsForValue().increment(playCountCacheKey, 1);
    }
}
