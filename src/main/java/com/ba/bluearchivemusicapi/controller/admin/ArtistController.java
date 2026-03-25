package com.ba.bluearchivemusicapi.controller.admin;

import com.ba.bluearchivemusicapi.dtos.artist.ArtistDTO;
import com.ba.bluearchivemusicapi.dtos.artist.ArtistUploadDTO;
import com.ba.bluearchivemusicapi.service.ArtistService;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(
        name = "Artist",
        description = "artist management"
)
@RestController
@RequestMapping("/admin/artist")
@AllArgsConstructor
public class ArtistController {

    private final ArtistService artistService;

    @PostMapping("/upload")
    public ResponseEntity<ArtistDTO> uploadAlbum(@Valid @ModelAttribute ArtistUploadDTO artistUploadDTO) {
        ArtistDTO artistDTO = artistService.uploadArtist(artistUploadDTO);
        return ResponseEntity.ok(artistDTO);
    }
}
