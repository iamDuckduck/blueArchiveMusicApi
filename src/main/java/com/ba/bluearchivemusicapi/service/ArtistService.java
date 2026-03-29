package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.dtos.artist.ArtistDTO;
import com.ba.bluearchivemusicapi.dtos.artist.ArtistUploadDTO;
import com.ba.bluearchivemusicapi.entities.Artist;
import com.ba.bluearchivemusicapi.repositories.ArtistRepository;
import lombok.AllArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@AllArgsConstructor
public class ArtistService {
    
    private final ArtistRepository artistRepository;
    
    public ArtistDTO uploadArtist(ArtistUploadDTO artistUploadDTO) {

        artistRepository.findByName(artistUploadDTO.getName()).ifPresent(artist -> {
            throw new RuntimeException("Artist with the same name already exists");
        });

		Artist artist = Artist.builder().name(artistUploadDTO.getName()).build();
        artistRepository.save(artist);

        ArtistDTO artistDTO = new ArtistDTO();
        artistDTO.setName(artistUploadDTO.getName());
        artistDTO.setId(artist.getId());
        return artistDTO;
    }
}
