package com.ba.bluearchivemusicapi.controller.user;

import com.ba.bluearchivemusicapi.dtos.album.AlbumDetailsDTO;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import com.ba.bluearchivemusicapi.service.AlbumService;
import lombok.AllArgsConstructor;
import java.util.List;

@RestController("UserAlbumController")
@RequestMapping("/user/albums")
@AllArgsConstructor
public class AlbumController {

    private final AlbumService albumService;

    @GetMapping("/details")
    public ResponseEntity<List<AlbumDetailsDTO>> getAllAlbumsWithDetails() {
        List<AlbumDetailsDTO> albums = albumService.getAllAlbumsWithDetails();
        return ResponseEntity.ok(albums);
    }

    @GetMapping("/{albumId}/songs")
    public ResponseEntity<AlbumDetailsDTO> getAlbumDetailsById(@PathVariable Long albumId) {
        AlbumDetailsDTO albumDetails = albumService.getAlbumDetailsById(albumId);
        return ResponseEntity.ok(albumDetails);
    }
}
