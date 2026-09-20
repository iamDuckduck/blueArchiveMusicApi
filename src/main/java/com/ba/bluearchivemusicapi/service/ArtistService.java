package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.dtos.artist.ArtistDTO;
import com.ba.bluearchivemusicapi.dtos.artist.ArtistUploadDTO;
import com.ba.bluearchivemusicapi.dtos.artist.ArtistAliasesDTO;
import com.ba.bluearchivemusicapi.common.exception.ResourceNotFoundException;
import com.ba.bluearchivemusicapi.entities.Artist;
import com.ba.bluearchivemusicapi.repositories.ArtistRepository;
import lombok.AllArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashSet;
import java.util.List;

@Service
@AllArgsConstructor
public class ArtistService {
    
    private final ArtistRepository artistRepository;
    
    @Transactional
    public ArtistDTO uploadArtist(ArtistUploadDTO artistUploadDTO) {
        String name = artistUploadDTO.getName().strip();

        artistRepository.findByName(name).ifPresent(artist -> {
            throw new IllegalArgumentException("Artist with the same name already exists");
        });

        return toDTO(artistRepository.save(Artist.builder().name(name).build()));
    }

    @Transactional(readOnly = true)
    public List<ArtistDTO> findArtists(String query) {
        if (query.length() > 255) throw new IllegalArgumentException("Artist lookup is limited to 255 characters");
        return artistRepository.findByNameContainingIgnoreCase(query.strip(),
                PageRequest.of(0, 50, Sort.by("name").ascending().and(Sort.by("id"))))
                .stream().map(this::toDTO).toList();
    }

    @Transactional(readOnly = true)
    public ArtistDTO getArtist(Long id) {
        return toDTO(requireArtist(id));
    }

    @Transactional
    public ArtistDTO updateAliases(Long id, ArtistAliasesDTO input) {
        if (input.aliases() == null || input.aliases().size() > 20) {
            throw new IllegalArgumentException("Supply up to 20 aliases; use an empty list to remove them");
        }
        var aliases = new LinkedHashSet<String>();
        for (String alias : input.aliases()) {
            if (alias == null || alias.isBlank() || alias.length() > 255) {
                throw new IllegalArgumentException("Aliases must contain 1 to 255 characters");
            }
            aliases.add(alias.strip());
        }
        Artist artist = requireArtist(id);
        // Aliases are search hints, never a request to merge or rename artists.
        artist.getAliases().clear();
        artist.getAliases().addAll(aliases);
        return toDTO(artist);
    }

    private Artist requireArtist(Long id) {
        return artistRepository.findById(id).orElseThrow(
                () -> new ResourceNotFoundException("Artist not found with id: " + id));
    }

    private ArtistDTO toDTO(Artist artist) {
        ArtistDTO artistDTO = new ArtistDTO();
        artistDTO.setName(artist.getName());
        artistDTO.setId(artist.getId());
        artistDTO.setCharacterName(artist.getCharacterName());
        artistDTO.setVoiceActorName(artist.getVoiceActorName());
        artistDTO.setAliases(artist.getAliases().stream().sorted().toList());
        return artistDTO;
    }
}
