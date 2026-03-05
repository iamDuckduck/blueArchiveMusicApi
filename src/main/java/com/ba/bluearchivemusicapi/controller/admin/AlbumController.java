package com.ba.bluearchivemusicapi.controller.admin;

import com.ba.bluearchivemusicapi.dtos.album.AlbumDTO;
import com.ba.bluearchivemusicapi.dtos.album.AlbumUploadDTO;
import com.ba.bluearchivemusicapi.service.AlbumService;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@Tag(
        name = "Album",
        description = "API endpoints for managing albums."
)
@RestController
@RequestMapping("/admin/album")
@AllArgsConstructor
public class AlbumController {

    private final AlbumService albumService;

    @PostMapping("/upload")
    public ResponseEntity<AlbumDTO> uploadAlbum(@Valid @ModelAttribute AlbumUploadDTO albumUploadDTO) {
        AlbumDTO albumDTO = albumService.uploadAlbum(albumUploadDTO);
        return ResponseEntity.ok(albumDTO);
    }
}
